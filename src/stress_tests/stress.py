from __future__ import division
import requests
import time
from threading import Thread


URL = "http://bigsister.info"

FREQS = [1024]
IMAGE = open("test_image.jpg", 'rb')


# Send an arbitrary image to the backend server
def send_image(l):
    files = {'imagefile': ("name", IMAGE, 'image/jpeg')}
    payload = {'camera_id': 0, 'photo_time': time.time()}
    response = requests.post(URL, files=files, data=payload)
    sec = response.elapsed.total_seconds()
    l.append(sec)

# Requests a random room from the backend server
def request_room(l):
    response = requests.get(URL + "/counts")
    sec = response.elapsed.total_seconds()
    l.append(sec)

def do_both(l):
    p_r = []
    g_r = []
    t1 = Thread(target=send_image, args=(p_r,))
    t2 = Thread(target=request_room, args=(g_r,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    l.append(max(p_r[0], g_r[0]))

def test_func(func):
    for freq in FREQS:
        l = []
        t = 0
        threads = []
        start = time.time()
        while t < 2:
            threads.append(Thread(target=func, args=(l,)))
            threads[-1].start()
            time.sleep(1/freq)
            t += 1/freq
        actual_freq = (time.time() - start)/(freq*2)
        for t in threads: 
            t.join()
        print "1/" + str(freq) + ": ", sum(l)/len(l), "response time", "actual: ", 1/actual_freq

def stress_server():
    print "*** TESTING GET REQUESTS ***"
    test_func(request_room)

    # print "*** TESTING POST REQUESTS ***"
    # test_func(send_image)

    # print "*** TESTING BOTH SIMULTANEOUSLY ***"
    # test_func(do_both)


if __name__ == "__main__":
    stress_server()
