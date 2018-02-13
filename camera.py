import requests
import os


SERVER_URL = 'http://18.221.18.72:5000'


def send_image(pic, f):
    files = {'imagefile': (os.path.basename(pic), f, 'image/jpeg')}
    result = requests.post(SERVER_URL, files=files)
    print result.status_code


if __name__ == "__main__":
    pic = '/Users/Sander/Desktop/Other/Pictures_Movies/5k/IMG_4794.JPG'
    with open(pic, 'r') as file:
        send_image(pic, file)
