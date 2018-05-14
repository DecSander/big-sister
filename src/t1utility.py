import sqlite3
import logging
import requests
from StringIO import StringIO
import json
import boto3
import uuid
from PIL import Image
import numpy as np

from utility import retrieve_startup_info
from const import TIER1_DB, MY_IP, TIMEOUT

logging.basicConfig(filename='t1.log', level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())
logger = logging.getLogger('t1')

s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')
all_seen_uuids = set()


def setup_db_tier1(counts, servers, backends):
    conn = sqlite3.connect(TIER1_DB)
    c = conn.cursor()

    c.execute('CREATE TABLE IF NOT EXISTS camera_counts (camera_id INTEGER, camera_count INTEGER, photo_time REAL);')
    c.execute('CREATE TABLE IF NOT EXISTS users (fb_id TEXT PRIMARY KEY, fb_token TEXT, name TEXT, face_encodings TEXT);')
    c.execute('CREATE TABLE IF NOT EXISTS face_sightings (sighting_time REAL, camera_id INTEGER, fb_id TEXT);')
    c.execute('CREATE TABLE IF NOT EXISTS server_list (ip_address TEXT UNIQUE);')
    c.execute('CREATE TABLE IF NOT EXISTS backend_list (ip_address TEXT UNIQUE);')
    conn.commit()

    c = conn.cursor()
    c.execute('SELECT camera_id, camera_count, photo_time FROM camera_counts;')
    camera_rows = c.fetchall()
    for row in camera_rows:
        camera_id = int(row[0])
        camera_count = int(row[1])
        photo_time = row[2]
        counts[camera_id] = {'camera_count': camera_count, 'photo_time': photo_time}

    c.execute('SELECT ip_address FROM server_list;')
    server_rows = c.fetchall()
    for row in server_rows:
        ip_address = row[0]
        servers.add(ip_address)

    c.execute('SELECT ip_address FROM backend_list;')
    backend_rows = c.fetchall()
    for row in backend_rows:
        ip_address = row[0]
        servers.add(ip_address)

    conn.close()


def persist(camera_id, camera_count, photo_time, img_id=None):
    if img_id in all_seen_uuids:
        return
    conn = sqlite3.connect(TIER1_DB)
    c = conn.cursor()
    c.execute('INSERT INTO camera_counts values (?, ?, ?);', (camera_id, camera_count, photo_time))
    conn.commit()
    conn.close()


def get_counts_at_time(time, camera_id=None):
    conn = sqlite3.connect(TIER1_DB)
    c = conn.cursor()
    if camera_id is None:
        c.execute('SELECT camera_id, camera_count, photo_time FROM camera_counts where photo_time <= (SELECT max(photo_time) FROM camera_counts WHERE photo_time < ? GROUP BY camera_id) order by photo_time desc;', (time,))
    else:
        c.execute(
            'SELECT camera_id, camera_count, photo_time FROM camera_counts WHERE camera_id = ? AND photo_time <= ?;',
            (camera_id,
             time))
    camera_rows = c.fetchall()
    conn.close()

    if len(camera_rows) == 0:
        return None
    else:
        return camera_rows[-1]


def get_last_data(camera_id=None):
    conn = sqlite3.connect(TIER1_DB)
    c = conn.cursor()
    if camera_id is None:
        c.execute("SELECT * FROM camera_counts WHERE datetime(photo_time, 'unixepoch', 'localtime') > datetime('now', '-28 days');")
    else:
        c.execute(
            "SELECT * FROM camera_counts WHERE datetime(photo_time, 'unixepoch', 'localtime') > datetime('now', '-28 days') AND camera_id = ?;",
            (camera_id,
             ))
    camera_rows = c.fetchall()
    conn.close()
    return camera_rows


def send_to_other_servers(servers, camera_id, camera_count, photo_time):
    global all_seen_uuids
    for server in servers:
        if MY_IP != server:
            try:
                seen_uuid = uuid.uuid4().hex
                all_seen_uuids.add(seen_uuid)
                result = requests.post('https://{}/update_camera'.format(server),
                                       timeout=TIMEOUT,
                                       verify=False,
                                       json={
                                       'camera_id': camera_id,
                                       'camera_count': camera_count,
                                       'photo_time': photo_time,
                                       'img_id': seen_uuid
                                       })
                if result.status_code != 200:
                    print result.json()
            except requests.exceptions.ConnectionError:
                logger.info('Failed to send count to {}'.format(server))


def temp_store(counts, camera_id, camera_count, photo_time):
    should_update = ('camera_id' not in counts) or (counts['camera_id'] < photo_time)
    if should_update:
        counts[camera_id] = {
            'camera_count': camera_count,
            'photo_time': photo_time
        }
    return should_update


def process_image(servers, counts, camera_count, camera_id, photo_time):
    if temp_store(counts, camera_id, camera_count, photo_time):
        persist(camera_id, camera_count, photo_time)
        send_to_other_servers(servers, camera_id, camera_count, photo_time)


def save_backend(backend):
    conn = sqlite3.connect(TIER1_DB)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO backend_list values (?)', (backend,))
        conn.commit()
    except sqlite3.IntegrityError:  # Indicates we already had this server address
        pass


def notify_new_server(servers):
    for server in servers:
        try:
            result = requests.post('https://{}/new_server'.format(server), verify=False, json={'ip_address': MY_IP})
            if result.status_code != 200:
                logger.warning('New server notification for server {} failed: {}'.format(server, result.text))
        except requests.exceptions.ConnectionError:
            logger.info('New server notification for server {} failed: Can\'t connect to server'.format(server))


def get_camera_count(imagefile, backends):
    imagefile_contents = imagefile.read()
    for backend in backends:
        try:
            imagefile_str = ('imagefile', StringIO(imagefile_contents), 'image/jpeg')
            result = requests.post('http://{}:5001'.format(backend), files={'imagefile': imagefile_str})
            if result.status_code == 200:
                try:
                    return json.loads(result.text)
                except ValueError:  # Received invalid JSON, try next one
                    logger.warning('Failed to retrieve camera count from {}: {}'.format(backend, result.text))
            # Else, we got an error message, try next one
            else:
                print(result.text)
        except requests.exceptions.ConnectionError:
            logger.info('Failed to retrieve camera count from {}: Couldn\'t connect to IP address'.format(backend))


def get_prediction(camera_id, timestamp, occupancy_predictors):
    payload = {"camera_id": camera_id, "timestamp": timestamp}
    for oc in occupancy_predictors:
        try:
            response = requests.post("http://" + oc, data=payload)
            if response.status_code == 200:
                return json.loads(response.text)
            elif response.status_code == 204:
                print "Received 204 from occupancy predictor service"
                return None
        except Exception as e:
            logger.info('Failed to retrieve prediction from {}'.format(oc))
            logger.info("error " + str(e))

    logger.info("could not contact any occupancy predictor service")
    return None


def upload_file_to_s3(file, camera_id, photo_time, camera_count):
    try:
        s3_client.upload_file(
            '{}_{}_{}.jpeg'.format(camera_id, int(photo_time * 1000), camera_count),
            file,
            'cc-proj',
            ExtraArgs={"ContentType": 'image/jpeg'}
        )
    except Exception as e:
        print e


def get_faces(imagefile, face_classifiers):
    imagefile_str = ('imagefile', StringIO(imagefile_contents), 'image/jpeg')
    files = {'imagefile': imagefile_str}
    for fc in face_classifiers:
        try:
            result = requests.post('http://{}/'.format(fc), files=files)
            if result.status_code == 200:
                return json.loads(response.text)
            print result.text
        except Exception as e:
            logger.info('Failed to get face classification from {}'.format(fc))
            logger.info("Error: " + str(e))


def register_user(servers, face_classifiers, fb_user_id, fb_short_token):
    json = {'fb_user_id': fb_user_id, 'fb_short_token': fb_short_token}
    for fc in face_classifiers:
        try:
            result = requests.post('http://{}/new_user'.format(fc), json)
            if result.status_code == 200:
                print result.text
                user = result.json()
                return user
            print result.text
        except Exception as e:
            logger.info('Failed to get create user from {}'.format(fc))
            logger.info("Error: " + str(e))


def persist_user(fb_id, fb_token, name, face_encodings_str):
    conn = sqlite3.connect(TIER1_DB)
    c = conn.cursor()
    c.execute('INSERT INTO users values (?, ?, ?, ?);', (fb_id, fb_token, name, face_encodings_str))
    conn.commit()
    conn.close()


def persist_sighting(servers, time, camera_id, fb_id):
    conn = sqlite3.connect(TIER1_DB)
    c = conn.cursor()
    c.execute('INSERT INTO face_sightings values (?, ?, ?);', (time, camera_id, fb_id))
    conn.commit()
    conn.close()


def broadcast_user(servers, fb_id, fb_token, name, face_encodings_str):
    for server in servers:
        if MY_IP != server:
            try:
                result = requests.post('https://{}/update_user'.format(server),
                                       timeout=TIMEOUT,
                                       verify=False,
                                       json={
                                       'fb_id': fb_id,
                                       'fb_token': fb_token,
                                       'photo_time': photo_time,
                                       'face_encodings_str': face_encodings_str
                                       })
                if result.status_code != 200:
                    print result.json()
            except requests.exceptions.ConnectionError:
                logger.info('Failed to send user to {}'.format(server))


def broadcast_sighting(servers, time, camera_id, fb_id):
    for server in servers:
        if MY_IP != server:
            try:
                result = requests.post('https://{}/update_user'.format(server),
                                       timeout=TIMEOUT,
                                       verify=False,
                                       json={
                                       'time': time,
                                       'camera_id': camera_id,
                                       'fb_id': fb_id,
                                       })
                if result.status_code != 200:
                    print result.json()
            except requests.exceptions.ConnectionError:
                logger.info('Failed to send sighting to {}'.format(server))


def bootup_tier1(counts, servers, backends):
    setup_db_tier1(counts, servers, backends)
    retrieve_startup_info(servers, backends, counts, TIER1_DB)
    notify_new_server(servers)
