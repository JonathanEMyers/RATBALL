# Sparkfun libraries for OTOS sensor tx/rx:
import qwiic_i2c, qwiic_otos
# Python stdlib: 
import struct, threading, socket, time
from collections import deque # for buffers
from datetime import datetime, timezone

# custom logger class:
from logger import Logger

import yaml
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

# instantiate logger object (supports log-level aware reporting):
logger = Logger('OpticalSensorClient', 3)

# network params (TODO: read from yaml conf)
HOST = '127.0.0.1'
PORT = 36783

# instantiate socket stream connection:
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT))
logger.info("Connected to server.")

# NOTE: I2C addresses should be verified with the following shell command: 
#    `i2cdetect -y -r 7`
# Both OTOS sensors have a fixed I2C address of `0x17`; to resolve address conflict,
# one sensor's address is remapped using an LTC4316 (dedicated I2C address translation IC)
SENSOR1_ADDR = 0x17
SENSOR2_ADDR = 0x67


# manifest of sensors as tuple of (i2c-address, sensor-device-object):
sensor_manifest = [
    (SENSOR1_ADDR, qwiic_otos.QwiicOTOS(address=SENSOR1_ADDR)), 
    (SENSOR2_ADDR, qwiic_otos.QwiicOTOS(address=SENSOR2_ADDR)),
]

# const buffer size for packing struct (">4dI", big-endian 4x double + 1x int = 36 bytes)
BUF_SIZE = 36


# following dict comprehension should eval to:
# sensor_map = {
#   '0x17': {
#       'device': qwiic_otos.QwiicOTOS(address=SENSOR1_ADDR),
#       'data_buffer': deque(maxlen=BUF_SIZE),
#       'meta_buffer': deque(maxlen=BUF_SIZE),
#   },
#   '0x67': {...}
# }
sensor_map = {
    str(sensor_addr): {
        'device': sensor,
        'data_buffer': deque(maxlen=BUF_SIZE),
        'meta_buffer': deque(maxlen=BUF_SIZE),
     } for sensor_addr, sensor in sensor_manifest
}


# sanity check; ensures all mapped sensors are reachable:
for addr, sensor in sensor_map.items():
    if not sensor['device'].is_connected():
        logger.critical(f'Device at address `{addr}` is not connected, aborting!')
        exit(1)


# begin polling sensors:
for sensor in sensor_map.values():
    sensor['device'].begin()


def recv_all(sock, size):
    """socket helper - ensures that each packet is complete before transmit"""
    data = b""
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            return None
        data += packet
    return data


unix_epoch = datetime.fromtimestamp(0, timezone.utc)
def unix_time_millis(dt):
    """formats timestamps as milliseconds-since-epoch (double-precision float, only requires 8 bytes)"""
    if dt.tzinfo is None:
        # make dt offset-aware in UTC if it's naive
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # convert to UTC if it's aware in a different timezone
        dt = dt.astimezone(timezone.utc)
    return (dt - unix_epoch).total_seconds() * 1000.0


def pack_motion_data(metadata: float, motion_data, sensor_idx: int):
    """serialization helper - marshals data into predefined binary struct"""
    return struct.pack(
        ">4dI", 
        metadata, motion_data[0].x, motion_data[0].y, motion_data[0].h, sensor_idx
    )


# thread-global flag for signalling receipt of an external termination signal:
global termFlag
termFlag = False


def data_enqueue_task():
    """thread task that pushes sensor data into deque buffers"""
    while not termFlag:
        for addr, sensor in sensor_map.items():
            data = sensor['device'].getPosVelAcc()
            if data: 
                sensor_map[addr]['data_buffer'].append(data)
                sensor_map[addr]['meta_buffer'].append(unix_time_millis(datetime.now()))


def data_transmit_task():
    """thread task that pops sensor data from deque buffers and transmits via socket"""
    transmissionComplete = False
    while not transmissionComplete:
        if not termFlag:
            for idx, (addr, sensor) in enumerate(sensor_map.items()):
                dataBuf, metaBuf = sensor['data_buffer'], sensor['meta_buffer']
                if len(dataBuf) > 0:
                    data, meta = dataBuf.popleft(), metaBuf.popleft()
                else:
                    data, meta = None, None
                    if termFlag:
                        logger.info("No data left, sending stop signal.")
                        try:
                            s.sendall(b'END_STOP')
                            transmissionComplete = True
                        except Exception as e:
                            logger.error(f"Error sending stop signal: {e}")
                        break
                if data is not None:
                    packet = pack_motion_data(meta, data, idx)
                    try:
                        s.sendall(packet)
                    except Exception as e:
                        logger.error(f"Error sending packet with timestamp `{meta}`: {e}")
    logger.debug("data transmit thread lifecycle complete, closing socket")
    s.close()


def term_listener_task():
    """thread task that listens for external termination signal"""
    logger.info("Listening for termination signal.")
    stopMessage = recv_all(s, 10)
    if stopMessage and stopMessage.startswith(b'BEGIN_STOP'):
        logger.info("Received termination signal.")
        termFlag = True


# set up and spawn thread pool:
thread_pool = [
    threading.Thread(name='optical-sensor-data-enq', target=data_enqueue_task,  daemon=True),
    threading.Thread(name='optical-sensor-data-tx',  target=data_transmit_task, daemon=True),
    threading.Thread(name='optical-sensor-term-lst', target=term_listener_task, daemon=True),
]
for t in thread_pool: t.start()
for t in thread_pool: t.join()
