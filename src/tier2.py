from flask import Flask, jsonify
import os

from sklearn.linear_model import LinearRegression
import pickle
import numpy as np

from t2utility import resize_image, bootup_tier2, persist_user, compare_all
from t2utility import fb_get_user_name, fb_get_user_photos_encodings
from decorators import handle_errors, require_files, require_json
from crowd_counter import count_people
from const import MAX_MB, MB_TO_BYTES, servers

DATA_DIR = "../data/images/labelled/"

app = Flask(__name__)

regression_model = None


@app.route('/', methods=['POST'])
@handle_errors
@require_files({'imagefile': 'image/jpeg'})
def upload_file(imagefile):
    # Check file length
    imagefile.seek(0, os.SEEK_END)
    filesize = imagefile.tell()
    imagefile.seek(0)

    if filesize > MAX_MB * MB_TO_BYTES:
        return jsonify({'error': 'Image supplied was too large, must be less than {} MB'.format(MAX_MB)})

    resized = resize_image(imagefile)
    model_count = count_people(resized)
    prediction = model_count
    # prediction = int(regression_model.predict(model_count)[0][0])
    return jsonify(prediction)


@app.route('/new_user', methods=['POST'])
@handle_errors
@require_json({'fb_id': str, 'fb_long_token': str})
def create_user(fb_id, fb_long_token):
    name = fb_get_user_name(fb_id, fb_long_token)
    face_encodings = fb_get_user_photos_encodings(fb_id, fb_long_token)
    face_encodings_str = repr(map(lambda x: x.tostring(), face_encodings))
    user = {
        'fb_id': fb_id,
        'fb_long_token': fb_long_token,
        'name': name,
        'face_encodings_str': face_encodings_str
    }
    persist_user(fb_id, fb_long_token, name, face_encodings)
    return jsonify(user)


@app.route('/identify_face', methods=['POST'])
@handle_errors
@require_files({'imagefile': 'image/jpeg'})
def identify_face(imagefile):
    user = compare_all(imagefile)
    print user
    return jsonify(user)


def create_model():
    if os.path.exists("regression_model.pkl"):
        with open("regression_model.pkl", 'r') as f:
            model = pickle.loads(f.read())
            print model.predict(100)
            return model

    files = os.listdir(DATA_DIR)

    predicted, expected = zip(*[map(float, f.split("-")[:2]) for f in files])
    predicted = np.array(predicted).reshape(len(predicted), 1)
    expected = np.array(predicted).reshape(len(expected), 1)

    model = LinearRegression()
    model.fit(predicted, expected)

    with open("regression_model.pkl", 'w') as f:
        f.write(pickle.dumps(model))
    print model.predict(500)
    return model


if __name__ == "__main__":
    regression_model = create_model()
    bootup_tier2({}, servers, set())
    app.run(host='0.0.0.0', port=5001)
