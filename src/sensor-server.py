import socket
import threading
import struct
import sys
import os
from loguru import logger

import yaml

logger.add(
    sys.stdout, colorize=True, format="<green>{time}</green> <level>{message}</level>"
)

self_path = os.path.abspath(__file__)
self_dir = os.path.split(self_path)[0]
parent_dir = os.path.abspath(os.path.join(self_dir, '..'))

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

with open(f"{parent_dir}/settings.yaml", "r") as settings_file:
    data = list(yaml.load(settings_file, Loader=SafeLoader))

    # network params
    ingestHostIP = data[0]["ingestorSettings"]["ingestorIPAddress"]
    ingestListenerPort = data[0]["ingestorSettings"]["ingestorListenerPort"]
    #    ingestJetsonPort = data[1]["jetsonSettings"]["ingestorJetsonCommPort"]
    #
    #    BMIHostIP = data[2]["BMISettings"]["BMIIPAddress"]
    #    BMIListenerPort = data[2]["BMISettings"]["BMIListenerPort"]
    #    BMIJetsonPort = data[1]["jetsonSettings"]["BMIJetsonCommPort"]

    settings_file.close()

# instantiate socket stream connections:
sock_ingest = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock_ingest.bind((ingestHostIP, ingestListenerPort))
sock_ingest.listen()
logger.info("Connected to ingestor server.")
logger.info(f"Listening on {ingestHostIP}:{ingestListenerPort}...")

# sock_BMI = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# sock_BMI.bind((BMIHostIP, BMIListenerPort))
# logger.info("Connected to BMI server.")
# logger.info(f"Listening on {BMIHostIP}:{BMIListenerPort}...")

# Flags to begin and end stopping program
terminationFlag = False

# TODO: refactor to be call order independent
# accept connection from sensor client:
conn, addr = sock_ingest.accept()
logger.info(f"Connected to sensor client via {addr}")

# accept connection to stop program client:
# conn2, addr2 = sock_BMI.accept()
# logger.info(f"Connected to stop client via {addr2}")


def format_output(unmarshaled_data):
    """helper for formatting collected data as CSV"""
    metadata = unmarshaled_data[0]
    sensor_x, sensor_y, sensor_h = unmarshaled_data[1:4]
    return f"{metadata},{sensor_x},{sensor_y},{sensor_h}\n"


def recv_all(sock, size):
    """Ensures all data is received before processing."""
    data = bytearray()
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            return None  # Handle closed connection
        data.extend(bytearray(packet))
        # logger.debug(f'sock.recv got data of length {len(data)}\n')
    return data


def data_receiver_task():
    """thread task that receives sensor data and writes it to files in CSV format"""
    global terminationFlag

    # open output file descriptors for writing:
    with open(f"{parent_dir}/output/sensor1.csv", "w") as fSensor1, open(
        f"{parent_dir}/output/sensor2.csv", "w"
    ) as fSensor2:
        logger.info("Opened sensor data files!")

        current_sensor = None
        while not terminationFlag:
            # Receiving entire packet
            packet = recv_all(conn, 36)
            # logger.log(f'packet: {struct.unpack(">4d", packet)}')
            if packet is None:
                pass
            elif packet[:8] == b"END_STOP":
                logger.info("Received terminationFlag trigger")
                terminationFlag = True
            else:
                # Splitting packet into metadata and sensor data
                unpacked = struct.unpack(">4dI", packet)
                sensor_idx = unpacked[4]
                sensor_change = current_sensor != sensor_idx
                current_sensor = sensor_idx
                if sensor_change:
                    logger.debug(f"Now receiving data for sensor ID {current_sensor}")
                if current_sensor == 0:
                    fSensor1.write(format_output(unpacked))
                elif current_sensor == 1:
                    fSensor2.write(format_output(unpacked))
                else:
                    logger.critical(
                        f"Got invalid sensor ID: `{current_sensor}`, possible packet corruption"
                    )
                    raise Exception("Invalid sensor ID")

    # close all connections:
    conn.close()
    # conn2.close()
    sock_ingest.close()
    logger.info("Server shut down.")


def term_signalling_task():
    """thread task that forwards an external termination signal"""
    while True:
        try:
            # stopSignal = conn2.recv(10)
            if stopSignal:
                logger.info("Stop signal received, forwarding to sensor client...")
                conn.sendall(stopSignal)
                break
        except:
            logger.error("Error encountered while forwarding stop program flag")
            break


# Start threads to handle each client
sensorThread = threading.Thread(target=data_receiver_task, daemon=True)
stoppingThread = threading.Thread(target=term_signalling_task, daemon=True)

sensorThread.start()
stoppingThread.start()

stoppingThread.join()
sensorThread.join()
