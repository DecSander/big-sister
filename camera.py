#!/usr/bin/env python2

import json
import requests
import time
import os

from utility import bootup_camera
from const import servers
from picamera import PiCamera
from threading import Thread


SERVER_URL = 'http://18.221.18.72:5000'
server_urls = servers

camera_id = 1


def get_urls():
    bootup_camera(server_urls)


def start_camera_thread(camera):
    c = Camera(camera)
    c.start()


class Camera(Thread):

    def __init__(self, camera):
        Thread.__init__(self)
        self.camera = camera

    def take_picture(self):
        self.photo_time = time.time()
        self.image_name = str(self.photo_time) + ".jpg"
        self.camera.capture(self.image_name)

    def send_image(self):
        files = {'imagefile': (self.image_name, open(os.path.basename(self.image_name), 'rb'), 'image/jpeg')}
        requests.post(SERVER_URL, files=files, data={"camera_id": camera_id, "photo_time": time.time()})

    def run(self):
        print "Taking picture..."
        self.take_picture()
        print "Sending picture..."
        self.send_image()
        print "Removing sent image..."
        os.remove(self.image_name)


if __name__ == "__main__":
    get_urls()
    print(server_urls)

    print "Initializing camera..."
    camera = PiCamera()
    camera.resolution = (1024, 768)
    camera.start_preview()
    time.sleep(2)  # Camera warm-up time

    print "Starting capture/thread loop"
    while True:
        start_camera_thread(camera)
        time.sleep(1)
