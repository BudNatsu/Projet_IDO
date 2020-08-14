import signal
import socket
import time
import calendar
import argparse
import re
import logging
import requests

run_app = True

logging.basicConfig(
    level = logging.INFO,
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger('adsbdatabase')

class AdsbError(Exception):
    pass

class Adsbmeg(object):

    REGEXP_MSG = r'^MSG,' \
        r'(?P<transmission>\d),' \
        r'(?P<session>\d+),' \
        r'(?P<aircraft>\d+),' \
        r'(?P<hexident>[0-9A-F]+),' \
        r'(?P<flight>\d+),' \
        r'(?P<gen_date>[0-9/]+),' \
        r'(?P<gen_time>[0-9:\.]+),' \
        r'(?P<log_date>[0-9/]+),' \
        r'(?P<log_time>[0-9:\.]+),' \
        r'(?P<callsign>[\w\s]*),' \
        r'(?P<altitude>\d*),' \
        r'(?P<speed>\d*),' \
        r'(?P<track>[\d\-]*),' \
        r'(?P<latitude>[\d\-\.]*),' \
        r'(?P<longitude>[\d\-\.]*),' \
        r'(?P<verticalrate>[\d\-]*),' \
        r'(?P<squawk>\d*),' \
        r'(?P<alert>[\d\-]*),' \
        r'(?P<emergency>[\d\-]*),' \
        r'(?P<spi>[\d\-]*),' \
        r'(?P<onground>[\d\-]*)$'

    NORMALIZE_MSG = {
        'transmission': (lambda v: int(v)),
        'session': (lambda v: int(v)),
        'aircraft': (lambda v: int(v)),
        'flight': (lambda v: int(v)),
        'callsign': (lambda v: v.strip()),
        'altitude': (lambda v: int(v)),
        'speed': (lambda v: int(v)),
        'track': (lambda v: int(v)),
        'latitude': (lambda v: float(v)),
        'longitude': (lambda v: float(v)),
        'verticalrate': (lambda v: int(v)),
        'alert': (lambda v: True if v == '-1' else False),
        'emergency': (lambda v: True if v == '-1' else False),
        'spi': (lambda v: True if v == '-1' else False),
        'onground': (lambda v: True if v == '-1' else False),
    }

    def __init__(self):
        self.re_msg = re.compile(self.REGEXP_MSG)
        self.avions = {}
        self.avions_age = {}

    def __normalize_msg(self, msg):
        for field, fnc in self.NORMALIZE_MSG.items():
            if field in msg:
                msg[field] = fnc(msg[field])

        return msg

    def keys(self):
        return self.avions.keys()

    def values(self):
        return self.avions.values()

    def items(self):
        return self.avions.items()

    def pop(self, *args):
        return self.avions.pop(*args)


    def age(self, hexident):
        return (time.time() - self.avions_age.get(hexident, 0))

    def msg(self, data):

        m = self.re_msg.match(data)
        if not m:
            log.error('Mauvais format MSG: \'{}\'.'.format(data))
            raise AdsbError('Mauvais format pour ce message!')
            pass

        message = {k: v for k, v in m.groupdict().items() if v}
        message = self.__normalize_msg(message)

        self.avions_age[message['hexident']] = time.time()

        if message['hexident'] not in self.avions:
            self.avions[message['hexident']] = message
            self.avions[message['hexident']]['count'] = 1
        else:
            self.avions[message['hexident']].update(message)
            self.avions[message['hexident']]['count'] += 1
            
class InfluxDB(object):
    def __init__(self, url, database='dump1090', username="admin", password="influx"):
        self.url = url
        self.params = '/write?precision=s&db={}'.format(database)

    def write(self, measurement, data, timestamp=None):

        lines = []

        for d in data:
            fields = []
            for k, v in d['fields'].items():
                if v is None:
                    continue
                elif type(v) is bool:
                    fields.append('{}={}'.format(k, 't' if v else 'f'))
                elif type(v) is int:
                    fields.append('{}={}i'.format(k, v))
                elif type(v) is float:
                    fields.append('{}={}'.format(k, v))
                elif type(v) is str:
                    fields.append('{}="{}"'.format(k, v))
                else:
                    log.warning('Le type {} n''est supporté par InfluxDB. {}={}.'.format(
                        type(v), k, v
                    ))

            lines.append('{measurement},{tags} {fields} {timestamp}'.format(
                measurement = measurement,
                tags = ','.join('{}={}'.format(k, v) for k, v in d['tags'].items()),
                fields = ','.join(x for x in fields),
                timestamp = d['timestamp'] if 'timestamp' in d else int(time.time()),
            ))

        resp = requests.post(self.url + self.params, data = '\n'.join(l for l in lines))
        if resp.status_code == 204:
            return True

        log.error('Ecriture impossible. Le code erreur est {}'.format(resp.status_code))
        return False

def exit_gracefully(signum, frame):
    global run_app
    run_app = False

class Dump1090(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.s = None
        self.data = ''

    def connect(self):
        log.info('Connexion à dump1090 en TCP sur {}:{}.'.format(self.host, self.port))
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connected = False

        while not connected:
            try:
                self.s.connect((self.host, self.port))
                log.info('Connexion OK, reception en cours')
            except:
                connected = False
                log.warning('Connexion impossible')
                time.sleep(1)
            else:
                connected = True

        self.s.setblocking(False)
        self.s.settimeout(1)

    def disconnect(self):
        self.s.close()

    def receive(self):

        ret = None

        try:
            self.data += self.s.recv(1024).decode('UTF-8')
            self.s.send(bytes("\r\n", 'UTF-8'))

            newline = self.data.find('\r\n')
            if newline >= 0:
                ret = self.data[:newline]
                self.data = self.data[newline + 2:]
        except socket.timeout:
            pass
        except socket.error as e:
            raise AdsbError('Socket error \'{}\'.'.format(e))

        return ret





def main():
    parser = argparse.ArgumentParser(
        description = 'Lis les données BaseStation de dump1090, '
        'les convertis en "InfluxDB line protocol", et les envois vers InfluxDB'
    )
    parser.add_argument(
        '-s', '--dump1090-server',
        default = "127.0.0.1",
        help = "Host/IP for dump1090 [127.0.0.1]"
    )
    parser.add_argument(
        '-p', '--dump1090-port',
        default = "30003",
        help = "Port pour la connexion TCP dump1090 pour les données BaseStation [30003]"
    )
    parser.add_argument(
        '-u', '--influx-url',
        default = "http://127.0.0.1:8186",
        help = "InfluxDB URL [http://127.0.0.1:8186]"
    )
    parser.add_argument(
        '-db', '--influx-database',
        default = "dump1090",
        help = "nom de la base de données InfluxDB"
    )
    parser.add_argument(
        '-si', '--send-interval',
        default = 60,
        help = "Reçoit les données, celles-ci seront stockées et envoyées vers InfluxDB toute les X secondes."
    )

    args = parser.parse_args()
    log.info(args)

    INTERVAL = int(args.send_interval)

    ap = Adsbmeg()

    dump1090 = Dump1090(args.dump1090_server, int(args.dump1090_port))
    dump1090.connect()

    influx = InfluxDB(args.influx_url, database=args.influx_database)

    last_print = time.time()

    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)

    global run_app
    while run_app:
        if (time.time() - last_print) > INTERVAL:
            last_print = time.time()

            to_send = []

            for hexident, msg in ap.items():
                if not all(k in msg for k in ['callsign', 'squawk']):
                    log.info('callsign ou squawk manquant pour {}'.format(hexident))
                    continue

                if ap.age(hexident) > INTERVAL:
                    log.info('l Avion {} n as pas été vu depuis longtemps.'.format(hexident))
                    continue

                timestamp = int(calendar.timegm(time.strptime('{} {}'.format(
                    msg['gen_date'], msg['gen_time']
                ), '%Y/%m/%d %H:%M:%S.%f')))

                # Prepare les données et les tags à envoyer.
                to_send.append({
                    'tags': {
                        'hexident': hexident,
                        'callsign': msg['callsign'],
                        'squawk': msg['squawk'],
                    },
                    'fields': {
                        'hexident': hexident,
                        'callsign': msg['callsign'],
                        'generated': timestamp,
                        'altitude': msg.get('altitude'),
                        'speed': msg.get('speed'),
                        'track': msg.get('track'),
                        'latitude': msg.get('latitude'),
                        'longitude': msg.get('longitude'),
                        'verticalrate': msg.get('verticalrate'),
                        'alert': msg.get('alert'),
                        'emergency': msg.get('emergency'),
                        'spi': msg.get('spi'),
                        'onground': msg.get('onground'),
                        'count': msg.get('count', 0),
                    }
                })

            ap.clear(INTERVAL * 3)
            if len(to_send) > 0:
                if influx.write('avions', to_send):
                    log.info('Sauvegarde de {} avions vers InfluxDB.'.format(len(to_send)))
            else:
                log.info('Aucun avions sauvegardés.')

        try:
            msg = dump1090.receive()
        except AdsbError as e:
            print(e)
            run_app = True
        else:
            if msg is not None:
                ap.msg(msg)

    log.info("Déconnecté de dump1090")
    dump1090.disconnect()

if __name__ == "__main__":
    main()
