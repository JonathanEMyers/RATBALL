import socket
import struct
import sys

from datetime import datetime
from os import makedirs
from camera import Camera

tmp_should_stream = False

HOST = "192.168.0.11"
PORT = 10_000
OUTPUT_DIR = f"/mnt/extended/data_capture/camera/{datetime.now().strftime('%Y-%m-%d')}"

makedirs(OUTPUT_DIR, exist_ok=True)

def _send_all(sock: socket.socket, data: bytes) -> None:
    """Reliable send that keeps calling send() until *data* is drained."""
    view = memoryview(data)
    while view:
        n_sent = sock.send(view)
        view = view[n_sent:]


def send_frame(sock: socket.socket, cam_id: int, frame: bytes, ts: bytes) -> None:
    """
    TCP frame format
    ----------------
    uint8   camera_id
    uint32  payload_len     (frame length in bytes, network byte-order)
    uint64  timestamp       (packed IEEE-754 ms-since-epoch; already 8 bytes)
    bytes   payload         (raw GRAY8 image bytes)
    """
    header = struct.pack("!BIQ", cam_id, len(frame), ts)
    _send_all(sock, header + frame)

cam_kwargs = {
    'width': 1280,
    'height': 720,
    'output_dir': OUTPUT_DIR,
    'framerate': 30
}

camera_manifest = (
    Camera(0, **cam_kwargs),
    Camera(1, **cam_kwargs),
)

capture_active = False
try:
    if tmp_should_stream:
        with socket.create_connection((HOST, PORT), timeout=5) as sock:
            print(f"Connected to {HOST}:{PORT}")
            sent_frames = 0
            while True:
                for idx, cam in enumerate(camera_manifest):
                    if not capture_active:
                        cam.start()
                    data = cam.pop()
                    if data is not None:
                        frame_bytes, ts = data
                        print(f"{ts} | Send cam{idx} frame -> {len(frame_bytes)}b")
                        print(f"            cam{idx} buffer items: {len(cam._buffer)}")
                        send_frame(sock, cam.sensor_id, frame_bytes, ts)
                        sent_frames += 1
                        print(f"\nTotal frames sent:\t{sent_frames}\n\n")
                    else:
                        if capture_active:
                            print("No frame data received")

                capture_active = True
    else:
        for idx, cam in enumerate(camera_manifest):
            if not capture_active:
                cam.start()
        capture_active = True


except (KeyboardInterrupt, BrokenPipeError):
    print("\nShutting down gracefully…", file=sys.stderr)

finally:
    for cam in camera_manifest:
        cam.stop()


