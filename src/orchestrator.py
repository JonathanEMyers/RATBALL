# Python stdlib:
import threading
import struct
import socket
import time
import sys
import os

import numpy as np
import sounddevice as sd

# lib to read settings from .yaml file:
import yaml

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

# custom classes for sensors:
from sensor import Sensor
import blankSensor

# logger class:
from loguru import logger

logger.add(
    sys.stdout, colorize=True, format="<green>{time}</green> <level>{message}</level>"
)

self_path = os.path.abspath(__file__)
self_dir = os.path.split(self_path)[0]


with open(f"{self_dir}/../settings.yaml", "r") as settings_file:
    settings = yaml.load(settings_file, Loader=SafeLoader)
    # network params
    ingest_ip = settings["ingestor"]["ip"]
    ingest_listen_port = settings["ingestor"]["listen_port"]
    jetson_ingest_comm_port = settings["jetson"]["ingest_comm_port"]

    bmi_ip = settings["bmi"]["ip"]
    bmi_listen_port = settings["bmi"]["listen_port"]
    jetson_bmi_comm_port = settings["jetson"]["bmi_comm_port"]

    # microphone Settings
    # audio_num_chan = data[4]["audioSettings"]["channels"]

    # format_str = data[4]["audioSettings"]["format"]

    # Speaker Settings
    speaker_amp = settings["speaker"]["amplitude"]
    speaker_block_size = settings["speaker"]["block_size"]
    audio_rate = settings["audio"]["rate"]
    buf_len = settings["buffer"]["buffer_length"]
    framerate = settings["buffer"]["framerate"]

    settings_file.close()

# intial parameters
speaker_frequency = 0
buf_size = buf_len * framerate

# instantiate socket stream connections:
sock_ingest = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock_ingest.connect((ingest_ip, ingest_listen_port))
logger.info("Connected to ingestor server.")
logger.info(f"Listening on {ingest_ip}:{ingest_listen_port}...")

# NOTE: add in when BMI is connected otherwise throws conn error
# sock_bmi = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# sock_bmi.connect((bmi_ip, bmi_listen_port))
# logger.info("Connected to ingestor server.")
# logger.info(f"Listening on {bmi_ip}:{bmi_listen_port}...")


# define sensor objects (2 optical, 2 camera, microphone, speaker, placeholders)
# mic = Microphone(buf_len * framerate, audio_rate, audio_num_chan, format_str, framerate)
lick_sensor = blankSensor.blankSensor(buf_size, framerate)
blank_sensor_one = blankSensor.blankSensor(buf_size, framerate)
blank_sensor_two = blankSensor.blankSensor(buf_size, framerate)
blank_sensor_three = blankSensor.blankSensor(buf_size, framerate)

# NOTE: I2C addresses should be verified with the following shell command:
#    `i2cdetect -y -r 7`
# Both OTOS sensors have a fixed I2C address of `0x17`; to resolve address conflict,
# one sensor's address is remapped using an LTC4316 (dedicated I2C address translation IC)
sensor_manifest = [
    Sensor(0x17),
    Sensor(0x67),
]

# begin polling sensors:
for sensor in sensor_manifest():
    sensor.begin()

# thread-global flag for signaling receipt of an external termination signal:
term_flag = threading.Event()


def recv_all(sock, size):
    """socket helper - ensures that each packet is complete before transmit"""
    data = b""
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            return None
        data += packet
    return data


# Uses sounddevice outputstream because alsaaudio pcm write was having issues
# with discontinuites creating weird harmonics, causing distorted sound.
# This allows constant audio stream and also phase shift of the waveform.
def audio_callback(outdata, frames):
    global speaker_frequency
    t = (np.arange(frames) + audio_callback.phase) / audio_rate
    wave = speaker_amp * np.sin(2 * np.pi * speaker_frequency * t)
    outdata[:] = wave.reshape(-1, 1)
    audio_callback.phase += frames  # Keep track of phase


audio_callback.phase = 0  # Initial phase

reconnect_timer = 60


# This function is called in case of a broken tcp connection between the jetson and another computer
# It tries to re-establish the connection for up to 60 seconds
def reconnect_to_ingestor():
    start_time = time.time()
    while time.time() - start_time < reconnect_timer:
        try:
            ingestSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ingestSocket.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
            )  # So the system does not wait so long after the program terminates to close the socket
            ingestSocket.bind((ingest_ip, jetson_ingest_comm_port))
            ingestSocket.connect((ingest_ip, ingest_listen_port))
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            print(
                f"In jetsonCode.reconnectToIngestor() -- Connection lost: {e}, retrying connection!"
            )
            time.sleep(1)
    print("In jetsonCode -- Connected to ingestor!")


def reconnect_to_BMI():
    start_time = time.time()

    while time.time() - start_time < reconnect_timer:
        try:
            BMISocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            BMISocket.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
            )  # So the system does not wait so long after the program terminates to close the socket
            BMISocket.bind((bmi_ip, jetson_bmi_comm_port))
            BMISocket.connect((bmi_ip, bmi_listen_port))
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            print(
                f"In jetsonCode.reconnectToBMI() -- Connection lost: {e}, retrying connection!"
            )
            time.sleep(1)
    print("In jetsonCode -- Connected to BMI!")


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


# def pack_audio_data(audio_metadata: float, sent_time: float, audio_data, frame_num: int):
#     """serialization helper - marshals data into predefined binary struct"""
#     return struct.pack(
#         ">I2d",
#         audio_metadata,
#         mic.unix_time_millis(sent_time),
#         frame_num,
#     ) + audio_data


def data_enqueue_task():
    """thread task that pushes sensor data into deque buffers"""
    while not term_flag.is_set():
        for sensor in sensor_manifest:
            sensor.poll_data()
        # mic.append_mic_data()


def data_transmit_task():
    """thread task that pops sensor data from deque buffers and transmits via socket"""
    transmission_complete = False
    while not transmission_complete:
        if not term_flag.is_set():
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
                else:
                    logger.info("No data left, sending stop signal.")
                    try:
                        sock_ingest.sendall(b"END_STOP")
                        transmission_complete = True
                    except Exception as e:
                        logger.error(f"Error sending stop signal: {e}")
                    break
    logger.debug("data transmit thread lifecycle complete, closing socket")

    sock_ingest.close()
    # sock_bmi.close()


def term_listener_task():
    """thread task that listens for external termination signal"""
    global speaker_frequency
    logger.info("Listening for termination signal.")
    stop_msg = recv_all(sock_bmi, 10)
    if stop_msg and stop_msg.startswith(b"BEGIN_STOP"):
        logger.info("Received termination signal.")
        term_flag.is_set(True)
    else:
        speaker_frequency = struct.unpack(">f", stop_msg[:4])[0]


def speaker_playback():
    with sd.OutputStream(
        callback=audio_callback,
        samplerate=audio_rate,
        blocksize=speaker_block_size,
        channels=1,
    ):
        while term_flag.is_set(False):
            time.sleep(0.1)


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
    threading.Thread(name="speaker-playback", target=speaker_playback, daemon=True),
]
for t in thread_pool:
    t.start()
for t in thread_pool:
    t.join()
