from __future__ import annotations

import struct
from queue import PriorityQueue
from dataclasses import dataclass
from threading import Thread, Event
from ..config import RatballConfig


# RATBALL Ingestor Server
# Responsible for consuming and handling socket transfers from RATBALL client:
#  - Odometry sensor data -> redirects to CSV files
#  - Camera image data    -> outputs still frames and/or chunked video to storage
#
# Also listens for termination signal from BMI server, upon which:
#  - Socket connections are closed and other transient system resources are freed
#  - Data file post-processing is performed (i.e. chunked video collation, frame decomposition, CSV data statistics, etc.)
# 
# Inbound connections are accepted on a single port, then per-device socket listeners are
# negotiated following successful receipt of the following salutory payload:
#
# Client Hello payload:
# | ---- device type ---- | ---- device ident ---- | --- timestamp --- | (18B)
#
# Device sockets are placed into a priority queue and handled round-robin according to timestamp.

client_hello_binfmt = ">6sid"
client_hello_len = struct.calcsize(client_hello_binfmt)

server_handshake_binfmt = ">H"
server_handshake_len = struct.calcsize(server_handshake_binfmt)

# immutable descriptor object for device connection data
@dataclass(frozen=True, slots=True)
class DeviceGovernorConnection:
    device_type: str
    ident: int
    created_ts: float
    socket: socket.socket

@dataclass(order=True)
class PrioritizedGvnrConn:
    priority: int
    item: DeviceGovernorConnection(compare=False)

class IngestorWorker(Thread):
    def __init__(self, *args, **kwargs):
        super(IngestorWorker, self).__init__(*args, **kwargs)
        self._cfg = RatballConfig()

        self._current_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # TODO: set up listener
        self._current_sock.bind((
            '0.0.0.0',
            8888,
        ))

        self._next_device_port = 42_000

        # priority queue of inbound device connections
        self.connection_pqueue = PriorityQueue()

        self._rx_complete = Event()
        self._term_flag = Event()

        self._thread_pool = [
            Thread(target=self.consume_camera_feed, name="_rx_camera_"),
            Thread(target=self.consume_sensor_feed, name="_rx_sensor_"),
        ]

    def get_next_device_port(self):
        port = self._next_device_port
        self._next_device_port += 1
        return port

    def _recv_client_hello(self, conn: socket.socket) -> bytes:
        try:
            hello = b""
            while len(hello) < client_hello_len:
                payload = sock.recv(client_hello_len - len(hello))
                if not payload:
                    return None
                hello += payload
            return hello
        except ex:
            logger.error(f"Exception occurred while accepting new connection: {ex}")

    def _unpack_client_hello(self, hello: bytes) -> Tuple[str, int, float]:
        try:
            return struct.unpack(hello)
        except error:
            logger.error(f"Failed to unpack client hello payload: {error}")
            pass


    def _accept_new_conn(self):
        """accepts device connections, assigns each device a socket in a priority queue, sends ack to client"""
        conn, addr = self._current_sock.accept()
        logger.info(f"Connection from: {addr}")

        hello = self._recv_client_hello(conn)
        if hello is not None:
            device, ident, ts = hello
            dt = time.now()*1000 - ts

            # create and bind a new socket at a precomputed port
            assigned_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            assigned_socket.bind(('0.0.0.0', self.get_next_device_port()))

            # place the device descriptor + assigned socket into queue
            self.connection_pool.put(
                PrioritizedGvnrConn(
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

            # send handshake w/ permanent port to the client to use for all further transactions
            conn.send(
                struct.pack(server_handshake_binfmt, assigned_socket.getsockname()[1])
            )
            # TODO: may not be needed with listen()
            conn.close()

            # TODO: renew entrypoint socket


    def _event_loop(self):
        pass


    def consume_camera_feed(self):
        pass

    def consume_sensor_feed(self):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def run(self):
        pass


