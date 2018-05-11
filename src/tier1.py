from flask import Flask, jsonify, send_from_directory, request
from flask_sslify import SSLify
from t1utility import temp_store, persist, bootup_tier1, get_camera_count, get_prediction
from t1utility import process_image, save_backend, logger, upload_file_to_s3, get_last_data
from utility import save_server
from decorators import handle_errors, require_json, require_files, require_form, validate_regex
from const import servers, backends, IP_REGEX, occupancy_predictors


app = Flask(__name__, static_url_path='')
sslify = SSLify(app)
most_recent_counts = {}


@app.route('/update_camera', methods=['POST'])
@handle_errors
@require_json({'camera_id': int, 'camera_count': int, 'photo_time': float, 'img_id': int})
def update_camera_value(camera_id, camera_count, photo_time, img_id):
    if temp_store(most_recent_counts, camera_id, camera_count, photo_time):
        persist(camera_id, camera_count, photo_time, img_id)
    return jsonify(True)


@app.route('/', methods=['POST'])
@handle_errors
@require_files({'imagefile': 'image/jpeg'})
@require_form({'camera_id': int, 'photo_time': float})
def upload_file(imagefile, camera_id, photo_time):
    should_update = (camera_id not in most_recent_counts) or (most_recent_counts[camera_id]['photo_time'] < photo_time)
    if not should_update:  # We have more recent data than this for this camera
        logger.info('Received old message')
        return jsonify(False)

    camera_count = get_camera_count(imagefile, backends)

    if camera_count is not None:
        process_image(servers, most_recent_counts, camera_count, camera_id, photo_time)
        upload_file_to_s3(imagefile, camera_id, photo_time, camera_count)
    return jsonify(camera_count)


@app.route("/new_server", methods=['POST'])
@handle_errors
@require_json({'ip_address': str})
@validate_regex({'ip_address': IP_REGEX})
def new_server(ip_address):
    servers.add(ip_address)
    save_server(ip_address)
    return jsonify(True)


@app.route("/new_backend", methods=['POST'])
@handle_errors
@require_json({'ip_address': str})
@validate_regex({'ip_address': IP_REGEX})
def new_backend(ip_address):
    backends.add(ip_address)
    save_backend(ip_address)
    return jsonify(True)


@app.route("/servers_backends", methods=['GET'])
@handle_errors
def server_list():
    return jsonify({
        'servers': list(servers),
        'backends': list(backends),
        'counts': most_recent_counts
    })


@app.route("/history", methods=['GET'])
@handle_errors
def history():
    camera_id = request.args.get('camera_id', None)
    return jsonify(get_last_data(camera_id))


@app.route("/counts", methods=['GET'])
@handle_errors
def current_counts():
    return jsonify(most_recent_counts)


@app.route("/counts/<room>", methods=['GET'])
@handle_errors
def room_count(room):
    if room in most_recent_counts:
        return jsonify(most_recent_counts[room])
    else:
        return jsonify({'error': 'Invalid room'}), 400


@app.route("/counts/<room>/<timestamp>", methods=['GET'])
@handle_errors
def predict_room(room, timestamp):
    if room in most_recent_counts:
        return jsonify(get_prediction(room, timestamp, occupancy_predictors))
    else:
        return jsonify({'error': 'Invalid room'}), 400


@app.route('/rooms', methods=['GET'])
@handle_errors
def rooms_list():
    return jsonify(most_recent_counts.keys())


@app.route('/', methods=['GET'])
@handle_errors
def homepage():
    return send_from_directory('static', 'index.html')


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)


if __name__ == "__main__":
    bootup_tier1(most_recent_counts, servers, backends)
    app.run(host='0.0.0.0', port=80, threaded=True, ssl_context=('../key.crt', '../key.key'))
