#!/usr/bin/env python2

import json
import requests
import time
import os

from picamera import PiCamera


SERVER_URL = 'http://18.221.18.72:5000'
server_urls = []

camera_id = 1

camera = PiCamera()
camera.resolution = (1024, 768)
camera.start_preview()

time.sleep(2)  # Camera warm-up time


def take_picture(file="foo.jpg"):
    camera.capture(file)


def send_image(f):
    files = {'imagefile': (f, open(os.path.basename(f), 'rb'), 'image/jpeg')}
    requests.post(SERVER_URL, files=files, data={"camera_id": camera_id, "photo_time": time.time()}, timeout=1)


def get_urls():
    result = requests.get(SERVER_URL + '/servers', timeout=10)
    global server_urls
    server_urls = json.loads(result.text)


if __name__ == "__main__":
    get_urls()
    print(server_urls)

    while True:
        take_picture("picture.jpg")
        send_image("picture.jpg")
        time.sleep(1)
