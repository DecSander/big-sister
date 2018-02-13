from flask import Flask, request
import json
import boto3
import time
from crowd_counter import count_people
import traceback


app = Flask(__name__)
s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')


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
        imagefile = request.files.get('imagefile', '')
        return json.dumps(count_people(imagefile))
    except Exception as err:
        traceback.print_exc()
        return json.dumps({'error': 'Server Error'}), 500


@app.route("/", methods=['GET'])
def pictures():
    bucket_iterator = s3_resource.Bucket('cc-proj').objects.iterator()
    files = [obj.key for obj in bucket_iterator]
    return json.dumps(files)


@app.route("/servers", methods=['GET'])
def servers():
    return json.dumps(['18.221.18.72'])


if __name__ == "__main__":
    app.run(host='0.0.0.0')
