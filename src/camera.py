#!/usr/bin/env python2
from __future__ import division
import argparse
import requests
import time
from glob import glob
import os
from picamera import PiCamera
from threading import Thread

from cutility import bootup_camera
from const import servers
import numpy as np
from PIL import Image

SERVER_URL = 'https://bigsister.info'
server_urls = servers
PERCENT_DIFFERENCE_THRESHOLD = 0.5

IMAGE_BANK_SIZE = 2**20 * 100
IMAGE_FILE_DIR = "image_data/"
PICTURE_FREQUENCY = 5 * 60

def get_urls():
    bootup_camera(server_urls)



class Camera(Thread):

    def __init__(self, cam, room_label):
        Thread.__init__(self)
        self.camera = cam
        self.room_label = room_label
        self.photo_time = None
        self.old_name = None
        self.current_name = None

    @staticmethod
    def get_percent_difference(image1, image2):
        im1 = np.asarray(Image.open(image1))
        im2 = np.asarray(Image.open(image2))

        diff = np.linalg.norm(im1-im2)
        max_diff = np.sqrt(reduce(lambda x, y: x*y, im1.shape)*(255**2))
        return diff/max_diff

    def take_picture(self):
        self.photo_time = time.time()
        self.old_name = self.current_name
        self.current_name = IMAGE_FILE_DIR + str(self.photo_time) + ".jpg"
        self.camera.capture(self.current_name)

    def send_image(self, same):
        try:
            if not same:
                files = {'imagefile': (self.current_name, open(self.current_name, 'rb'), 'image/jpeg')}
                r = requests.post(SERVER_URL, files=files, verify=False, data={"camera_id": self.room_label, "photo_time": time.time()})
            else:
                r = requests.post(SERVER_URL, verify=False, data={"camera_id": self.room_label, "photo_time": time.time()})
            print r.text
        except Exception as e:
            print "failed to send image:", e

    def run(self):
        while True:
            print "Taking picture..."
            self.take_picture()
            print(self.current_name, self.old_name)
            if self.old_name is None:
                diff = 1
            else:
                diff = self.get_percent_difference(self.current_name, self.old_name)
            if diff > PERCENT_DIFFERENCE_THRESHOLD: 
                print "Sending picture [%s]" % self.current_name
                self.send_image(same=False)
                if self.old_name is not None:
                    os.remove(self.old_name)
            else:
                print "Image matches previous image; discarding"
                os.remove(self.current_name)
                self.current_name = self.old_name
                self.send_image(same=True)
            time.sleep(PICTURE_FREQUENCY)


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
    c = Camera(camera, args.room_label)
    c.start()

