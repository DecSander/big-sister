import requests
import os
import json


SERVER_URL = 'http://18.221.18.72:5000'
server_urls = []


def send_image(pic, f):
    files = {'imagefile': (os.path.basename(pic), f, 'image/jpeg')}
    requests.post(SERVER_URL, files=files)


def get_urls():
    result = requests.get(SERVER_URL + '/servers', timeout=3)
    global server_urls
    server_urls = json.loads(result.text)


if __name__ == "__main__":
    # pic = '/Users/Sander/Desktop/Other/Pictures_Movies/5k/IMG_4794.JPG'
    # with open(pic, 'r') as file:
    #     send_image(pic, file)
    get_urls()
    print(server_urls)
