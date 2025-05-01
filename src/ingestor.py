from __future__ import annotations
from operator import itemgetter

import socket
import struct
import sys
import time

from loguru import logger
from queue import PriorityQueue
from collections import deque
from typing import Deque
from dataclasses import dataclass
from threading import Thread, Event
from .config import RatballConfig
from .utils import safe_unwrap_exception


# RATBALL Ingestor Server
# Responsible for consuming and handling socket transfers from RATBALL client:
#  - Odometry sensor data -> redirects to CSV files
#  - Camera image data    -> outputs still frames and/or chunked video to storage
#
# Also listens for termination signal from BMI server, upon which:
#  - Socket connections are closed and other transient system resources are freed
#  - Data file post-processing may be performed (i.e. chunked video collation, frame decomposition, CSV data statistics, etc.)
# 
# Inbound connections are accepted on a single port, then per-device socket listeners are
# negotiated following successful receipt of the following salutory payload:
#
# Client Hello payload:
# | ---- device type ---- | ---- device ident ---- | --- timestamp --- | (18B)
#
# Device sockets are placed into a priority queue and handled round-robin according to timestamp.

#client_hello_binfmt = ">6sId"
#client_hello_len = struct.calcsize(client_hello_binfmt)

server_handshake_binfmt = ">H"
server_handshake_len = struct.calcsize(server_handshake_binfmt)

# immutable descriptor object for device connection data
@dataclass(frozen=True, slots=True)
class DeviceGovernorConnection:
    device_type: str
    ident: int
    created_ts: float
    sock: socket.socket

    # implement to make instances subscriptable:
    def __getitem__(self, item):
        return getattr(self, item)


class IngestorService:
    def __init__(self):
        super().__init__()
        self._cfg = RatballConfig()

        self._gateway_sock: socket.socket = None
        self._next_device_port: int = self._cfg.ingestor.data_port_range_start
        self._init_gateway_socket()

        # priority queue of inbound device connections
        self.connection_pool = PriorityQueue()

        self._rx_complete = Event()
        self._term_flag = Event()

        # begin with one listener thread; thread pool will grow with # of clients
        self._thread_pool = [
            Thread(target=self.queue_inbound_clients, name="_lst_client_"),
#            Thread(target=self.consume_camera_feed, name="_rx_camera_"),
#            Thread(target=self.consume_sensor_feed, name="_rx_sensor_"),
        ]
        self.sensor_data: Deque = deque()


    def _init_gateway_socket(self):
        """Initialize the gateway socket and begin listening for client connections"""
        try:
            self._gateway_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._gateway_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._gateway_sock.bind((
                '',
                self._cfg.ingestor.gateway_port,
            ))
            self._gateway_sock.listen()
        except socket.error as ex:
            exmsg = safe_unwrap_exception(ex)
            logger.error(f"Socket error occurred while reinitializing gateway socket: {exmsg}")

    def _get_next_device_port(self):
        """Return the next available data port number, then increment it"""
        port = self._next_device_port
        self._next_device_port += 1
        return port

    def _recv_client_hello(self, conn: socket.socket) -> bytes:
        client_hello_len = struct.calcsize(
            self._cfg.ingestor.client_hello_binfmt
        )
        try:
            payload = conn.recv(client_hello_len)
            if not payload:
                raise Exception("Got empty payload for client hello packet")
            return payload
        except Exception as ex:
            exmsg = ex.message if hasattr(ex, 'message') else ex
            logger.error(f"Exception occurred while accepting new connection: {exmsg}")

    def _unpack_client_hello(self, hello: bytes) -> Tuple[str, int, float]:
        try:
            return struct.unpack(
                self._cfg.ingestor.client_hello_binfmt,
                hello
            )
        except Exception as ex:
            exmsg = ex.message if hasattr(ex, 'message') else ex
            logger.critical(f"Exception occurred while unpacking client hello payload: {exmsg}")

    def _accept_new_conn(self):
        """Accept device connection, assign that device a socket in a priority queue, then send handshake to client"""
        conn, addr = self._gateway_sock.accept()
        logger.info(f"Connection from: {addr}")

        hello = self._recv_client_hello(conn)
        if hello is not None:
            device_enc, ident, ts = self._unpack_client_hello(hello)
            device = device_enc.decode("ascii")
            logger.info(f"Got client hello from device {device}{ident}, ts={ts}")
            dt = time.time()*1000 - ts

            # create and bind a new socket at a precomputed port
            assigned_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            assigned_socket.bind(('', self._get_next_device_port()))
            assigned_socket.listen()

            # place the device descriptor + assigned socket into queue
            self.connection_pool.put(
                (
                    # prioritize according to delta w/ incoming connection timestamp
                    int(dt),
                    DeviceGovernorConnection(
                        device,
                        ident,
                        ts,
                        assigned_socket,
                    )
                )
            )

            if device == 'sensor':
                logger.info(f"Adding new thread to thread pool for sensor{ident}, ts={ts}")
                t = Thread(target=self.consume_sensor_feed, name=f"_rx_sensor_{len(self._thread_pool)}_", daemon=True)
                self._thread_pool.append(t)
                t.start()
            if device == 'camera':
                logger.info(f"Adding new thread to thread pool for camera{ident}, ts={ts}")
                t = Thread(target=self.consume_camera_feed, name=f"_rx_camera_{len(self._thread_pool)}_", daemon=True)
                self._thread_pool.append(t)
                t.start()

            # send handshake w/ permanent port to the client to use for all further transactions
            conn.send(
                struct.pack(server_handshake_binfmt, assigned_socket.getsockname()[1])
            )

            # clean up and reset for new client connections
            conn.close()
            self._init_gateway_socket()
        else:
            logger.warning(f"Did not receive hello packet from client at {addr}")

    def queue_inbound_clients(self):
        logger.info("Listening for inbound clients to queue")
        while True:
            self._accept_new_conn()

    def consume_camera_feed(self):
        pass

    def _recv_sensor_data(self, conn):
        data_pkt_size = struct.calcsize(self._cfg.sensor.binfmt)

        # keep receiving data for the lifetime of the thread
        while True:
            sensor_data_bin = sock.recv(data_pkt_size)
            ts, x, y, h, idx = struct.unpack(
                self._cfg.sensor.binfmt,
                sensor_data_bin,
            )
            payload = SensorPacketPayload(ts, x, y, h, idx)
            self.sensor_data.append(payload)


    def consume_sensor_feed(self):
        while True:
            if not self.connection_pool.empty():
                # pop prioritized connection from PriorityQueue, unpack tuple
                prio, device_connection = self.connection_pool.get()

                # unpack device descriptor fields from DeviceGovernorConnection
                device_type, ident, created_ts, sock = itemgetter('device_type', 'ident', 'created_ts', 'sock')(
                    device_connection
                )
                # reprioritize with a new timestamp
                dt = time.time()*1000 - created_ts
                # if the device isn't what we're looking for, reprioritize and re-enqueue it
                if device_type != 'sensor':
                    self.connection_pool.put(
                        (
                            # prioritize according to delta w/ incoming connection timestamp
                            int(dt),
                            DeviceGovernorConnection(
                                device,
                                ident,
                                ts,
                                assigned_socket,
                            )
                        )
                    )

                # if it is, accept connection on socket and begin reading to CSV
                else:
                    conn, addr = sock.accept()
                    self._recv_sensor_data(conn)



        pass

    def start(self):
        for thread in self._thread_pool:
            thread.start()
        for thread in self._thread_pool:
            thread.join()

    def stop(self):
        pass
