import os

MY_IP = os.environ['STATIC_IP'] if 'STATIC_IP' in os.environ else None
servers = set(['18.218.132.215', '18.221.18.72', 'localhost'])
backends = set(['18.218.132.215', '18.221.18.72', 'localhost'])
occupancy_predictors = set(['18.218.132.215:5002/', '18.221.18.72:5002/', 'localhost:5002/'])
occupancy_predictors = set(['18.218.132.215:5003/', '18.221.18.72:5003/', 'localhost:5003/'])
MAX_MB = 2
MB_TO_BYTES = 1024 * 1024
basewidth = 1000
TIMEOUT = 3
TIER1_DB = '../databases/tier1.db'
TIER2_DB = '../databases/tier2.db'
TIER2_DB = '../databases/tier2.db'
SENSOR_DB = '../databases/sensor.db'
FC_DB = '../databases/fc.db'
IP_REGEX = '\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'

FACE_COMPARE_THRESHOLD = 0.4

# Facebook App stuff
FB_APP_ID = '172353816928881'
FB_APP_SECRET = 'e7ebaa026225cdbc01b075d0ed014651'
