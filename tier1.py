from flask import Flask, request, jsonify
import traceback
import logging
from utility import temp_store, persist, is_number, bootup, get_camera_count
from utility import process_image, validate_ip, save_server, save_backend
from const import servers, backends


logging.basicConfig(filename='server.log', level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())
app = Flask(__name__)
most_recent_counts = {}


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
        camera_id = json_values['camera_id']
        camera_count = json_values['camera_count']
        photo_time = json_values['photo_time']

        if temp_store(most_recent_counts, camera_id, camera_count, photo_time):
            persist(camera_id, camera_count, photo_time)
        return jsonify(True)


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
            return jsonify({'error': 'Camera ID was not supplied'}), 400
        elif photo_time is None or not is_number(photo_time):
            return jsonify({'error': 'Photo time was not supplied'}), 400

        camera_id = int(camera_id)
        photo_time = float(photo_time)

        should_update = (camera_id not in most_recent_counts) or (most_recent_counts[camera_id] < photo_time)
        if not should_update:  # We have more recent data than this for this camera
            logger.info('Received old message')
            return jsonify(False)

        camera_count = get_camera_count(imagefile, backends)
        valid_camera_count = camera_count is not None

        if valid_camera_count:
            process_image(servers, most_recent_counts, camera_count, camera_id, photo_time)
            # upload_file_to_s3(imagefile, camera_id, photo_time)
        return jsonify(valid_camera_count)

    except Exception:
        traceback.print_exc()
        return jsonify({'error': 'Server Error'}), 500


@app.route("/new_server", methods=['POST'])
def new_server():
    req_json = request.json()
    if 'ip_address' not in req_json:
        return jsonify({'error': 'IP Address not included'}), 400
    elif validate_ip(req_json['ip_address']):
        return jsonify({'error': 'Invalid IP Address'})
    new_ip_address = req_json['ip_address']
    servers.add(new_ip_address)
    save_server(new_ip_address)
    return jsonify(True)


@app.route("/new_backend", methods=['POST'])
def new_backend():
    req_json = request.json()
    if 'ip_address' not in req_json:
        return jsonify({'error': 'IP Address not included'}), 400
    elif validate_ip(req_json['ip_address']):
        return jsonify({'error': 'Invalid IP Address'})
    new_ip_address = req_json['ip_address']
    backends.add(new_ip_address)
    save_backend(new_ip_address)
    return jsonify(True)


@app.route("/servers_backends", methods=['GET'])
def server_list():
    return jsonify({'servers': list(servers), 'backends': list(backends), 'counts': most_recent_counts})


@app.route("/", methods=['GET'])
def current_counts():
    return jsonify(most_recent_counts)


if __name__ == "__main__":
    bootup(most_recent_counts, servers, backends)
    app.run(host='0.0.0.0', port=5000, threaded=True)