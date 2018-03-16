import sqlite3
from const import SENSOR_DB
from utility import retrieve_startup_info


def setup_db_sensor(servers):
    conn = sqlite3.connect(SENSOR_DB)
    c = conn.cursor()

    c.execute('CREATE TABLE IF NOT EXISTS server_list (ip_address TEXT UNIQUE);')
    conn.commit()

    c.execute('SELECT ip_address FROM server_list;')
    server_rows = c.fetchall()
    for row in server_rows:
        ip_address = row[0]
        servers.add(ip_address)

    conn.close()


def bootup_camera(servers):
    setup_db_sensor(servers)
    retrieve_startup_info(servers, set(), {}, SENSOR_DB)
