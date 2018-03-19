from flask import Flask, jsonify
import os

from sklearn.linear_model import LinearRegression
import pickle
import numpy as np

from t2utility import resize_image, bootup_tier2
from decorators import handle_errors, require_files
from crowd_counter import count_people
from const import MAX_MB, MB_TO_BYTES, servers



app = Flask(__name__)

regression_model = None

@app.route('/', methods=['POST'])
@handle_errors
@require_files({'imagefile', 'image/jpeg'})
def upload_file(imagefile):
    # Check file length
    imagefile.seek(0, os.SEEK_END)
    filesize = imagefile.tell()
    imagefile.seek(0)

    if filesize > MAX_MB * MB_TO_BYTES:
        return jsonify({'error': 'Image supplied was too large, must be less than {} MB'.format(MAX_MB)})

    resized = resize_image(imagefile)
    model_count = count_people(resized)
    prediction = regression_model.predict(model_count)[0][0]
    return jsonify(prediction)

def create_model():
    if os.path.exists("regression_model.pkl"):
        with open("regression_model.pkl", 'r') as f:
            return pickle.loads(f.read())

    data = np.array([1, 2, 3, 4]).reshape((4, 1))
    expected = np.array([1, 2, 3, 4]).reshape((4, 1))
    model = LinearRegression()
    model.fit(data, expected)

    with open("regression_model.pkl", 'w') as f:
        f.write(pickle.dumps(model))
    return model



if __name__ == "__main__":
    regression_model = create_model()
    bootup_tier2({}, servers, set())
    app.run(host='0.0.0.0', port=5001)
