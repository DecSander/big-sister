from flask import Flask, request, jsonify
import traceback
import os
import threading
from utility import temp_store, persist, is_number, bootup, process_image
from const import MAX_MB, MB_TO_BYTES
from PIL import Image

app = Flask(__name__)
most_recent_counts = {}
basewidth = 1000


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
        filesize = imagefile.tell()
        imagefile.seek(0)
        if filesize > MAX_MB * MB_TO_BYTES:
            return jsonify({'error': 'Image supplied was too large, must be less than {} MB'.format(MAX_MB)})

        resized = Image.open(imagefile)
        wpercent = basewidth / float(resized.size[0])
        hsize = int((float(resized.size[1]) * float(wpercent)))
        resized = resized.resize((basewidth, hsize), Image.ANTIALIAS)

        camera_id = int(camera_id)
        photo_time = float(photo_time)

        t = threading.Thread(target=process_image, args=(most_recent_counts, resized, imagefile, camera_id, photo_time, most_recent_counts))
        t.start()
        return jsonify(True)

    except Exception:
        traceback.print_exc()
        return jsonify({'error': 'Server Error'}), 500


@app.route("/current_counts", methods=['GET'])
def current_data():
    return jsonify(most_recent_counts)


if __name__ == "__main__":
    bootup(most_recent_counts)
    app.run(host='0.0.0.0')
