from flask import Flask, jsonify, send_from_directory, request
import time
from collections import defaultdict

from t1utility import temp_store, persist, bootup_tier1, get_camera_count, get_prediction, get_counts_at_time
from t1utility import process_image, save_backend, logger, upload_file_to_s3, get_last_data
from t1utility import register_user, persist_user, persist_sighting, broadcast_user, broadcast_sighting, get_faces
from t1utility import send_to_other_servers, get_sightings, get_all_users
from utility import save_server
from decorators import handle_errors, require_json, require_files, require_form, validate_regex
from const import servers, backends, IP_REGEX, occupancy_predictors, face_classifiers


app = Flask(__name__, static_url_path='')
most_recent_counts = {}
most_recent_sightings = defaultdict(dict)


@app.route('/update_camera', methods=['POST'])
@handle_errors
@require_json({'camera_id': int, 'camera_count': int, 'photo_time': float, 'img_id': str})
def update_camera_value(camera_id, camera_count, photo_time, img_id):
    if temp_store(most_recent_counts, camera_id, camera_count, photo_time, img_id):
        send_to_other_servers(servers, camera_id, camera_count, photo_time, img_id)
        persist(camera_id, camera_count, photo_time, img_id)
    return jsonify(True)


@app.route('/update_user', methods=['POST'])
@handle_errors
@require_json({'fb_id': str, 'fb_token': str, 'name': str, 'face_encodings_str': str})
def update_user(fb_id, fb_token, name, face_encodings_str):
    if persist_user(fb_id, fb_token, name, face_encodings_str):
        broadcast_user(servers, face_classifiers, fb_id, fb_token, name, face_encodings_str)
    return jsonify(True)


@app.route('/update_sighting', methods=['POST'])
@handle_errors
@require_json({'time': float, 'camera_id': int, 'fb_id': str, 'sighting_id': str})
def update_sighting(time, camera_id, fb_id, sighting_id):
    if persist_sighting(time, camera_id, fb_id, most_recent_sightings, sighting_id):
        broadcast_sighting(servers, time, camera_id, fb_id, sighting_id)
    return jsonify(True)


@app.route('/', methods=['POST'])
@handle_errors
@require_files({'imagefile': 'image/jpeg'}, optional=True)
@require_form({'camera_id': int, 'photo_time': float})
def upload_file(imagefile, camera_id, photo_time):
    should_update = (camera_id not in most_recent_counts) or (most_recent_counts[camera_id]['photo_time'] < photo_time)
    if not should_update:  # We have more recent data than this for this camera
        logger.info('Received old message')
        return jsonify(False)

    if imagefile is not None:
        camera_count = get_camera_count(imagefile, backends)
        imagefile.seek(0)
        fb_ids = get_faces(imagefile, face_classifiers)
        for fb_id in fb_ids:
            persist_sighting(photo_time, camera_id, fb_id, most_recent_sightings)
            broadcast_sighting(servers, photo_time, camera_id, fb_id)
    else:
        camera_count = most_recent_counts[camera_id]["camera_count"]

    if camera_count is not None:
        process_image(servers, most_recent_counts, camera_count, camera_id, photo_time)
        if imagefile is not None:
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
    if camera_id is not None:
        camera_id = int(camera_id)
    return jsonify(get_last_data(camera_id))


@app.route("/counts", methods=['GET'])
@handle_errors
def current_counts():
    recent_sightings = get_sightings()
    counts_info = dict(most_recent_counts)
    for room in counts_info.keys():
        counts_info[room]['sightings'] = recent_sightings[room] if room in recent_sightings else []
    return jsonify(counts_info)


@app.route("/counts/<room>", methods=['GET'])
@handle_errors
def room_count(room):
    room = int(room)
    if room in most_recent_counts:
        room_info = dict(most_recent_counts[room])
        room_info['sightings'] = get_sightings(room)
        return jsonify(room_info)
    else:
        return jsonify({'error': 'Invalid room'}), 400


@app.route("/counts/<room>/<timestamp>", methods=['GET'])
@handle_errors
def predict_room(room, timestamp):
    room, timestamp = int(room), int(timestamp)
    if room not in most_recent_counts:
        return jsonify({'error': 'Invalid room'}), 400

    if timestamp > time.time():
        pred = get_prediction(room, timestamp, occupancy_predictors)
        if pred is not None:
            return jsonify(pred)
        else:
            return "no data", 204
    else:
        data = get_counts_at_time(timestamp, room)
        if data is not None:
            return jsonify(data[1])
        else:
            return "no data", 204


@app.route('/rooms', methods=['GET'])
@handle_errors
def rooms_list():
    return jsonify(most_recent_counts.keys())


@app.route('/fb_login', methods=['POST'])
@handle_errors
@require_json({'fb_id': str, 'fb_short_token': str})
def fb_login(fb_id, fb_short_token):
    # Check if user already exists instead of always broadcasting?
    user = register_user(face_classifiers, fb_id, fb_short_token)
    broadcast_user(
        servers,
        face_classifiers,
        user['fb_id'],
        user['fb_token'],
        user['name'],
        user['face_encodings_str'])
    return jsonify(user)


@app.route('/users', methods=['GET'])
@handle_errors
def all_users():
    return jsonify(get_all_users())


@app.route('/', methods=['GET'])
@handle_errors
def homepage():
    return send_from_directory('static', 'index.html')


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)


@app.route('/favicon.ico')
def send_favicon():
    return send_from_directory('static', "favicon.ico")


if __name__ == "__main__":
    bootup_tier1(most_recent_counts, servers, backends)
    app.run(host='0.0.0.0', port=443, threaded=True, ssl_context=('/etc/letsencrypt/live/bigsister.info/fullchain.pem', '/etc/letsencrypt/live/bigsister.info/privkey.pem'))
