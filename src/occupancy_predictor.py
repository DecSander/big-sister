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

HISTORY_UPDATE_TIME = 60*60*24 # Daily

app = Flask(__name__)

history = None
NUM_QUERY_WEEKS = 4 # About the last month is probably a good predictor

def mean(l):
    return sum(l)/len(l)

@app.route('/')
@require_form({'day': int, 'hour': int, 'camera_id': int})
@handle_errors
def predict_occupancy(day, hour, camera_id):
    if not history:
        return jsonify({"error" : "History is not initialized, cannot infer"}), 400

    prediction = 0
    total_weight = 0
    # Using a weighted prediction algorithm where the first week is worth 4, then 2, then 4/3, then 1, etc.
    # More recent weeks are more relevant, but we don't want the most recent week being an outlier to skew the
    # result to enormously.
    for i, week in enumerate(history[camera_id][:NUM_QUERY_WEEKS]):
        if day in week and hour in week[day]:
            prediction += mean(week[day][hour]) * (NUM_QUERY_WEEKS/(i+1))
            total_weight += (NUM_QUERY_WEEKS/(i+1))

    if total_weight == 0:
        # This means we had no data to predict from
        return jsonify(None), 204

    return jsonify(prediction/total_weight)


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
