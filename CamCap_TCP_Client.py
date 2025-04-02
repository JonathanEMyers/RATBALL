 # 
 # File: CamCap_Client_V2.0.py
 # Copy: Copyright (c) 2025 Tyler C. Brasher
 # BlazerID: brashert
 # Desc: Script to capture frames from two CSI cameras and stream it over TCP/IP
 # 


import cv2 # computer vision library
import time # manipulation of time
import socket # Networking library
import struct #  s t r u c t u r e s
import threading # make the CPU not panic
from datetime import datetime # part 2 electric boogaloo

# Server configuration 
SERVER_IP = "192.168.2.57"  # Change this to the remote machine's IP
SERVER_PORT = 10000

capture_done = False

# Capture settings
framerate = 30
# buffer_switch_time = 10  # Switch buffers every 10 seconds

# Define camera pipeline
def gstreamer_pipeline(sensor_id=0, width=1280, height=720):
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), width={width}, height={height}, format=NV12, framerate={framerate}/1 ! "
        f"nvvidconv flip-method=0 ! "
        f"video/x-raw, width={width}, height={height}, format=BGRx ! "
        f"videoconvert ! video/x-raw, format=BGR ! appsink"
    )

# Initalize both cameras
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

frame_queue = []  # Shared queue for frames
data_lock = threading.Lock()

def send_frames():
    global capture_done
    while not capture_done or frame_queue:
        with data_lock:
            if frame_queue:
                frame_data = frame_queue.pop(0)
            else:
                frame_data = None

        if frame_data:
            try:
                size = struct.pack(">L", len(frame_data))
                client_socket.sendall(size)
                client_socket.sendall(frame_data)
                print(f"Sent frame of size {len(frame_data)} bytes")
            except Exception as e:
                print(f"Error sending frame: {e}")
                break
        else:
            time.sleep(0.01)  # Small sleep to avoid busy-waiting


# Function to capture frames in its own thread
def capture_frames():
    global capture_done
    start_time = time.perf_counter()
    frame_count = 0
    fps = framerate
    duration = 10  # Capture for 10 seconds
    frame_interval = 1 / fps

    while time.perf_counter() - start_time < duration:
        frame_start = time.perf_counter()
        ret0, frame0 = cap0.read()
        ret1, frame1 = cap1.read()

        if not (ret0 and ret1):
            print("Error: Failed to grab frame from one or both cameras.")
            break

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.%f")[:-3]
        cv2.putText(frame0, timestamp, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
        cv2.putText(frame1, timestamp, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

        # Flatten the arrays into raw bytes
        cam0_bytes = frame0.tobytes()
        cam1_bytes = frame1.tobytes()

        # Metadata: Shape and data type for each frame
        cam0_meta = f"{frame0.shape}*{frame0.dtype.name}\n"
        cam1_meta = f"{frame1.shape}*{frame1.dtype.name}\n"
        # print(f"Cam0 Meta before encode: '{cam0_meta}'")
        # print(f"Cam1 Meta before encode: '{cam1_meta}'")

        metadata = (cam0_meta + cam1_meta).encode('utf-8')
        print(f"Encoded meta: '{metadata}'")
        meta_size = 256 # fixed for now, will likely move to config
        metadata = metadata.ljust(meta_size, b' ') # add padding
        print(f"padded metadata: '{metadata}'")

        # Package the data together for transmission
        frame_data = metadata + cam0_bytes + cam1_bytes


        with data_lock:
            frame_queue.append(frame_data)
        
        print(f"Captured frame {frame_count}")  # Debug print

        frame_count += 1
        elapsed_time = time.perf_counter() - frame_start
        sleep_time = max(0, frame_interval - elapsed_time)
        time.sleep(sleep_time)

    capture_done = True


# Start frame capture in a separate thread
capture_thread = threading.Thread(target=capture_frames, daemon=True)
capture_thread.start()


# Start sender thread after some delay to ensure frames are captured
time.sleep(1)  # Allow some frames to be captured
sender_thread = threading.Thread(target=send_frames, daemon=True)
sender_thread.start()

# Keep main thread alive
capture_thread.join()
sender_thread.join()

client_socket.close()
cap0.release()
cap1.release()
cv2.destroyAllWindows()
print("Finished streaming frames.")
