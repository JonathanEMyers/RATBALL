# Python stdlib:
import struct
import threading
import socket
import time
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
from microphone import Microphone

# logger class:
from loguru import logger
logger.add(sys.stdout, colorize=True, format="<green>{time}</green> <level>{message}</level>")

self_path = os.path.abspath(__file__)
self_dir = os.path.split(self_path)[0]



with open(f"{self_dir}/../settings.yaml", "r") as settingsFile:
    data = list(yaml.load(settings_file, Loader=SafeLoader))

    # network params
    ingest_host_IP = data[0]["ingestorSettings"]["ingestorIPAddress"]
    ingest_listener_port = data[0]["ingestorSettings"]["ingestorListenerPort"]
    ingest_jetson_port = data[1]["jetsonSettings"]["ingestorJetsonCommPort"]

    BMI_host_IP = data[2]["BMISettings"]["BMIIPAddress"]
    BMI_listener_port = data[2]["BMISettings"]["BMIListenerPort"]
    BMI_jetson_port = data[1]["jetsonSettings"]["BMIJetsonCommPort"]

    # microphone Settings
    audio_num_chan = data[4]["audioSettings"]["channels"]
    audio_rate = data[4]["audioSettings"]["rate"]

    format_str = data[4]["audioSettings"]["format"]

    buf_len = data[3]["bufferSettings"]["bufferLength"]
    framerate = data[3]["bufferSettings"]["framerate"]

    # Speaker Settings
    speaker_amp = data[5]["speakerSettings"]["amplitude"]
    speaker_block_size = data[5]["speakerSettings"]["blockSize"]

    settings_file.close()

# instantiate socket stream connections:
sock_ingest = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock_ingest.setsockopt(
    socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
)  # do not wait so long after program terminates to close socket
sock_ingest.connect(
    (ingest_host_IP, ingest_listener_port)
)  # client side should connect, server should bind
logger.info("Connected to ingestor server.")
logger.info(f"Listening on {ingest_host_IP}:{ingest_listener_port}...")

sock_BMI = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock_BMI.setsockopt(
    socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
)  # So the system does not wait so long after the program terminates to close the socket
sock_BMI.connect(
    (BMI_host_IP, BMI_listener_port)
)  # client side should connect, server should bind
logger.info("Connected to BMI server.")
logger.info(f"Listening on {BMI_host_IP}:{BMI_listener_port}...")

# define sensor objects (2 optical, 2 camera, microphone, speaker, placeholders)
mic = Microphone(buf_len * framerate, audio_rate, audio_num_chan, format_str, framerate)

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
termFlag = False

# intial parameters
speaker_frequency = 0

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
def audio_callback(outdata, frames, time, status):
    global speaker_frequency
    t = (np.arange(frames) + audio_callback.phase) / audio_rate
    wave = speaker_amp * np.sin(2 * np.pi * speaker_frequency * t)
    outdata[:] = wave.reshape(-1, 1)
    audio_callback.phase += frames  # Keep track of phase
audio_callback.phase = 0  # Initial phase


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


def pack_audio_data(audio_metadata, sent_time, audio_data, frame_num):
    """serialization helper - marshals data into predefined binary struct"""
    return struct.pack(
        ">I3d",
        audio_metadata,
        Microphone.unix_time_millis(sent_time),
        audio_data,
        frame_num,
    )


def data_enqueue_task():
    """thread task that pushes sensor data into deque buffers"""
    while not termFlag:
        for sensor in sensor_manifest():
            sensor.poll_data()
        mic.append_mic_data()


def data_transmit_task():
    """thread task that pops sensor data from deque buffers and transmits via socket"""
    transmissionComplete = False
    while not transmissionComplete:
        if not termFlag:
            audio_metadata, audio_data = Microphone.pop_mic_data()
            if audio_data is not None:
                audio_packet = pack_audio_data(audio_metadata, audio_data)
            for idx, sensor in enumerate(sensor_manifest):
                metadata, data = sensor.get_next()
                if data is not None:
                    packet = pack_motion_data(metadata, data, idx)
                    try:
                        sock_ingest.sendall(packet + audio_packet)
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
    sock_BMI.close()

def term_listener_task():
    """thread task that listens for external termination signal"""
    global termFlag
    global speaker_frequency
    logger.info("Listening for termination signal.")
    stopMessage = recv_all(sock_BMI, 10)
    if stopMessage and stopMessage.startswith(b"BEGIN_STOP"):
        logger.info("Received termination signal.")
        termFlag = True
    else:
        speaker_frequency = struct.unpack('>f', stopMessage[:4])[0]


def speaker_playback():
    global termFlag

    with sd.OutputStream(callback=audio_callback, samplerate=audio_rate, blocksize=speaker_block_size, channels=1):
        while not termFlag:
            time.sleep(.1)


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
    threading.Thread(
        name="speaker-playback", target=speaker_playback, daemon=True
    ),
]
for t in thread_pool:
    t.start()
for t in thread_pool:
    t.join()
