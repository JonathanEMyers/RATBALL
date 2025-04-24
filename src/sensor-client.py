# Python stdlib:
import struct
import threading
import socket
import sys
import os

# custom sensor class for OTOS sensors:
from sensor import Sensor

# lib to read settings from .yaml file
import yaml

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

# logger class:
from loguru import logger

logger.add(
    sys.stdout, colorize=True, format="<green>{time}</green> <level>{message}</level>"
)

self_path = os.path.abspath(__file__)
self_dir = os.path.split(self_path)[0]


with open(f"{self_dir}/../settings.yaml", "r") as settingsFile:
    data = list(yaml.load(settingsFile, Loader=SafeLoader))

    # network params
    ingestHostIP = data[0]["ingestorSettings"]["ingestorIPAddress"]
    ingestListenerPort = data[0]["ingestorSettings"]["ingestorListenerPort"]
    # ingestJetsonPort = data[1]["jetsonSettings"]["ingestorJetsonCommPort"]

    # BMIHostIP = data[2]["BMISettings"]["BMIIPAddress"]
    # BMIListenerPort = data[2]["BMISettings"]["BMIListenerPort"]
    # BMIJetsonPort = data[1]["jetsonSettings"]["BMIJetsonCommPort"]

    settingsFile.close()

# instantiate socket stream connections:
sock_ingest = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock_ingest.connect((ingestHostIP, ingestListenerPort))
logger.info("Connected to ingestor server.")
logger.info(f"Listening on {ingestHostIP}:{ingestListenerPort}...")

# sock_BMI = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# sock_BMI.connect((BMIHostIP, BMIListenerPort))
# logger.info("Connected to BMI server.")
# logger.info(f"Listening on {BMIHostIP}:{BMIListenerPort}...")


# NOTE: I2C addresses should be verified with the following shell command:
#    `i2cdetect -y -r 7`
# Both OTOS sensors have a fixed I2C address of `0x17`; to resolve address conflict,
# one sensor's address is remapped using an LTC4316 (dedicated I2C address translation IC)
sensor_manifest = [Sensor(0x17), Sensor(0x67)]

# begin polling sensors:
for sensor in sensor_manifest:
    sensor.begin()

# thread-global flag for signalling receipt of an external termination signal:
termFlag = False


def recv_all(sock, size):
    """socket helper - ensures that each packet is complete before transmit"""
    data = b""
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            return None
        data += packet
    return data


def pack_motion_data(metadata: float, motion_data, sensor_idx: int):
    """serialization helper - marshals data into predefined binary struct"""
    return struct.pack(
        ">4dI",
        metadata,
        motion_data[0].x,
        motion_data[0].y,
        motion_data[0].h,
        sensor_idx,
    )


def data_enqueue_task():
    """thread task that pushes sensor data into deque buffers"""
    while not termFlag:
        for sensor in sensor_manifest:
            sensor.poll_data()


def data_transmit_task():
    """thread task that pops sensor data from deque buffers and transmits via socket"""
    transmissionComplete = False
    while not transmissionComplete:
        if not termFlag:
            for idx, sensor in enumerate(sensor_manifest):
                metadata, data = sensor.get_next()
                if data is not None:
                    packet = pack_motion_data(metadata, data, idx)
                    try:
                        sock_ingest.sendall(packet)
                    except Exception as e:
                        logger.error(
                            f"Error sending packet with timestamp `{metadata}`: {e}"
                        )
                elif termFlag:
                    logger.info("No data left, sending stop signal.")
                    try:
                        sock_ingest.sendall(b"END_STOP")
                        transmissionComplete = True
                    except Exception as e:
                        logger.error(f"Error sending stop signal: {e}")
                    break
    logger.debug("data transmit thread lifecycle complete, closing socket")
    sock_ingest.close()


def term_listener_task():
    """thread task that listens for external termination signal"""
    global termFlag
    logger.info("Listening for termination signal.")
    stopMessage = recv_all(sock_ingest, 10)
    if stopMessage and stopMessage.startswith(b"BEGIN_STOP"):
        logger.info("Received termination signal.")
        termFlag = True


# set up and spawn thread pool:
thread_pool = [
    threading.Thread(
        name="optical-sensor-data-enq", target=data_enqueue_task, daemon=True
    ),
    threading.Thread(
        name="optical-sensor-data-tx", target=data_transmit_task, daemon=True
    ),
    threading.Thread(
        name="optical-sensor-term-lst", target=term_listener_task, daemon=True
    ),
]
for t in thread_pool:
    t.start()
for t in thread_pool:
    t.join()
