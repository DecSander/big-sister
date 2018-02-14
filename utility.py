import boto3
import sqlite3
import requests
import time
import json
from const import servers, MY_IP

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

    for server in servers:
        if MY_IP != server:
            try:
                result = requests.get('http://{}:5000/current_counts'.format(server), timeout=3)
                if result.status_code == 200:
                    counts = merge_dicts(counts, json.loads(result.text))
                else:
                    print result.json()
            except requests.exceptions.ConnectionError:
                print('Failed to retrieve counts from {}'.format(server))


def upload_file_to_s3(file):
    timer = time.time()
    s3_client.upload_fileobj(
        file,
        'cc-proj',
        str(int(timer)) + '.jpeg',
        ExtraArgs={"ContentType": file.content_type}
    )
    return "{}.jpeg".format(int(timer))


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
