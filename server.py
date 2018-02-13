from flask import Flask, request
import json
import boto3
import time
from crowd_counter import count_people
import traceback
import os


app = Flask(__name__)
s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')
MB_TO_BYTES = 1024 * 1024
MAX_MB = 2


def upload_file_to_s3(file):
    timer = time.time()
    s3_client.upload_fileobj(
        file,
        'cc-proj',
        str(int(timer)) + '.jpeg',
        ExtraArgs={"ContentType": file.content_type}
    )
    return "{}".format(timer)


@app.route('/', methods=['POST'])
def upload_file():
    try:
        imagefile = request.files.get('imagefile', None)
        if imagefile is None:
            return json.dumps({'error': 'Image file was not supplied'}), 400
        elif imagefile.content_type != 'image/jpeg':
            return json.dumps({'error': 'Image supplied must be a jpeg, you supplied {}'.format(imagefile.content_type)}), 400
        else:
            imagefile.seek(0, os.SEEK_END)
            size = imagefile.tell()
            imagefile.seek(0)

            if size > MAX_MB * MB_TO_BYTES:
                return json.dumps({'error': 'Image supplied was too large, must be less than {} MB'.format(MAX_MB)})
            else:
                # upload_file_to_s3(imagefile)
                return json.dumps(count_people(imagefile))
    except Exception:
        traceback.print_exc()
        return json.dumps({'error': 'Server Error'}), 500


@app.route("/", methods=['GET'])
def pictures():
    bucket_iterator = s3_resource.Bucket('cc-proj').objects.iterator()
    files = [obj.key for obj in bucket_iterator]
    return json.dumps(files)


@app.route("/servers", methods=['GET'])
def servers():
    return json.dumps([])


if __name__ == "__main__":
    app.run(host='0.0.0.0')
