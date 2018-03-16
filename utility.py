import sqlite3
import requests
import logging
import json
import re
from flask import jsonify, request
import traceback
from functools import wraps

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
            file_value = request.files
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
