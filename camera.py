import json
import requests
import time
import os

from utility import bootup_camera
from const import servers
from picamera import PiCamera


SERVER_URL = 'http://18.221.18.72:5000'
server_urls = servers

camera = PiCamera()
camera.resolution = (1024, 768)
camera.start_preview()

time.sleep(2)  # Camera warm-up time


def take_picture(file="foo.jpg"):
    camera.capture(file)


def send_image(f):
    files = {'imagefile': (f, open(os.path.basename(f), 'rb'), 'image/jpeg')}
    requests.post(SERVER_URL, files=files, data={"camera_id": 1, "photo_time": time.time()}, timeout=1)


def get_urls():
    bootup_camera(server_urls)


if __name__ == "__main__":
    # pic = '/Users/Sander/Desktop/Other/Pictures_Movies/5k/IMG_4794.JPG'
    # with open(pic, 'r') as file:
    #     send_image(pic, file)
    get_urls()
    print(server_urls)
