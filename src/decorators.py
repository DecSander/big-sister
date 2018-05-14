from flask import jsonify, request
import traceback
from functools import wraps
import re


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
                            return jsonify({'error': '{} ({}) of type {} could not be cast to type {}'.format(arg, kwargs[arg], type(json_value[arg]), json_types[arg])}), 400
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


def require_files(file_types, optional=False):
    def real_decorator_file(func):
        @wraps(func)
        def func_wrapper_file(*args, **kwargs):
            file_value = request.files
            for arg in file_types:
                if arg not in file_value:
                    if not optional:
                        return jsonify({'error': '{} not supplied'.format(arg)}), 400
                    else:
                        kwargs[arg] = None
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
