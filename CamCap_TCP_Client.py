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
import threading # make the CPU not panic
from datetime import datetime # part 2 electric boogaloo
import collections # Gotta collect them all! Nope, not how that phrase goes...

# Server configuration 
SERVER_IP = "192.168.2.57"
SERVER_PORT = 10000

# Capture settings
framerate = 30
buffer_switch_time = 10  # Switch buffers every 10 seconds
bufferSize = framerate * buffer_switch_time

# Define camera pipeline
def gstreamer_pipeline(sensor_id=0, width=1280, height=720):
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), width={width}, height={height}, format=NV12, framerate={framerate}/1 ! "
        f"nvvidconv flip-method=0 ! "
        f"video/x-raw, width={width}, height={height}, format=BGRx ! "
        f"videoconvert ! video/x-raw, format=GRAY8 ! appsink"
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
camBufferOne = collections.deque(maxlen=bufferSize)
# videoMetaBufferOne = collections.deque(maxlen=bufferSize)
camBufferTwo = collections.deque(maxlen=bufferSize)
# videoMetaBufferTwo = collections.deque(maxlen=bufferSize)

whichVideoBuffer = True     # True for bufferOne, False for bufferTwo
beginStop = False

# Function to capture frames
def capture_frames():
    global whichVideoBuffer
    global beginStop
    frame_interval = 1 / framerate

    while (not beginStop):
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
        print(timestamp)


        # Flatten the arrays into raw bytes
        cam0_bytes = frame0.tobytes()
        cam1_bytes = frame1.tobytes()

        # header for sizes of the data
        print(f"Packed cam0 frame size: {len(cam0_bytes)} bytes, cam1 size: {len(cam1_bytes)} bytes")

        message = cam0_bytes + cam1_bytes

        # whichVideoBuffer being true means stack up bufferOne and transmit from bufferTwo
        if(whichVideoBuffer == True):

            # Appending audio data and metadata to associated lists
            camBufferOne.append(message)
            # videoMetaBufferOne.append(timestamp)

            # Switching flag to indicate bufferOne is full
            if(len(camBufferOne) >= bufferSize):
                whichVideoBuffer = False

        # whichVideoBuffer being false means stack up bufferTwo and transmit from bufferOne
        elif(whichVideoBuffer == False):

            # Appending audio data and metadata to associated lists
            camBufferTwo.append(message)
            # videoMetaBufferTwo.append(timestamp)
            
            # Switching flag to indicate bufferTwo is full
            if(len(camBufferTwo) >= bufferSize):
                whichVideoBuffer = True

        else:
            print("In audioRecordingClient.recordAudio() -- Unsupported flag value!")

        elapsed_time = time.perf_counter() - frame_start
        time.sleep(max(0, frame_interval - elapsed_time))
        print(len(camBufferOne))
        print(len(camBufferTwo))
        print(whichVideoBuffer)

    print("Capture thread exiting...")
    flush_event.set()  # Signal sender to flush remaining frames

# Function to send frames
def send_frames():
    global whichVideoBuffer
    global beginStop
    endStop = False
    isVideoData = True
    while (not endStop):


        # Getting video data -- Get data out of buffer one first, then two
        if(not whichVideoBuffer and len(camBufferOne) > 0):
            videoData = camBufferOne.popleft()
            # videoMetadata = videoMetaBufferOne.popleft()
            isVideoData = True
        elif(whichVideoBuffer and len(camBufferTwo) > 0):
            videoData = camBufferTwo.popleft()
            # videoMetadata = videoMetaBufferTwo.popleft()
            isVideoData = True
        else:
            videoData = bytearray(1280 * 720 * 1) + bytearray(1280 * 720 * 1)   # In case there is no more video data but there is still audio data
            # videoMetadata = bytearray(videoMetaSize)
            isVideoData = False

        # Send all frames in the buffer
        if (isVideoData):
            try:
                size = struct.pack(">L", len(videoData))
                client_socket.sendall(videoData)
            except Exception as e:
                print(f"Error sending frame: {e}")
                stop_event.set()
                return

    print("Sender thread exiting...")

def recieveStop():
    global beginStop

    print("In audioRecordingClient.recieveStop() -- Stopping thread is executing.")


    while(not beginStop):
        message = recvAll(BMIConn, 10)

        if(message.startswith(b'BEGIN_STOP')):
            print("In audioRecordingClient.recieveStop() -- Received beginStop trigger!")
            beginStop = True
        else:
            extraBytes = message[4:]


# Start threads
stoppingThread = threading.Thread(target=recieveStop, daemon=True)
capture_thread = threading.Thread(target=capture_frames, daemon=True)
sender_thread = threading.Thread(target=send_frames, daemon=True)

stoppingThread.start()
capture_thread.start()
sender_thread.start()

# Wait for threads to complete
stoppingThread.join()
capture_thread.join()
sender_thread.join()

# Cleanup
client_socket.close()
cap0.release()
cap1.release()
cv2.destroyAllWindows()
print("Finished streaming frames.")


