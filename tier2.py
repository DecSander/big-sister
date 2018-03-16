from flask import Flask, jsonify
import os

from t2utility import resize_image, bootup_tier2
from utility import handle_errors, require_files
from crowd_counter import count_people
from const import MAX_MB, MB_TO_BYTES, servers


app = Flask(__name__)


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
    return jsonify(count_people(resized))


if __name__ == "__main__":
    bootup_tier2({}, servers, [])
    app.run(host='0.0.0.0', port=5001)
