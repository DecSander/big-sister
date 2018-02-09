from flask import Flask, request
import json
app = Flask(__name__)


most_recent_value = 0


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
    app.run()
