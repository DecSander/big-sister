import sqlite3
import requests
import logging
import json
import re

from const import MY_IP, TIMEOUT

logging.basicConfig(filename='utility.log', level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())
logger = logging.getLogger('utility')


def is_number(v):
    try:
        float(v)
        return True
    except ValueError:
        return False

def merge_dicts(orig, y):
    for k in y:
        if (int(k) not in orig) or (int(k) in orig and y[k]['photo_time'] > orig[int(k)]['photo_time']):
            orig[int(k)] = y[k]


def save_server(server, db):
    conn = sqlite3.connect(db)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO server_list values (?)', (server,))
        conn.commit()
    except sqlite3.IntegrityError:  # Indicates we already had this server address
        pass


def retrieve_startup_info(servers, backends, counts, db):
    unvisited_servers = servers.copy()
    visited_servers = set()
    while len(unvisited_servers) > 0:
        server = unvisited_servers.pop()
        visited_servers.add(server)
        if MY_IP != server:
            try:
                result = requests.get('http://{}/servers_backends'.format(server), timeout=TIMEOUT)
                if result.status_code == 200:
                    startup_info = json.loads(result.text)
                    servers.update(set(startup_info['servers']))
                    backends.update(set(startup_info['backends']))
                    merge_dicts(counts, startup_info['counts'])

                    for new_server in startup_info['servers']:
                        save_server(new_server, db)
                        if new_server not in visited_servers:
                            unvisited_servers.add(new_server)
                else:
                    logger.warning('Failed to retrieve startup info from {}: {}'.format(server, result.text))
            except requests.exceptions.ConnectionError:
                logger.info('Failed to retrieve startup info from {}: Couldn\'t connect to IP address'.format(server))


def validate_ip(addr):
    pattern = re.compile('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')
    return pattern.match(addr)
