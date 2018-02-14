import os

MY_IP = os.environ['STATIC_IP'] if 'STATIC_IP' in os.environ else None
servers = ['18.218.132.215', '18.221.18.72']
MAX_MB = 2
MB_TO_BYTES = 1024 * 1024
