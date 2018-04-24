from __future__ import division
from bisect import bisect
import logging
import json
from threading import Thread
import time
from flask import Flask, jsonify
import requests

from const import servers
from decorators import handle_errors, require_form

logging.basicConfig(filename='occupancy_predictor.log', level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())
logger = logging.getLogger('occ_pred')


SECONDS_PER_HOUR = 60 * 60
SECONDS_PER_WEEK = SECONDS_PER_HOUR * 24 * 7

HISTORY_UPDATE_TIME = SECONDS_PER_HOUR * 24  # Daily
HISTORY_UPDATE_TIME = 5

app = Flask(__name__)
history = None
NUM_QUERY_WEEKS = 4  # About the last month is probably a good predictor


def mean(l):
    return sum(l) / len(l)


@app.route('/', methods=['POST'])
@require_form({'timestamp': int, 'camera_id': int})
@handle_errors
def predict_occupancy(timestamp, camera_id):
    if not history or camera_id not in history:
        return jsonify({"error": "History is not initialized for this camera, cannot infer"}), 400

    hist_data = history[camera_id]
    prediction = 0
    total_weight = 0
    # Using a weighted prediction algorithm where the first week is worth 4, then 2, then 4/3, then 1, etc.
    # More recent weeks are more relevant, but we don't want the most recent week being an outlier to skew the
    # result to enormously.
    for weeks_past in xrange(1, len(NUM_QUERY_WEEKS)+1):
        datapoints = []
        # Find first datapoints a week and a half hour ago
        time_start = timestamp - weeks_past * SECONDS_PER_WEEK - SECONDS_PER_HOUR/2
        time_end = timestamp - weeks_past * SECONDS_PER_WEEK + SECONDS_PER_HOUR/2
        curr = bisect([x[1] for x in hist_data], time_start)
        # Iterate until an hour after
        while curr < len(hist_data) and hist_data[curr][1] < time_end:
            datapoints.append(hist_data[curr][0])
            curr += 1

        if not datapoints:
            continue

        prediction += mean(datapoints) * (NUM_QUERY_WEEKS / (weeks_past + 1))
        total_weight += (NUM_QUERY_WEEKS / (weeks_past + 1))
    if total_weight == 0:
        # This means we had no data to predict from
        return jsonify(None), 204

    return jsonify(prediction / total_weight)


def get_history():
    print "getting history"
    global history
    for server in servers:
        print "trying: ", server
        try:
            data = requests.get('http://{}/history'.format(server))
            if data.status_code == 200:
                try:
                    hist_db_data = json.loads(data.text)
                    new_hist = {}
                    for c_id, count, timestamp in hist_db_data:
                        if c_id not in new_hist:
                            new_hist[c_id] = [(count, timestamp)]
                        else:
                            new_hist[c_id].append((count, timestamp))

                    history = {k:sorted(v, key=v[1]) for k, v in new_hist.iteritems()}
                    print history
                except ValueError:
                    logger.info("Invalid JSON returned")
            else:
                logger.info(data.text)
        except requests.exceptions.ConnectionError:
            logger.info("server " + str(server) + " could not connect")


def history_loop():
    while True:
        get_history()
        time.sleep(HISTORY_UPDATE_TIME)


if __name__ == "__main__":
    Thread(target=history_loop).start()
    app.run(host='0.0.0.0', port=5002)
