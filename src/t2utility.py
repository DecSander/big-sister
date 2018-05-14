import sqlite3
import requests
import logging
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
            result = requests.post('https://{}/new_backend'.format(server), json={'ip_address': MY_IP})
            if result.status_code != 200:
                logger.warning('New server notification for server {} failed: {}'.format(server, result.text))
        except requests.exceptions.ConnectionError:
            logger.info('New server notification for server {} failed: Can\'t connect to server'.format(server))


def bootup_tier2(counts, servers, backends):
    setup_db_tier2(servers)
    retrieve_startup_info(servers, backends, counts, TIER2_DB)
    notify_new_backend(servers)
