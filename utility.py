import boto3
import sqlite3
import requests
from PIL import Image
import json
import re
from const import servers, MY_IP, basewidth
from crowd_counter import count_people

s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')


def setup_db(counts):
    conn = sqlite3.connect('counts.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS camera_counts (camera_id INTEGER UNIQUE, camera_count INTEGER, photo_time REAL);')
    conn.commit()

    c = conn.cursor()
    c.execute('SELECT camera_id, camera_count, photo_time FROM camera_counts;')
    rows = c.fetchall()
    for row in rows:
        camera_id = row[0]
        camera_count = row[1]
        photo_time = row[2]
        counts[camera_id] = {'camera_count': camera_count, 'photo_time': photo_time}
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
    conn = sqlite3.connect('counts.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO camera_counts values (?, ?, ?);', (camera_id, camera_count, photo_time))
        conn.commit()
    except sqlite3.IntegrityError:
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


def bootup(counts):
    setup_db(counts)
    get_servers()
    retrieve_counts(counts)


def get_servers(servers):
    server_copy = servers.copy()
    for server in server_copy:
        try:
            result = requests.get('http://{}:5000/servers'.format(server), timeout=3)
            if result.status_code == 200:
                servers.update(set(json.loads(result.text)))
            else:
                print result.text()
                servers.remove(server)
        except requests.exceptions.ConnectionError:
            print('Failed to retrieve server list').format(server)
            servers.remove(server)


def retrieve_counts(counts):
    for server in servers:
        if MY_IP != server:
            try:
                result = requests.get('http://{}:5000/current_counts'.format(server), timeout=3)
                if result.status_code == 200:
                    merge_dicts(counts, json.loads(result.text))
                else:
                    print result.text()
                    servers.remove(server)
            except requests.exceptions.ConnectionError:
                servers.remove(server)
                print('Failed to retrieve counts from {}'.format(server))


def send_to_other_servers(camera_id, camera_count, photo_time):
    for server in servers:
        if MY_IP != server:
            try:
                result = requests.post('http://{}:5000/update_camera'.format(server),
                                       timeout=3,
                                       json={
                                       'camera_id': camera_id,
                                       'camera_count': camera_count,
                                       'photo_time': photo_time
                                       })
                if result.status_code != 200:
                    print result.json()
            except requests.exceptions.ConnectionError:
                print('Failed to send count to {}'.format(server))


def resize_image(imagefile):
    image = Image.open(imagefile)
    wpercent = basewidth / float(image.size[0])
    hsize = int(float(image.size[1]) * float(wpercent))
    return image.resize((basewidth, hsize), Image.ANTIALIAS)


def process_image(counts, resized, camera_id, photo_time):
        camera_count = count_people(resized)

        if temp_store(counts, camera_id, camera_count, photo_time):
            persist(camera_id, camera_count, photo_time)
            send_to_other_servers(camera_id, camera_count, photo_time)


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
