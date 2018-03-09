#!/usr/bin/env python2

import argparse
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


def get_urls():
    bootup_camera(server_urls)


def start_camera_thread(camera, room_label):
    c = Camera(camera, room_label)
    c.start()


class Camera(Thread):

    def __init__(self, camera, room_label):
        Thread.__init__(self)
        self.camera = camera
        self.room_label = room_label

    def take_picture(self):
        self.photo_time = time.time()
        self.image_name = str(self.photo_time) + ".jpg"
        self.camera.capture(self.image_name)

    def send_image(self):
        files = {'imagefile': (self.image_name, open(os.path.basename(self.image_name), 'rb'), 'image/jpeg')}
        requests.post(SERVER_URL, files=files, data={"camera_id": self.room_label, "photo_time": time.time()})

    def run(self):
        print "Taking picture..."
        self.take_picture()
        print "Sending picture [%s]" % self.image_name
        self.send_image()
        print "Removing sent image [%s]" % self.image_name
        os.remove(self.image_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-r, --room', type=str, dest="room_label", help='label for room')
    args = parser.parse_args()
    print "Room Label: %s" % args.room_label

    get_urls()
    print(server_urls)

    print "Initializing camera..."
    camera = PiCamera()
    camera.resolution = (1024, 768)
    camera.start_preview()
    time.sleep(2)  # Camera warm-up time

    print "Starting capture/thread loop"
    while True:
        start_camera_thread(camera, args.room_label)
        time.sleep(10)
