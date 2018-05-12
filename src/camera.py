#!/usr/bin/env python2
from __future__ import division
import argparse
import requests
import time
import os
# from picamera import PiCamera
from threading import Thread

from cutility import bootup_camera
from const import servers
import numpy as np
from PIL import Image

SERVER_URL = 'http://18.221.18.72:5000'
server_urls = servers
PERCENT_DIFFERENCE_THRESHOLD = 0.02


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
        self.old_name = None
        self.current_name = None

    def take_picture(self):
        self.photo_time = time.time()
        self.current_name = str(self.photo_time) + ".jpg"
        self.camera.capture(self.current_name)

    @staticmethod
    def get_percent_difference(image1, image2):
        im1 = np.asarray(Image.open(image1))
        im2 = np.asarray(Image.open(image2))

        diff = np.linalg.norm(im1-im2)
        max_diff = np.sqrt(reduce(lambda x, y: x*y, im1.shape)*(255**2))
        return diff/max_diff

    def send_image(self):
        files = {'imagefile': (self.current_name, open(os.path.basename(self.current_name), 'rb'), 'image/jpeg')}
        requests.post(SERVER_URL, files=files, data={"camera_id": self.room_label, "photo_time": time.time()})

    def run(self):
        print "Taking picture..."
        self.take_picture()
        print "Sending picture [%s]" % self.current_name
        self.send_image()
        print "Removing sent image [%s]" % self.current_name
        os.remove(self.current_name)


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
