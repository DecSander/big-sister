from flask import Flask, request, jsonify
import traceback
import os
from utility import resize_image
from crowd_counter import count_people
from const import MAX_MB, MB_TO_BYTES


app = Flask(__name__)


@app.route('/', methods=['POST'])
def upload_file():
    try:
        imagefile = request.files.get('imagefile', None)

        resized = resize_image(imagefile)

        # Check file length
        imagefile.seek(0, os.SEEK_END)
        filesize = imagefile.tell()
        imagefile.seek(0)

        resized = resize_image(imagefile)

        if filesize > MAX_MB * MB_TO_BYTES:
            return jsonify({'error': 'Image supplied was too large, must be less than {} MB'.format(MAX_MB)})

        return jsonify(count_people(resized))

    except Exception:
        traceback.print_exc()
        return jsonify({'error': 'Server Error'}), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)
