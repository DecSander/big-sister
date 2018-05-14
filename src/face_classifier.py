import face_recognition as fr
import logging
import numpy as np
import requests
import sqlite3
from flask import Flask, jsonify
from PIL import Image

from const import FB_APP_ID, FB_APP_SECRET, FACE_COMPARE_THRESHOLD, FC_DB, servers
from decorators import handle_errors, require_files, require_form, require_json


logging.basicConfig(filename='fc.log', level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())
logger = logging.getLogger('fc')

app = Flask(__name__)


def startup():
    conn = sqlite3.connect(FC_DB)
    c = conn.cursor()

    c.execute('CREATE TABLE IF NOT EXISTS users (fb_id TEXT PRIMARY KEY, fb_token TEXT, name TEXT, face_encodings TEXT)')
    conn.commit()

    for server in servers:
        url = 'https://{}/users'.format(server)
        try:
            result = requests.get(url)
            if result.status_code == 200:
                users = result.json()
                for user in users:
                    persist_user(user['fb_id'], user['fb_token'], user['name'], user['face_encodings_str'])
                return
            logger.warning('Got non-200 response from {}'.format(server))
            logger.warning(result.text)
        except Exception as e:
            logger.warning('Failed to get users from server {}'.format(server))
            logger.warning(e)

    conn.close()


@app.route('/update_user', methods=['POST'])
@handle_errors
@require_json({'fb_id': str, 'fb_token': str, 'name': str, 'face_encodings_str': str})
def update_user(fb_id, fb_token, name, face_encodings_str):
    persist_user(fb_id, fb_token, name, face_encodings_str)
    return jsonify(True)


@app.route('/', methods=['POST'])
@handle_errors
@require_files({'imagefile': 'image/jpeg'})
def classify_faces(imagefile):
    imagefile.seek(0)
    img = Image.open(imagefile)
    encodings = get_face_encodings(img)
    users = map(compare_all_faces, encodings)
    users = [x['fb_id'] for x in users if x is not None]
    return jsonify(users)


def compare_all_faces(encoding):
    conn = sqlite3.connect(FC_DB)
    c = conn.cursor()

    closest_distance = 1.0
    closest_row = ''
    for row in c.execute('SELECT * FROM users'):
        known_encodings = parse_face_encodings_str(row[3])
        dists = fr.api.face_distance(known_encodings, encoding)
        min_dist = min(dists)
        if closest_distance > min_dist:
            closest_distance = min_dist
            closest_row = row

    if closest_distance > FACE_COMPARE_THRESHOLD:
        return None  # TODO: Can you jsonify(None)?
    user = {
        'fb_id': closest_row[0],
        'fb_token': closest_row[1],
        'name': closest_row[2],
        'face_encodings_str': closest_row[3],
    }
    return user


def parse_face_encodings_str(s):
    encodings_strs = eval(s)
    encodings = map(np.fromstring, encodings_strs)
    return encodings


@app.route('/new', methods=['POST'])
@handle_errors
@require_json({'fb_id': str, 'fb_short_token': str})
def new_user(fb_id, fb_short_token):
    conn = sqlite3.connect(FC_DB)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE fb_id = ?", (fb_id,))
    row = c.fetchone()
    if row is not None:
        user = {
            'fb_id': row[0],
            'fb_token': row[1],
            'name': row[2],
            'face_encodings_str': row[3]
        }
        return jsonify(user)

    # TODO: REMOVE THIS
    fb_long_token = fb_short_token
    # fb_long_token = fb_get_long_lived_token(fb_short_token)
    name = fb_get_user_name(fb_id, fb_long_token)
    face_encodings = fb_get_user_photos_encodings(fb_id, fb_long_token)
    face_encodings_str = repr(map(lambda x: x.tostring(), face_encodings))
    user = {
        'fb_id': fb_id,
        'fb_token': fb_long_token,
        'name': name,
        'face_encodings_str': face_encodings_str
    }
    persist_user(fb_id, fb_long_token, name, face_encodings_str)
    return jsonify(user)


def fb_get_long_lived_token(fb_short_token):
    url = 'https://graph.facebook.com/oauth/access_token'
    payload = {
        'grant_type': 'fb_exchange_token',
        'client_id': FB_APP_ID,
        'client_secret': FB_APP_SECRET,
        'fb_exchange_token': fb_short_token,
    }
    try:
        result = requests.get(url, params=payload)
        if result.status_code != 200:
            print result.json()
        return result.json()['access_token']
    except Exception as e:
        print e


def fb_get_user_name(fb_user_id, fb_token):
    url = 'https://graph.facebook.com/{}'.format(fb_user_id)
    payload = {'access_token': fb_token}
    try:
        result = requests.get(url, params=payload)
        if result.status_code == 200:
            name = result.json()['name']
            return name
        logger.warning('Failed to get user name:' + result.text)
    except Exception as e:
        print e


def fb_get_user_photos_encodings(fb_user_id, fb_token):
    prof_photo_encoding = fb_get_prof_photo_encoding(fb_user_id, fb_token)
    tagged_photos_ids = fb_get_tagged_photo_ids(fb_user_id, fb_token)

    # Filter tagged photos for only the user's face
    user_face_encodings = [prof_photo_encoding]
    for i in tagged_photos_ids:
        encodings = fb_photo_id_to_encodings(i, fb_token)
        if len(encodings) == 0:
            continue
        distances = fr.api.face_distance(encodings, prof_photo_encoding)
        user_face_encodings.append(encodings[np.argmax(distances)])
    return user_face_encodings


def fb_get_prof_photo_encoding(fb_user_id, fb_token):
    url = 'https://graph.facebook.com/{}/picture'.format(fb_user_id)
    payload = {'width': 10000}  # arbitrarily large width for largest size
    img = url_to_image(url, payload)
    encoding = get_face_encodings(img)
    return encoding[0]  # Assume only one face in prof pic


def fb_get_tagged_photo_ids(fb_user_id, fb_token, limit=14):
    url = 'https://graph.facebook.com/{}/photos'.format(fb_user_id)
    payload = {'access_token': fb_token, 'fields': 'id'}
    try:
        result = requests.get(url, params=payload)
        if result.status_code == 200:
            data = result.json()['data']
            ids = map(lambda x: x['id'], data)
            return ids
        logger.warning('Failed to get tagged photo ids:' + result.text)
    except Exception as e:
        print e


def fb_photo_id_to_encodings(fb_photo_id, fb_token):
    url = 'https://graph.facebook.com/{}/picture'.format(fb_photo_id)
    payload = {'access_token': fb_token}
    img = url_to_image(url, payload)
    encodings = get_face_encodings(img)
    return encodings


def url_to_image(url, payload=None):
    try:
        result = requests.get(url, params=payload, stream=True)
        if result.status_code == 200:
            img = Image.open(result.raw)
            return img
        logger.warning('Failed to get image from url:' + result.text)
    except Exception as e:
        print e


def get_face_encodings(img):
    array = np.array(img)
    encodings = fr.face_encodings(array)
    return encodings


def persist_user(fb_id, fb_token, name, face_encodings_str):
    conn = sqlite3.connect(FC_DB)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users values (?, ?, ?, ?);', (fb_id, fb_token, name, face_encodings_str))
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        pass


def main():
    startup()
    app.run(host='0.0.0.0', port=5003)


if __name__ == '__main__':
    main()
