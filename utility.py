import boto3
import sqlite3
import requests
from PIL import Image
import json
import re
import logging
from const import MY_IP, basewidth, TIMEOUT, DB_NAME


logging.basicConfig(filename='server.log', level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())
logger = logging.getLogger('servers')
s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')


def setup_db(counts, servers, backends):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute('CREATE TABLE IF NOT EXISTS camera_counts (camera_id INTEGER UNIQUE, camera_count INTEGER, photo_time REAL);')
    c.execute('CREATE TABLE IF NOT EXISTS server_list (ip_address TEXT UNIQUE);')
    c.execute('CREATE TABLE IF NOT EXISTS backend_list (ip_address TEXT UNIQUE);')
    conn.commit()

    c = conn.cursor()
    c.execute('SELECT camera_id, camera_count, photo_time FROM camera_counts;')
    camera_rows = c.fetchall()
    for row in camera_rows:
        camera_id = row[0]
        camera_count = row[1]
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


def temp_store(counts, camera_id, camera_count, photo_time):
    should_update = ('camera_id' not in counts) or (counts['camera_id'] < photo_time)
    if should_update:
        counts[camera_id] = {
            'camera_count': camera_count,
            'photo_time': photo_time
        }
    return should_update


def persist(camera_id, camera_count, photo_time):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO camera_counts values (?, ?, ?);', (camera_id, camera_count, photo_time))
        conn.commit()
    except sqlite3.IntegrityError:  # Indicates that camera_id is already in the database
        c.execute('UPDATE camera_counts SET camera_count = ?, photo_time = ?;', (camera_count, photo_time))
        conn.commit()
    conn.close()


def is_number(v):
    try:
        float(v)
        return True
    except ValueError:
        return False


def merge_dicts(x, y):
    for k in y:
        if (k not in x) or (k in x and y[k]['photo_time'] > x[k]['photo_time']):
            x[k] = y[k]


def save_server(server):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO server_list values (?)', (server,))
        conn.commit()
    except sqlite3.IntegrityError:  # Indicates we already had this server address
        pass


def save_backend(backend):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO backend_list values (?)', (backend,))
        conn.commit()
    except sqlite3.IntegrityError:  # Indicates we already had this server address
        pass


def bootup(counts, servers, backends):
    setup_db(counts, servers, backends)
    retrieve_startup_info(servers, backends, counts)


def retrieve_startup_info(servers, backends, counts):
    unvisited_servers = servers.copy()
    visited_servers = set()
    while len(unvisited_servers) > 0:
        server = unvisited_servers.pop()
        visited_servers.add(server)
        if MY_IP != server:
            try:
                result = requests.get('http://{}:5000/servers_backends'.format(server), timeout=TIMEOUT)
                if result.status_code == 200:
                    startup_info = json.loads(result.text)
                    servers.update(set(startup_info['servers']))
                    backends.update(set(startup_info['backends']))
                    merge_dicts(counts, startup_info['counts'])

                    for new_server in startup_info['servers']:
                        save_server(new_server)
                        if new_server not in visited_servers:
                            unvisited_servers.add(new_server)
                else:
                    logger.warning('Failed to retrieve startup info from {}: {}'.format(server, result.text()))
            except requests.exceptions.ConnectionError:
                logger.info('Failed to retrieve startup info from {}: Couldn\'t connect to IP address'.format(server))


def send_to_other_servers(servers, camera_id, camera_count, photo_time):
    for server in servers:
        if MY_IP != server:
            try:
                result = requests.post('http://{}:5000/update_camera'.format(server),
                                       timeout=TIMEOUT,
                                       json={
                                       'camera_id': camera_id,
                                       'camera_count': camera_count,
                                       'photo_time': photo_time
                                       })
                if result.status_code != 200:
                    print result.json()
            except requests.exceptions.ConnectionError:
                logger.info('Failed to send count to {}'.format(server))


def resize_image(imagefile):
    imagefile.seek(0)
    image = Image.open(imagefile)
    wpercent = basewidth / float(image.size[0])
    hsize = int(float(image.size[1]) * float(wpercent))
    return image.resize((basewidth, hsize), Image.ANTIALIAS)


def process_image(servers, counts, camera_count, camera_id, photo_time):
    if temp_store(counts, camera_id, camera_count, photo_time):
        persist(camera_id, camera_count, photo_time)
        send_to_other_servers(servers, camera_id, camera_count, photo_time)


def upload_file_to_s3(file, camera_id, photo_time):
    s3_client.upload_fileobj(
        file,
        'cc-proj',
        '{}_{}.jpeg'.format(camera_id, int(photo_time * 1000)),
        ExtraArgs={"ContentType": 'image/jpeg'}
    )


def validate_ip(addr):
    pattern = re.compile('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')
    return pattern.match(addr)


def get_camera_count(imagefile, backends):
    for backend in backends:
        try:
            result = requests.post('http://{}:5001'.format(backend), files={'imagefile': imagefile})
            if result.status_code == 200:
                try:
                    return json.loads(result.text)
                except ValueError:  # Received invalid JSON, try next one
                    pass
            # Else, we got an error message, try next one
        except requests.exceptions.ConnectionError:
            pass  # This backend is down, trying next one
