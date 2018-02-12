from flask import Flask, request
import json
import boto3
import time
app = Flask(__name__)


most_recent_value = 0

s3 = boto3.client('s3')


def upload_file_to_s3(file):
    timer = time.time()
    try:
        s3.upload_fileobj(
            file,
            'cc-proj',
            str(int(timer)) + '.jpeg',
            ExtraArgs={"ContentType": file.content_type}
        )
        return "{}".format(timer)
    except Exception as e:
        print("Something Happened: ", e)


@app.route('/', methods=['POST'])
def upload_file():
    try:
        imagefile = request.files.get('imagefile', '')
        upload_file_to_s3(imagefile)
        return 'true'
    except Exception as err:
        print(err)


@app.route("/", methods=['POST'])
def store():
    global most_recent_value
    most_recent_value = request.json
    return json.dumps(True)


@app.route("/", methods=['GET'])
def hello():
    global most_recent_value
    return json.dumps(most_recent_value)


if __name__ == "__main__":
    app.run(host='0.0.0.0')
