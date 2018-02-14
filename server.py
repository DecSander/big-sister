from flask import Flask, request, jsonify
from crowd_counter import count_people
import traceback
import os
from utility import temp_store, persist, is_number, send_to_other_servers, bootup
from const import MAX_MB, MB_TO_BYTES

app = Flask(__name__)
most_recent_counts = {}


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

        if temp_store(most_recent_counts, camera_id, camera_count, photo_time):
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
    bootup(most_recent_counts)
    app.run(host='0.0.0.0')
