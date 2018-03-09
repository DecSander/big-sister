import boto3
import sqlite3
import requests
from PIL import Image
import json
import re
import logging
from flask import jsonify, request
import traceback
from StringIO import StringIO
from functools import wraps
from const import MY_IP, basewidth, TIMEOUT, TIER1_DB, TIER2_DB, SENSOR_DB


logging.basicConfig(filename='utility.log', level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())
logger = logging.getLogger('utility')
s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')


def setup_db_tier1(counts, servers, backends):
    conn = sqlite3.connect(TIER1_DB)
    c = conn.cursor()

    c.execute('CREATE TABLE IF NOT EXISTS camera_counts (camera_id INTEGER UNIQUE, camera_count INTEGER, photo_time REAL);')
    c.execute('CREATE TABLE IF NOT EXISTS server_list (ip_address TEXT UNIQUE);')
    c.execute('CREATE TABLE IF NOT EXISTS backend_list (ip_address TEXT UNIQUE);')
    conn.commit()

    c = conn.cursor()
    c.execute('SELECT camera_id, camera_count, photo_time FROM camera_counts;')
    camera_rows = c.fetchall()
    for row in camera_rows:
        camera_id = row[0]
        camera_count = row[1]
        photo_time = row[2]
        counts[camera_id] = {'camera_count': camera_count, 'photo_time': photo_time}

    c.execute('SELECT ip_address FROM server_list;')
    server_rows = c.fetchall()
    for row in server_rows:
        ip_address = row[0]
        servers.add(ip_address)

    c.execute('SELECT ip_address FROM backend_list;')
    backend_rows = c.fetchall()
    for row in backend_rows:
        ip_address = row[0]
        servers.add(ip_address)

    conn.close()


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


def setup_db_sensor(servers):
    conn = sqlite3.connect(SENSOR_DB)
    c = conn.cursor()

    c.execute('CREATE TABLE IF NOT EXISTS server_list (ip_address TEXT UNIQUE);')
    conn.commit()

    c.execute('SELECT ip_address FROM server_list;')
    server_rows = c.fetchall()
    for row in server_rows:
        ip_address = row[0]
        servers.add(ip_address)

    conn.close()


def temp_store(counts, camera_id, camera_count, photo_time):
    should_update = ('camera_id' not in counts) or (counts['camera_id'] < photo_time)
    if should_update:
        counts[camera_id] = {
            'camera_count': camera_count,
            'photo_time': photo_time
        }
    return should_update


def persist(camera_id, camera_count, photo_time):
    conn = sqlite3.connect(TIER1_DB)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO camera_counts values (?, ?, ?);', (camera_id, camera_count, photo_time))
        conn.commit()
    except sqlite3.IntegrityError:  # Indicates that camera_id is already in the database
        c.execute('UPDATE camera_counts SET camera_count = ?, photo_time = ?;', (camera_count, photo_time))
        conn.commit()
    conn.close()


def is_number(v):
    try:
        float(v)
        return True
    except ValueError:
        return False


def merge_dicts(x, y):
    for k in y:
        if (k not in x) or (k in x and y[k]['photo_time'] > x[k]['photo_time']):
            x[k] = y[k]


def save_server(server, db):
    conn = sqlite3.connect(db)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO server_list values (?)', (server,))
        conn.commit()
    except sqlite3.IntegrityError:  # Indicates we already had this server address
        pass


def save_backend(backend):
    conn = sqlite3.connect(TIER1_DB)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO backend_list values (?)', (backend,))
        conn.commit()
    except sqlite3.IntegrityError:  # Indicates we already had this server address
        pass


def notify_new_server(servers):
    for server in servers:
        try:
            result = requests.post('http://{}:5000/new_server'.format(server), json={'ip_address': MY_IP})
            if result.status_code != 200:
                logger.warning('New server notification for server {} failed: {}'.format(server, result.text))
        except requests.exceptions.ConnectionError:
            logger.info('New server notification for server {} failed: Can\'t connect to server'.format(server))


def notify_new_backend(servers):
    for server in servers:
        try:
            result = requests.post('http://{}:5000/new_backend'.format(server), json={'ip_address': MY_IP})
            if result.status_code != 200:
                logger.warning('New server notification for server {} failed: {}'.format(server, result.text))
        except requests.exceptions.ConnectionError:
            logger.info('New server notification for server {} failed: Can\'t connect to server'.format(server))


def bootup_tier1(counts, servers, backends):
    setup_db_tier1(counts, servers, backends)
    retrieve_startup_info(servers, backends, counts, TIER1_DB)
    notify_new_server(servers)


def bootup_tier2(counts, servers, backends):
    setup_db_tier2(servers)
    retrieve_startup_info(servers, backends, counts, TIER2_DB)
    notify_new_backend(servers)


def bootup_camera(servers):
    retrieve_startup_info(servers, set(), {}, SENSOR_DB)


def retrieve_startup_info(servers, backends, counts, db):
    unvisited_servers = servers.copy()
    visited_servers = set()
    while len(unvisited_servers) > 0:
        server = unvisited_servers.pop()
        visited_servers.add(server)
        if MY_IP != server:
            try:
                result = requests.get('http://{}:5000/servers_backends'.format(server), timeout=TIMEOUT)
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


def send_to_other_servers(servers, camera_id, camera_count, photo_time):
    for server in servers:
        if MY_IP != server:
            try:
                result = requests.post('http://{}:5000/update_camera'.format(server),
                                       timeout=TIMEOUT,
                                       json={
                                       'camera_id': camera_id,
                                       'camera_count': camera_count,
                                       'photo_time': photo_time
                                       })
                if result.status_code != 200:
                    print result.json()
            except requests.exceptions.ConnectionError:
                logger.info('Failed to send count to {}'.format(server))


def resize_image(imagefile):
    imagefile.seek(0)
    image = Image.open(imagefile)
    wpercent = basewidth / float(image.size[0])
    hsize = int(float(image.size[1]) * float(wpercent))
    return image.resize((basewidth, hsize), Image.ANTIALIAS)


def process_image(servers, counts, camera_count, camera_id, photo_time):
    if temp_store(counts, camera_id, camera_count, photo_time):
        persist(camera_id, camera_count, photo_time)
        send_to_other_servers(servers, camera_id, camera_count, photo_time)


def upload_file_to_s3(file, camera_id, photo_time):
    s3_client.upload_fileobj(
        file,
        'cc-proj',
        '{}_{}.jpeg'.format(camera_id, int(photo_time * 1000)),
        ExtraArgs={"ContentType": 'image/jpeg'}
    )


def validate_ip(addr):
    pattern = re.compile('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')
    return pattern.match(addr)


def get_camera_count(imagefile, backends):
    imagefile_contents = imagefile.read()
    for backend in backends:
        try:
            imagefile_str = StringIO(imagefile_contents)
            result = requests.post('http://{}:5001'.format(backend), files={'imagefile': imagefile_str})
            if result.status_code == 200:
                try:
                    return json.loads(result.text)
                except ValueError:  # Received invalid JSON, try next one
                    logger.warning('Failed to retrieve camera count from {}: {}'.format(backend, result.text))
            # Else, we got an error message, try next one
        except requests.exceptions.ConnectionError:
            logger.info('Failed to retrieve camera count from {}: Couldn\'t connect to IP address'.format(backend))


def handle_errors(func):
    @wraps(func)
    def func_wrapper_errors(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            traceback.print_exc()
            return jsonify({'error': 'Server Error'}), 500
    return func_wrapper_errors


def require_json(json_types):
    def real_decorator_json(func):
        @wraps(func)
        def func_wrapper_json(*args, **kwargs):
            json_value = request.get_json()
            if type(json_value) != dict:
                return jsonify({'error': 'JSON Dictionary not supplied'}), 400
            else:
                for arg in json_types:
                    if arg not in json_value:
                        return jsonify({'error': '{} not supplied'.format(arg)}), 400
                    elif json_types[arg] in [float, int, str]:
                        try:
                            kwargs[arg] = json_types[arg](json_value[arg])
                        except ValueError:
                            return jsonify({'error': '{} of type {} could not be cast to type {}'.format(arg, type(json_value[arg]), json_types[arg])}), 400
                    elif type(json_value[arg]) != json_types[arg]:
                        return jsonify({'error': '{} of type {} should be type {}'.format(arg, type(json_value[arg]), json_types[arg])}), 400
                    else:
                        kwargs[arg] = json_value[arg]
                return func(*args, **kwargs)
        return func_wrapper_json
    return real_decorator_json


def require_form(form_types):
    def real_decorator_form(func):
        @wraps(func)
        def func_wrapper_form(*args, **kwargs):
            form_value = request.form
            for arg in form_types:
                if arg not in form_value:
                    return jsonify({'error': '{} not supplied'.format(arg)}), 400
                elif form_types[arg] in [float, int, str]:
                    try:
                        kwargs[arg] = form_types[arg](form_value.get(arg, None))
                    except ValueError:
                        return jsonify({'error': '{} of type {} could not be cast to type {}'.format(arg, type(form_value[arg]), form_types[arg])}), 400
                elif type(form_value.get(arg, None)) != form_types[arg]:
                    return jsonify({'error': '{} of type {} should be type {}'.format(arg, type(form_value[arg]), form_types[arg])}), 400
                else:
                    kwargs[arg] = form_value.get(arg, None)
            return func(*args, **kwargs)
        return func_wrapper_form
    return real_decorator_form


def require_files(file_types):
    def real_decorator_file(func):
        @wraps(func)
        def func_wrapper_file(*args, **kwargs):
            file_value = request.file
            for arg in file_types:
                if arg not in file_value:
                    return jsonify({'error': '{} not supplied'.format(arg)}), 400
                elif file_value.get(arg, None).content_type != file_types[arg]:
                    return jsonify({'error': '{} of type {} should be type {}'.format(arg, file_value[arg].content_type, file_types[arg])}), 400
                else:
                    kwargs[arg] = file_value.get(arg, None)
            return func(*args, **kwargs)
        return func_wrapper_file
    return real_decorator_file


def validate_regex(regex_types):
    def real_decorator_regex(func):
        @wraps(func)
        def func_wrapper_regex(*args, **kwargs):
            for arg in regex_types:
                kwarg = kwargs[arg]
                pattern = re.compile(regex_types[arg])
                if not pattern.match(kwarg):
                    return jsonify({'error': 'Invalid value for argument {}'.format(arg)})
            return func(*args, **kwargs)
        return func_wrapper_regex
    return real_decorator_regex
