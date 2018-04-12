from __future__ import division
from flask import Flask, jsonify
from const import servers
import requests
import logging
import json
from decorators import handle_errors, require_form
from threading import Thread
import time

logging.basicConfig(filename='occupancy_predictor.log', level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())
logger = logging.getLogger('occ_pred')

HISTORY_UPDATE_TIME = 60 * 60 * 24  # Daily
app = Flask(__name__)
history = None


@app.route('/')
@require_form({'day': int, 'hour': int})
@handle_errors
def predict_occupancy(day, hour):
    if not history:
        return jsonify({"error": "History is not initialized, cannot infer"}), 400

    prediction = 0
    x = 0.5
    s = 0
    for week in history:
        prediction += week[day][hour] * x
        s += x
        x /= 2

    return jsonify(prediction / s)


def get_history():
    global history
    for server in servers:
        try:
            data = requests.get('http://{}/history'.format(server))
            if data.status_code == 200:
                try:
                    history = json.loads(data.text)
                except ValueError:
                    logger.info("Invalid JSON returned")
            else:
                logger.info(data.text)
        except requests.exceptions.ConnectionError:
            logger.info("server" + str(server) + " could not connect")


def history_loop():
    while True:
        get_history()
        time.sleep(HISTORY_UPDATE_TIME)


if __name__ == "__main__":
    Thread(target=history_loop).start()
    app.run(host='0.0.0.0', port=5002)
