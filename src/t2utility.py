import sqlite3
import requests
import logging
import face_recognition
import numpy as np
from PIL import Image

from const import TIER2_DB, MY_IP, basewidth, FACE_COMPARE_THRESHOLD
from utility import retrieve_startup_info

logging.basicConfig(filename='t2.log', level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())
logger = logging.getLogger('t2')


def setup_db_tier2(servers):
    conn = sqlite3.connect(TIER2_DB)
    c = conn.cursor()

    c.execute('CREATE TABLE IF NOT EXISTS server_list (ip_address TEXT UNIQUE);')
    c.execute('CREATE TABLE IF NOT EXISTS users (fb_id TEXT PRIMARY KEY, fb_token TEXT, name TEXT, face_encodings TEXT)')
    conn.commit()

    c.execute('SELECT ip_address FROM server_list;')
    server_rows = c.fetchall()
    for row in server_rows:
        ip_address = row[0]
        servers.add(ip_address)

    # TODO: Ask other backends for stored users?
    conn.commit()

    conn.close()


def resize_image(imagefile):
    imagefile.seek(0)
    image = Image.open(imagefile)
    wpercent = basewidth / float(image.size[0])
    hsize = int(float(image.size[1]) * float(wpercent))
    return image.resize((basewidth, hsize), Image.ANTIALIAS)


def notify_new_backend(servers):
    for server in servers:
        try:
            result = requests.post('http://{}/new_backend'.format(server), json={'ip_address': MY_IP})
            if result.status_code != 200:
                logger.warning('New server notification for server {} failed: {}'.format(server, result.text))
        except requests.exceptions.ConnectionError:
            logger.info('New server notification for server {} failed: Can\'t connect to server'.format(server))


def bootup_tier2(counts, servers, backends):
    setup_db_tier2(servers)
    retrieve_startup_info(servers, backends, counts, TIER2_DB)
    notify_new_backend(servers)


def persist_user(fb_id, fb_token, name, face_encodings):
    face_encodings_str = repr(map(lambda x: x.tostring(), face_encodings))
    conn = sqlite3.connect(TIER2_DB)
    c = conn.cursor()
    c.execute('INSERT INTO users values (?, ?, ?, ?);', (fb_id, fb_token, name, face_encodings_str))
    conn.commit()
    conn.close()


def compare_all(encoding_str):
    conn = sqlite3.connect(TIER2_DB)
    c = conn.cursor()

    unknown = np.fromstring(encoding)
    closest_distance = 1.0
    closest_row = ''
    for row in c.execute('SELECT * FROM users'):
        known_encodings = parse_face_encodings_str(row[3])
        dists = face_recognition.api.face_distance(known_encodings, unknown)
        min_dist = min(dists)
        if closest_distance > min_dist:
            closest_distance = min_dist
            closest_row = row

    if closest_distance > FACE_COMPARE_THRESHOLD:
        return None  # Can you jsonify(None)?
    user = {
        'fb_id': closest_row[0],
        'fb_token': closest_row[1],
        'name': closest_row[2],
        'face_encodings_str': closest_row[3],
    }
    return user


def parse_face_encodings_str(s):
    l = eval(s)
    encodings = map(np.fromstring, l)
    return encodings


def fb_get_user_name(fb_user_id, fb_token):
    url = 'https://graph.facebook.com/{}'.format(fb_user_id)
    payload = {'access_token': fb_token}
    try:
        result = requests.get(url, params=payload)
        if result.status_code == 200:
            name = result.json()['name']
            return name
        logger.warn('Failed to get user name:' + result.text)
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
        distances = face_recognition.api.face_distance(encodings, prof_photo_encoding)
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
        logger.warn('Failed to get tagged photo ids:' + response.text)
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
        logger.warn('Failed to get image from url:' + result.text)
    except Exception as e:
        print e


def get_face_encodings(img):
    array = np.array(img)
    encodings = face_recognition.face_encodings(array)
    return encodings


def save_user(user):
    raise Exception('TODO')
