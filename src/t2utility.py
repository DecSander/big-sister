import sqlite3
import requests
import logging
import face_recognition
import numpy as np
from PIL import Image

from const import TIER2_DB, MY_IP, basewidth
from utility import retrieve_startup_info

logging.basicConfig(filename='t2.log', level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())
logger = logging.getLogger('t2')


def setup_db_tier2(servers):
    conn = sqlite3.connect(TIER2_DB)
    c = conn.cursor()

    c.execute('CREATE TABLE IF NOT EXISTS server_list (ip_address TEXT UNIQUE);')
    conn.commit()

    c.execute('SELECT ip_address FROM server_list;')
    server_rows = c.fetchall()
    for row in server_rows:
        ip_address = row[0]
        servers.add(ip_address)

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


def fb_get_user_photos(fb_user_id, fb_token):
    prof_photo_endoding = fb_get_prof_photo_encoding(fb_user_id, fb_token)

    # Filter tagged photos for only the user's face
    raise Exception('TODO')


def fb_get_prof_photo_encoding(fb_user_id, fb_token):
    # Returns PIL.image object instead of id cause for some reason fb doesn't
    # give you a profile pic node and just gives you the url instead
    url = 'https://graph.facebook.com/{}/picture'.format(fb_user_id)
    payload = {'width': 10000}  # arbitrarily large width for largest size
    img = url_to_image(url, payload)
    encoding = get_face_encodings(img)
    return encoding[0]  # Assume only one face in prof pic


def fb_get_tagged_photo_ids(fb_user_id, fb_token, limit=14):
    raise Exception('TODO')


def fb_photo_id_to_encodings(fb_photo_id, fb_token):
    url = "https://graph.facebook.com/{}/picture".format(fb_photo_id)
    payload = None
    payload = {'access_token': fb_token}
    img = url_to_image(url, payload)
    encodings = get_face_encodings(img)
    return encodings


def url_to_image(img_url, payload=None):
    try:
        result = requests.get(img_url, params=payload, stream=True)
        # TODO: Check if response is OK
        img = Image.open(result.raw)
        return img
    except Exception as e:
        print e


def get_face_encodings(img):
    array = np.array(img)
    encodings = face_recognition.face_encodings(array)
    return encodings


def main():
    token = 'EAACEdEose0cBADaoBWxjA4gVpYoBtQiNgqupaItPb7I5ZCwbGPFseE7wyC9ZCvZBfZBkZCVw175cUquZBUosmEYnXw4afr1SPtZABt02GQpk3dBZACRPs0WYTOLZAN3CfMTbrwWbhvDLHxHjhSAiNAulaWcT8rX2hn5coDUW5I1QJoIvihsf1ZAVCdJUY6UcfV89rzeSFFJ2t7VcZBZAZCGQUpnQimw0rpyZBEnbMZD'
    user_id = '926160917410000'
    photo_id = '2377287488963995'
    print len(fb_photo_id_to_encodings(photo_id, token))

if __name__ == '__main__':
    main()
