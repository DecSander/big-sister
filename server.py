from flask import Flask, request, jsonify
import boto3
import time
from crowd_counter import count_people
import traceback
import os
import requests
import json
import sqlite3


app = Flask(__name__)
s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')
MB_TO_BYTES = 1024 * 1024
MAX_MB = 2
MY_IP = os.environ['STATIC_IP'] if 'STATIC_IP' in os.environ else None
servers = ['18.218.132.215', '18.221.18.72']
most_recent_counts = {}


def setup_db():
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
        most_recent_counts[camera_id] = {'camera_count': camera_count, 'photo_time': photo_time}
    conn.close()


def temp_store(camera_id, camera_count, photo_time):
    should_update = ('camera_id' not in most_recent_counts) or (most_recent_counts['camera_id'] < photo_time)
    if should_update:
        most_recent_counts[camera_id] = {
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


def bootup():
    setup_db()

    for server in servers:
        if MY_IP != server:
            try:
                result = requests.get('http://{}:5000/current_counts'.format(server), timeout=3)
                if result.status_code == 200:
                    global most_recent_counts
                    most_recent_counts = merge_dicts(most_recent_counts, json.loads(result.text))
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


@app.route('/update_camera', methods=['POST'])
def update_camera_value():
    json_values = request.get_json()
    if type(json_values) != dict:
        return jsonify({'error': 'JSON Dictionary not supplied'}), 400
    elif 'camera_id' not in json_values or type(json_values['camera_id']) != int:
        return jsonify({'error': 'No camera id supplied'}), 400
    elif 'camera_count' not in json_values or type(json_values['camera_count']) != float:
        return jsonify({'error': 'No camera count supplied'}), 400
    else:
        camera_id = json_values['camera_id']
        camera_count = json_values['camera_count']
        photo_time = json_values['photo_time']

        if temp_store(camera_id, camera_count, photo_time):
            persist(camera_id, camera_count, photo_time)
        return jsonify(True)


@app.route('/all_cameras', methods=['GET'])
def get_all_cameras():
    return jsonify(most_recent_counts)


@app.route('/', methods=['POST'])
def upload_file():
    try:
        imagefile = request.files.get('imagefile', None)
        camera_id = request.form.get('camera_id', None)
        photo_time = request.form.get('photo_time', None)

        if imagefile is None:
            return jsonify({'error': 'Image file was not supplied'}), 400
        elif imagefile.content_type != 'image/jpeg':
            content_type = imagefile.content_type
            return jsonify({'error': 'Image supplied must be a jpeg, you supplied {}'.format(content_type)}), 400
        elif camera_id is None or not is_number(camera_id):
            return jsonify({'error': 'Camera ID was not supplied'})
        elif photo_time is None or not is_number(photo_time):
            return jsonify({'error': 'Photo time was not supplied'})

        # Check file length
        imagefile.seek(0, os.SEEK_END)
        size = imagefile.tell()
        imagefile.seek(0)
        if size > MAX_MB * MB_TO_BYTES:
            return jsonify({'error': 'Image supplied was too large, must be less than {} MB'.format(MAX_MB)})

        # upload_file_to_s3(imagefile)
        camera_id = int(camera_id)
        photo_time = float(photo_time)
        camera_count = count_people(imagefile)

        if temp_store(camera_id, camera_count, photo_time):
            persist(camera_id, camera_count, photo_time)
            send_to_other_servers(camera_id, camera_count, photo_time)
        return jsonify(camera_count)

    except Exception:
        traceback.print_exc()
        return jsonify({'error': 'Server Error'}), 500


@app.route("/current_counts", methods=['GET'])
def current_data():
    return jsonify(most_recent_counts)


if __name__ == "__main__":
    bootup()
    app.run(host='0.0.0.0')
