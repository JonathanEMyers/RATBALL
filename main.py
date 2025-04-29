import struct
from threading import Thread, Event
from datetime import datetime
import sys
import socket
from loguru import logger
from config import RatballConfig
# custom classes
from sensor import Sensor
from speaker import Speaker
from camera import Camera


class SensorGovernor(Thread):
    def __init__(self):
        # init governor thread superconstructor
        super(SensorGovernor, self).__init__(self)
        self._cfg = RatballConfig()
        # start thread events
        self._tx_complete = Event()
        self._term_flag = Event()

        self._manifest = [Sensor(addr) for addr in self._cfg.sensor.i2c_addr]

        self._sock_ingest = None
        self._sock_bmi = None
        self._init_sockets()

        # initialize sensor threads
        self._thread_pool = [
            Thread(target=self.enqueue, name="_sensor_enq_"),
            Thread(target=self.transmit, name="_sensor_tx_"),
            # listen thread runs in background, daemonize to exit when enq/tx threads die
            Thread(target=self.term_listen, name="_sensor_lst_", daemon=True),
        ]

    def _init_sockets(self) -> None:
        '''sets up TCP connections using socket Python stdlib'''
        # ingestor tx/rx
        self._sock_ingest = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock_ingest.connect(
            (self._cfg.ingestor.ip, self._cfg.ingestor.listen_port)
        )
        self._sock_ingest.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock_ingest.sendall()

        # bmi tx/rx
        self._sock_bmi = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock_bmi.connect((self._cfg.bmi.ip, self._cfg.bmi.listen_port))
        self._sock_bmi.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock_bmi.sendall()

    def _recv_all(self, sock, size) -> bytes:
        """ensures that each packet is complete before transmit"""
        data = b""
        while len(data) < size:
            packet = sock.recv(size - len(data))
            if not packet:
                return None
            data += packet
        return data

    def _pack_sensor_data(self, metadata: float, motion_data, sensor_idx: int) -> bytes:
        """marshals data into predefined binary struct"""
        return struct.pack(
            ">4dI",
            metadata,
            motion_data[0].x,
            motion_data[0].y,
            motion_data[0].h,
            sensor_idx,
        )

    def enqueue(self) -> None:
        '''thread task that pushes sensor data into deque buffers'''
        while not self._tx_complete.is_set():
            for sensor in self._manifest:
                sensor.poll_data()

    def transmit(self) -> None:
        '''thread task that pops sensor data from deque buffers and transmits via socket'''
        while not self._tx_complete.is_set():
            if not self._term_flag.is_set():
                for idx, sensor in enumerate(self._manifest):
                    # continue popping data from buffer until empty
                    metadata, data = sensor.get_next()
                    if data is not None:
                        packet = self._pack_motion_data(metadata, data, idx)
                        try:
                            self._sock_ingest.sendall(packet)
                        except Exception as e:
                            logger.error(
                                f"Error sending packet with timestamp `{metadata}`: {e}"
                            )
                    else:
                        logger.info("No data left, sending stop signal.")
                        try:
                            self._sock_ingest.sendall(b"END_STOP")
                            self._tx_complete.set()
                        except Exception as e:
                            logger.error(f"Error sending stop signal: {e}")
                        break
        logger.debug("data transmit thread lifecycle complete, closing socket")
        self._sock_ingest.close()

    def term_listen(self):
        """thread task that listens for external termination signal"""
        term_msg = self._recv_all(self._sock_bmi, 10)
        if term_msg and term_msg.startswith(b"BEGIN STOP"):
            logger.info("Received termination signal")
            self._term_flag.set()

    def run(self):
        '''spawns thread pool'''
        for thread in self._thread_pool:
            thread.start()
        for thread in self._thread_pool:
            thread.join()


class SpeakerGovernor(Thread):
    def __init__(self):
        super(SpeakerGovernor, self).__init__(self)
        self._cfg = RatballConfig()
        self._term_flag = Event()
        self.speaker = Speaker(0, self._cfg.audio.rate, self._cfg.speaker.block_size, self._cfg.buffer.framerate)

        self._sock_bmi = None
        self._init_socket()

        self._thread_pool = [
            # listen thread runs in background, daemonize to exit when enq/tx threads die
            Thread(target=self.listen, name="_speaker_listen", daemon=True),
        ]

    def _init_socket(self) -> None:
        # bmi tx/rx
        self._sock_bmi = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock_bmi.connect((self._cfg.bmi.ip, self._cfg.bmi.listen_port))
        self._sock_bmi.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock_bmi.sendall()

    def _recv_all(self, sock, size) -> bytes:
        """ensures that each packet is received"""
        data = b""
        while len(data) < size:
            packet = sock.recv(size - len(data))
            if not packet:
                return None
            data += packet
        return data

    def listen(self):
        '''thread task that listens for external frequency and termination signal'''
        self.speaker.start()
        term_msg = self._recv_all(self._sock_bmi, 10)
        # If the received message is the stop program indicator message
        if term_msg and term_msg.startswith(b"BEGIN STOP"):
            logger.info("Received termination signal")
            self.speaker.stop()
            self._term_flag.set()

        # if the received message is a normal frequency
        else:
            speaker_frequency = struct.unpack('>f', term_msg[:4])[0]
            # extra_bytes = term_msg[4:]
            # play given frequency
            self.speaker.set_frequency(speaker_frequency)

    def run(self):
        '''spawns thread pool'''
        for thread in self._thread_pool:
            thread.start()
        for thread in self._thread_pool:
            thread.join()


class CameraGovernor(Thread):
    def __init__(self):
        super(CameraGovernor, self).__init__(self)
        self._cfg = RatballConfig()
        self._tx_complete = Event()
        self._term_flag = Event()

        # capture_id is unique per experiment, but shared by each Camera
        capture_id = datetime.now().strftime("%y%m%d_%H%M")
        self._manifest = [Camera(ident, capture_id) for ident in self._cfg.camera.ident]

        self._sock_ingest = None
        self._sock_bmi = None
        self._init_sockets()


    def _init_sockets(self) -> None:
        # ingestor tx/rx
        self._sock_ingest = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock_ingest.connect(
            (self._cfg.ingestor.ip, self._cfg.ingestor.listen_port)
        )
        self._sock_ingest.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock_ingest.sendall()

        # bmi tx/rx
        self._sock_bmi = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock_bmi.connect((self._cfg.bmi.ip, self._cfg.bmi.listen_port))
        self._sock_bmi.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock_bmi.sendall()

    def _recv_all(self, sock, size) -> bytes:
        """ensures that each packet is complete before transmit"""
        data = b""
        while len(data) < size:
            packet = sock.recv(size - len(data))
            if not packet:
                return None
            data += packet
        return data

    def transmit(self):
        while not self._tx_complete.is_set():
            if not self._term_flag.is_set():
                for camera in self._manifest:
                    camera.start()

    def term_listen(self):
        term_msg = self._recv_all(self._sock_bmi, 10)
        if term_msg and term_msg.startswith(b"BEGIN STOP"):
            logger.info("Received termination signal")
            self._term_flag.set()

    def run(self):
        pass


def init_logger():
    # remove default log handler
    logger.remove()

    # log to both stderr/console and a rotating+compressed log file (capped at 200 MB)
    logger.add(
        sys.stderr,
        format="{time} | <level><bold>{level}</></> | <cyan>{thread}</> | <red>{exception}</> | {message}",
    )
    logger.add(RatballConfig().data_paths.logs, rotation="200 MB", compression="zip")


def main():
    init_logger()

    sensor_gov = SensorGovernor()
    sensor_gov.run()

    speaker_gov = SpeakerGovernor()
    speaker_gov.run()

    camera_gov = CameraGovernor()
    camera_gov.run()


if __name__ == "__main__":
    main()
