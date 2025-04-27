import socket
import struct
import sys

from camera import Camera


HOST = "192.168.0.11"
PORT = 10_000


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


cam0 = Camera(sensor_id=0, width=1280, height=720, framerate=30)
cam1 = Camera(sensor_id=1, width=1280, height=720, framerate=30)

# cam0.start()
# cam1.start()

capture_active = False
try:
    # while True:
    with socket.create_connection((HOST, PORT), timeout=5) as sock:
        print(f"Connected to {HOST}:{PORT}")
        # with socket.create_connection((HOST, PORT), timeout=5) as sock:
        sent_frames = 0
        while True:
            #            for idx, cam in enumerate((cam0, cam1)):
            #                bufdata = cam.drain()
            #                sent_frames = 0
            #                for frame_bytes, ts in bufdata:
            #                    print(f"{ts} | Send cam{idx} frame -> {len(frame_bytes)}b")
            #                    print(f"            cam{idx} buffer items: {len(cam._buffer)}")
            #                    send_frame(sock, cam.sensor_id, frame_bytes, ts)
            #                    sent_frames += 1
            #                    print(f"\nTotal frames sent:\t{sent_frames}\n\n")

            for idx, cam in enumerate((cam0, cam1)):
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
                        print("Got no frame data :(")

            capture_active = True

except (KeyboardInterrupt, BrokenPipeError):
    print("\nShutting down gracefully…", file=sys.stderr)

finally:
    cam0.stop()
    cam1.stop()
