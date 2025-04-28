import socket
import struct
import time
from os import path
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

HDRSIZE = 13
def recv_img(conn) -> Tuple[Optional[bytes], Optional[int], Optional[int], Optional[int]]:
    hdr_data = b""
    # Observe application header without draining socket:
    header_frag = conn.recv(HDRSIZE, socket.MSG_PEEK)
    if not header_frag:
        return (None, None, None, None)
    cam_id, frame_sz, sent_ts = struct.unpack("!BIQ", header_frag)

    recv_ts = time.perf_counter_ns()
    if frame_sz == 0:
        return (None, cam_id, frame_sz, recv_ts)
    img_bytes = b""
    consumed_header = False
    while len(img_bytes) < frame_sz:
        offset = HDRSIZE if not consumed_header else 0
        payload = conn.recv(offset + frame_sz - len(img_bytes))
        if not consumed_header:
            payload = payload[HDRSIZE:]
            consumed_header = True
        if not payload:
            return (None, cam_id, frame_sz, recv_ts)
        img_bytes += payload

    return (img_bytes, cam_id, sent_ts, recv_ts)


def normalize_path(p):
    return path.join(*p.split('/'))


def handle_client(conn, addr, img_dir = 'images'):
    count = 0
    try:
        while True:
            count = count + 1
            print (f'Client connected: {addr}')

            data, *meta = recv_img(conn)

            if data is not None:
                pil_img = Image.frombytes('L', (1280, 720), data)
                img_name = f"f{str(count)}_cam{meta[0]}_txTS{meta[1]}_rxTS{meta[2]}"
                dst = normalize_path(f"{img_dir}/{img_name}.png")
                pil_img.save(dst)
                print(f"Saved image: {dst}")
            else:
                print("Got empty data")
    finally:
        count = 0
        conn.close()
        print("Connection closed")


# not certain this is necessary, but good to know:
def set_keepalive_linux(sock, after_idle_sec=1, interval_sec=3, max_fails=5):
    """Set TCP keepalive on an open socket.

    It activates after 1 second (after_idle_sec) of idleness,
    then sends a keepalive ping once every 3 seconds (interval_sec),
    and closes the connection after 5 failed ping (max_fails), or 15 seconds
    """
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, after_idle_sec)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, interval_sec)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, max_fails)


def start_server(host = '0.0.0.0', port = 10000):
    srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv_sock.bind((host, port))
    srv_sock.listen()
    set_keepalive_linux(srv_sock)

    while True:
        conn, addr = srv_sock.accept()
        handle_client(conn, addr)

if __name__ == '__main__':
    start_server()

