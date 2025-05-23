import struct
import socket
import sys
from multiprocessing import Process, Queue, Event
from threading import Thread
from datetime import datetime
from loguru import logger

from .config import RatballConfig
from .sensor import Sensor
from .speaker import Speaker
from .camera import Camera
from .dataclasses import SensorPacketPayload

from .utils import unix_time_millis, safe_unwrap_exception

def build_client_hello(device_name: str, device_ident: int) -> bytes:
    try:
        device_name_enc = device_name.encode(encoding="ascii")
        if len(device_name_enc) != 6:
            logger.critical(f"Invalid length for encoded device name: {len(device_name_enc)}")
            raise Exception(f"Failed to build client hello for device {device_name} with ident {ident}")
        return struct.pack(">6sId", device_name_enc, device_ident, unix_time_millis(datetime.now()))
    except struct.error as ex:
        exmsg = safe_unwrap_exception(ex)
        logger.error(f"Struct error occurred while building client hello packet for device {device_name}{device_ident}: {exmsg}")
    except Exception as ex:
        exmsg = safe_unwrap_exception(ex)
        logger.error(f"Exception occurred while building client hello for device {device_name}{device_ident}: {exmsg}")



class SensorGovernor(Process):
    def __init__(self):
        # init governor thread superconstructor
        super().__init__()
        self._cfg = RatballConfig()
        # start thread events
        self._client_ready = Event()
        self._tx_complete = Event()
        self._term_flag = Event()

        self._manifest = None
        try:
            self._manifest = [Sensor(addr) for addr in self._cfg.sensor.i2c_addr]
        except Exception as ex:
            exmsg = safe_unwrap_exception(ex)
            logger.critical(
                f"Fatal exception occurred while building sensor manifest for I2C addresses {self._cfg.sensor.i2c_addr}: {exmsg}"
            )
            self._manifest = []

        self._sock_ingest = None
        self._sock_bmi = None

        self._init_sockets()
        self._client_handshake()

        # initialize sensor threads
        self._thread_pool = [
            Thread(target=self.enqueue, name="_sensor_enq_"),
            Thread(target=self.transmit_live, name="_sensor_tx_"),
            # listen thread runs in background, daemonize to exit when enq/tx threads die
            # Thread(target=self.term_listen, name="_sensor_lst_", daemon=True),
        ]

    def _init_sockets(self) -> None:
        '''sets up TCP connections using socket Python stdlib'''
        self._sock_ingest = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock_bmi = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # ingestor tx/rx
        try:
            self._sock_ingest.connect(
                (self._cfg.ingestor.ip, self._cfg.ingestor.gateway_port)
            )
            self._sock_ingest.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except socket.error as ex:
            exmsg = safe_unwrap_exception(ex)
            logger.error(f"Exception occurred while connecting to Ingestor: {exmsg}")

        # bmi tx/rx
        try:
            self._sock_bmi.connect((self._cfg.bmi.ip, self._cfg.bmi.listen_port))
            self._sock_bmi.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except socket.error as ex:
            exmsg = safe_unwrap_exception(ex)
            logger.error(f"Socket error occurred while connecting to BMI: {exmsg}")


    def _is_valid_data_port(self, portno: int):
        return self._cfg.ingestor.data_port_range_start <= int(portno) < self._cfg.ingestor.data_port_range_end

    def _client_handshake(self) -> None:
        for ident, _ in enumerate(self._manifest):
            try:
                self._sock_ingest.sendall(
                    build_client_hello('sensor', ident)
                )
            except socket.error as ex:
                exmsg = safe_unwrap_exception(ex)
                logger.error(f"Socket error occurred while sending hello packet to Ingestor for device sensor{ident}: {exmsg}")

            try:
                next_port_payload = self._sock_ingest.recv(
                    struct.calcsize(self._cfg.ingestor.handshake_binfmt)
                )
                try:
                    next_port = struct.unpack(self._cfg.ingestor.handshake_binfmt, next_port_payload)[0]
                except struct.error as ex:
                    exmsg = safe_unwrap_exception(ex)
                    logger.critical(f"Struct error occurred while unpacking Ingestor handshake port: {exmsg}")

                if self._is_valid_data_port(next_port):
                    logger.info(f"Got client handshake from Ingestor, sending sensor{ident} stream to port {next_port}")
                    self._sock_ingest.close()
                    self._sock_ingest = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self._sock_ingest.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    self._sock_ingest.connect(
                        (self._cfg.ingestor.ip, next_port)
                    )
                    self._client_ready.set()
                else:
                    logger.critical(f"Ingestor responded to client handshake with out-of-bounds destination port: {next_port}")
                    self._sock_ingest.close()
                    raise Exception("Ingestor stream connection could not be established, aborting")
            except socket.error as ex:
                exmsg = safe_unwrap_exception(ex)
                logger.error(f"Socket error occurred while receiving client handshake from Ingestor for sensor{ident}: {exmsg}")
            except Exception as ex:
                exmsg = safe_unwrap_exception(ex)
                logger.error(f"Exception occurred while receiving client handshake from Ingestor for sensor{ident}: {exmsg}")


    def _recv_all(self, sock, size) -> bytes:
        """ensures that each packet is complete before transmit"""
        try:
            data = b""
            while len(data) < size:
                packet = sock.recv(size - len(data))
                if not packet:
                    return None
                data += packet
            return data
        except socket.error as ex:
            exmsg = safe_unwrap_exception(ex)
            logger.error(f"Socket error occurred while attempting to receive BMI data")

    def _pack_sensor_data(self, payload) -> bytes:
        """marshals data into predefined binary struct"""
        ordered_payload = [payload.ts, payload.x, payload.y, payload.h, payload.idx]
        return struct.pack(
            self._cfg.sensor.binfmt,
            *ordered_payload,
        )

    def enqueue(self) -> None:
        '''thread task that pushes sensor data into deque buffers'''
        while not self._tx_complete.is_set():
            for sensor in self._manifest:
                sensor.poll_data()

    def transmit_live(self) -> None:
        '''thread task that pops sensor data from deque buffers and transmits via socket'''
        while not self._tx_complete.is_set():
            if not self._term_flag.is_set():
                for idx, sensor in enumerate(self._manifest):
                    metadata, data = sensor.get_next()
                    if data is not None:
                        payload = SensorPacketPayload(
                            metadata,
                            data[0].x,
                            data[0].y,
                            data[0].h,
                            idx,
                        )
                        logger.debug(f"Preparing to pack sensor data payload: {payload}")
                        packet = self._pack_sensor_data(payload)
                        if self._client_ready.is_set():
                            logger.info("Sensor{idx} got client ready signal, beginning data transmission")
                            try:
                                self._sock_ingest.sendall(packet)
                            except socket.error as ex:
                                exmsg = safe_unwrap_exception(ex)
                                logger.error(
                                    f"Socket error occurred while sending data packet for sensor{idx}: {exmsg}"
                                )
                    else:
                        logger.debug("No data received from sensor, skipping.")
                        break
        logger.info(f"Sensor data transmit thread lifecycle has completed, closing socket.")
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


class SpeakerGovernor(Process):
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


class CameraGovernor(Process):
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


