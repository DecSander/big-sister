from flask import Flask, request
import json
import boto3
import time


app = Flask(__name__)
s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')


def upload_file_to_s3(file):
    timer = time.time()
    try:
        s3_client.upload_fileobj(
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
        return upload_file_to_s3(imagefile)
    except Exception as err:
        print(err)
        return json.dumps({'error': 'Server Error'}), 500


@app.route("/", methods=['GET'])
def hello():
    return json.dumps(list(map(lambda obj: obj.key, list(s3_resource.Bucket('cc-proj').objects.iterator()))))


if __name__ == "__main__":
    app.run(host='0.0.0.0')
