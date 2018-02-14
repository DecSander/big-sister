from flask import Flask, request, jsonify
import boto3
import time
from crowd_counter import count_people
import traceback
import os
import requests
import json


app = Flask(__name__)
s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')
MB_TO_BYTES = 1024 * 1024
MAX_MB = 2
MY_IP = os.environ['STATIC_IP'] if 'STATIC_IP' in os.environ else None
servers = ['18.218.132.215', '18.221.18.72']
most_recent_counts = {}


def merge_dicts(x, y):
    z = x.copy()
    z.update(y)
    return z


def bootup():
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
                pass


def upload_file_to_s3(file):
    timer = time.time()
    s3_client.upload_fileobj(
        file,
        'cc-proj',
        str(int(timer)) + '.jpeg',
        ExtraArgs={"ContentType": file.content_type}
    )
    return "{}.jpeg".format(int(timer))


def send_to_other_servers(camera_id, camera_count):
    for server in servers:
        if MY_IP != server:
            try:
                result = requests.post('http://{}:5000/update_camera'.format(server), timeout=3, json={'camera_id': camera_id, 'camera_count': camera_count})
                if result.status_code != 200:
                    print result.json()
            except requests.exceptions.ConnectionError:
                pass


@app.route('/update_camera', methods=['POST'])
def update_camera_value():
    json_values = request.get_json()
    if type(json_values) != dict:
        return jsonify({'error': 'JSON Dictionary not supplied'}), 400
    elif 'camera_id' not in json_values or type(json_values['camera_id']) != int:
        return jsonify({'error': 'No camera id supplied'}), 400
    elif 'camera_count' not in json_values or type(json_values['camera_count']) != int:
        return jsonify({'error': 'No camera count supplied'}), 400
    else:
        most_recent_counts[json_values['camera_id']] = json_values['camera_count']
        return jsonify(True)


@app.route('/all_cameras', methods=['GET'])
def get_all_cameras():
    return jsonify(most_recent_counts)


@app.route('/', methods=['POST'])
def upload_file():
    try:
        imagefile = request.files.get('imagefile', None)
        camera_id = request.form.get('camera_id', None)
        try:
            camera_id = int(camera_id)
        except ValueError:
            return jsonify({'error': 'Camera ID supplied was not a number'})

        if imagefile is None:
            return jsonify({'error': 'Image file was not supplied'}), 400
        elif imagefile.content_type != 'image/jpeg':
            return jsonify({'error': 'Image supplied must be a jpeg, you supplied {}'.format(imagefile.content_type)}), 400
        elif camera_id is None:
            return jsonify({'error': 'Camera ID was not supplied'})
        else:
            imagefile.seek(0, os.SEEK_END)
            size = imagefile.tell()
            imagefile.seek(0)

            if size > MAX_MB * MB_TO_BYTES:
                return jsonify({'error': 'Image supplied was too large, must be less than {} MB'.format(MAX_MB)})
            else:
                # upload_file_to_s3(imagefile)
                camera_count = count_people(imagefile)
                most_recent_counts[camera_id] = camera_count
                send_to_other_servers(camera_id, camera_count)
                return jsonify(camera_count)
    except Exception:
        traceback.print_exc()
        return jsonify({'error': 'Server Error'}), 500


@app.route("/", methods=['GET'])
def pictures():
    bucket_iterator = s3_resource.Bucket('cc-proj').objects.iterator()
    files = [obj.key for obj in bucket_iterator]
    return jsonify(files)


@app.route("/current_counts", methods=['GET'])
def current_data():
    return jsonify(most_recent_counts)


if __name__ == "__main__":
    bootup()
    app.run(host='0.0.0.0')
