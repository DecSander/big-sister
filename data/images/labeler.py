import sys
import webbrowser
import os
sys.path.append("../../src")
from PIL import Image
from crowd_counter import count_people
from shutil import copyfile

chrome_path = '/usr/bin/google-chrome %s'

def is_int(n):
    try:
        int(n)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    direc = os.path.dirname(os.path.realpath(__file__))
    for img_name in os.listdir(direc):
        img = os.path.join(direc, img_name)
        if img.endswith("jpg") or img.endswith("png") or img.endswith("jpeg"):
            print 'file://' + os.path.join(direc, img)
            webbrowser.get(chrome_path).open('file://' + img)
            num = ""
            while not num.lower().startswith("d") and not is_int(num):
                num = raw_input("Count or delete: ")
            if not num.lower().startswith("d"):
                estimated = count_people(Image.open(img))
                truth = int(num)
                file_name = str(truth) + "-" + str(estimated) + "-" + img_name.split(".")[0] + "." + img_name.split(".")[-1]
                copyfile(img, os.path.join(direc, "labelled", file_name))
                print "Wrote out file: ", file_name
                os.remove(img)
            else:
                os.remove(img)
                print "DELETED FILE: ", img
                