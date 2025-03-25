 # 
 # File: CamCap_TCP_Client.py
 # Copy: Copyright (c) 2025 Tyler C. Brasher
 # BlazerID: brashert
 # Desc: Script to capture frames from two CSI cameras and stream it over TCP/IP
 # 

import cv2 # computer vision library
import time # manipulation of time
import os # interface with operating system
import socket # Networking library
import struct #  s t r u c t u r e s
import zlib # data compression for easy data transmission
import threading # make the CPU not panic
from datetime import datetime # part 2 electric boogaloo

# Server configuration 
SERVER_IP = "192.168.2.57"
SERVER_PORT = 10000

# Capture settings
framerate = 30
buffer_switch_time = 5  # Switch buffers every 10 seconds

# Define camera pipeline
def gstreamer_pipeline(sensor_id=0, width=1280, height=720):
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), width={width}, height={height}, format=NV12, framerate={framerate}/1 ! "
        f"nvvidconv flip-method=0 ! "
        f"video/x-raw, width={width}, height={height}, format=BGRx ! "
        f"videoconvert ! video/x-raw, format=BGR ! appsink"
    )

# Initialize cameras
cap0 = cv2.VideoCapture(gstreamer_pipeline(sensor_id=0), cv2.CAP_GSTREAMER)
cap1 = cv2.VideoCapture(gstreamer_pipeline(sensor_id=1), cv2.CAP_GSTREAMER)

if not (cap0.isOpened() and cap1.isOpened()):
    print("Error: Could not open one or both cameras.")
    cap0.release()
    cap1.release()
    exit()

# Connect to server
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((SERVER_IP, SERVER_PORT))
print(f"Connected to server at {SERVER_IP}:{SERVER_PORT}")

# Buffer initialization
buffer_a = []
buffer_b = []
active_buffer = buffer_a
buffer_lock = threading.Lock()
buffer_ready = threading.Event()
stop_event = threading.Event()  # Event to stop everything
flush_event = threading.Event()  # Event to signal buffer flush

# Function to capture frames
def capture_frames():
    global active_buffer
    frame_interval = 1 / framerate

    while not stop_event.is_set():
        start_time = time.perf_counter()
        while (time.perf_counter() - start_time < buffer_switch_time) and not stop_event.is_set():
            frame_start = time.perf_counter()
            ret0, frame0 = cap0.read()
            ret1, frame1 = cap1.read()

            if not (ret0 and ret1):
                print("Error: Failed to grab frame from one or both cameras.")
                stop_event.set()
                break

            # Time stamp overlay to frames
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.%f")[:-3]
            cv2.putText(frame0, timestamp, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
            cv2.putText(frame1, timestamp, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)


            # Flatten the arrays into raw bytes
            cam0_bytes = frame0.tobytes()
            cam1_bytes = frame1.tobytes()

            # Compress the raw data for transmission
            cam0_compressed = zlib.compress(cam0_bytes)
            cam1_compressed = zlib.compress(cam1_bytes)

            # Metadata: Shape and data type for each frame
            cam0_meta = f"{frame0.shape},{frame0.dtype.name}\n"
            cam1_meta = f"{frame1.shape},{frame1.dtype.name}\n"

            metadata = (cam0_meta + cam1_meta).encode('utf-8')
            meta_size = 256 # fixed for now, will likely move to config
            metadata = metadata.ljust(meta_size, b' ') # add padding

            # header for sizes of the data
            header = struct.pack(">LL", len(cam0_compressed), len(cam1_compressed))

            # message: header + metadata + frames
            message = header + metadata + cam0_compressed + cam1_compressed

            # Append to buffer
            with buffer_lock:
                active_buffer.append(message)

            elapsed_time = time.perf_counter() - frame_start
            time.sleep(max(0, frame_interval - elapsed_time))

        # Swap buffers
        with buffer_lock:
            if active_buffer is buffer_a:
                active_buffer = buffer_b
            else:
                active_buffer = buffer_a
            buffer_ready.set()  # Signal sender thread

    print("Capture thread exiting...")
    flush_event.set()  # Signal sender to flush remaining frames

# Function to send frames
def send_frames():
    while not stop_event.is_set() or buffer_ready.is_set() or flush_event.is_set():
        buffer_ready.wait()  # Wait for a full buffer or stop signal

        with buffer_lock:
            if active_buffer is buffer_a:
                send_buffer = buffer_b[:]
                buffer_b.clear()
            else:
                send_buffer = buffer_a[:]
                buffer_a.clear()
            buffer_ready.clear()  # Reset signal

        # Send all frames in the buffer
        for message in send_buffer:
            try:
                size = struct.pack(">L", len(message))
                client_socket.sendall(size)
                client_socket.sendall(message)
            except Exception as e:
                print(f"Error sending frame: {e}")
                stop_event.set()
                return

    print("Sender thread exiting...")

# Function to listen for STOP command from server
def listen_for_stop():
    while not stop_event.is_set():
        msg = client_socket.recv(1024)
        if not msg:
            break  # Connection closed
        msg = msg.decode().strip()
        if "STOP" in msg:  # In case multiple messages are received
            print("Received STOP command from server.")
            stop_event.set()
            buffer_ready.set()  
            flush_event.set()  
            break


# Start threads
stop_listener_thread = threading.Thread(target=listen_for_stop, daemon=True)
capture_thread = threading.Thread(target=capture_frames, daemon=True)
sender_thread = threading.Thread(target=send_frames, daemon=True)

stop_listener_thread.start()
capture_thread.start()
sender_thread.start()

# Wait for threads to complete
stop_listener_thread.join()
capture_thread.join()
flush_event.set()  # Signal sender to flush remaining frames
buffer_ready.set()  # Ensure sender finishes remaining frames
sender_thread.join()

# Cleanup
client_socket.close()
cap0.release()
cap1.release()
cv2.destroyAllWindows()
print("Finished streaming frames.")


