 # 
 # File: CamCapRaw_TCP_Server.py
 # Copy: Copyright (c) 2025 Tyler C. Brasher
 # BlazerID: brashert
 # Desc: Server for Jetson camera streaming over TCP/IP
 # 


import socket # Networking library
import struct #  s t r u c t u r e s
import zlib # data compression for easy data transmission
import threading # make the CPU not panic
import os # interface with operating system
import cv2 # Computer Vision Library
import numpy as np # n u m p y

# Server configuration
HOST = "192.168.2.57"  # Listen on all network interfaces
PORT = 10000
SAVE_DIR = "captured_frames"

if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

frame_counter = 0
stop_event = threading.Event()

def receive_full_data(conn, size):
    data = b""
    while len(data) < size:
        packet = conn.recv(size - len(data))
        if not packet:
            return None
        data += packet
    return data

def handle_client(conn, addr):
    global frame_counter
    print(f"Connected to {addr}")
    try:
        while not stop_event.is_set():
            header_size = 8 # 4 bytes per camera, total of 8
            header = receive_full_data(conn, header_size)
            if not header:
                print("[-] Connection closed by Jetson")
                break

            cam0_size, cam1_size = struct.unpack(">LL", header)
            print(f"Expecting cam0 frame size: {cam0_size} bytes, cam1 size: {cam1_size} bytes")

            # Take in metadata from Jetson
            meta_size = 256 # based on expected metadata length
            meta_data = receive_full_data(conn, meta_size)
            if not meta_data:
                print("[-] Metadata not received!")
                break

            try:
                print({meta_data})
                meta_str = meta_data.decode('utf-8').strip()
            except UnicodeDecodeError as e:
                print(f"metadata decoding error: {e}")
                break
            lines = meta_str.split('\n')

            # Take in shape and data type for frames
            cam0_shape_str, cam0_dtype = lines[0].split(',')
            cam1_shape_str, cam1_dtype = lines[1].split(',')

            cam0_shape = tuple(map(int, cam0_shape_str.strip('()').split(',')))
            cam1_shape = tuple(map(int, cam1_shape_str.strip('()').split(',')))

            print(f"meta cam0: shape={cam0_shape}, datatype={cam0_dtype}")
            print(f"meta cam0: shape={cam1_shape}, datatype={cam1_dtype}")

            # Take in compressed frame data
            cam0_compressed = receive_full_data(conn, cam0_size)
            cam1_compressed = receive_full_data(conn, cam1_size)

            # Decompress the data
            cam0_raw = zlib.decompress(cam0_compressed)
            cam1_raw = zlib.decompress(cam1_compressed)

            # convert raw back into numpy arrays
            cam0_frame = np.frombuffer(cam0_raw, dtype=cam0_dtype).reshape(cam0_shape)
            cam1_frame = np.frombuffer(cam1_raw, dtype=cam1_dtype).reshape(cam1_shape)

            # Save frames
            cam0_raw_filename = os.path.join(SAVE_DIR, f"cam0_frame_{frame_counter}.raw")
            cam1_raw_filename = os.path.join(SAVE_DIR, f"cam1_frame_{frame_counter}.raw")

            cam0_frame.tofile(cam0_raw_filename)
            cam1_frame.tofile(cam1_raw_filename)

            print(f"Saved frame {frame_counter} to disk")


            frame_counter += 1
    
    except Exception as e:
        print(f"Error with {addr}: {e}")
    finally:
        frame_counter = 0
        print(f"Connection closed: {addr}")
        conn.close()

def send_stop_command():
    """ Send a STOP command to the connected client. """
    print("Sending STOP command to client...")
    try:
        stop_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        stop_socket.connect((HOST, PORT))
        stop_socket.sendall(b"STOP")
        stop_socket.close()
    except Exception as e:
        print(f"Error sending STOP command: {e}")

def user_input_listener():
    """ Listen for user input in a separate thread. """
    global stop_event
    while True:
        user_input = input("Enter 'STOP' to stop the client: ")
        if user_input.strip().upper() == "STOP":
            stop_event.set()
            send_stop_command()
            stop_event.clear()  # Reset event to allow new connections

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"Server listening on {HOST}:{PORT}")

    threading.Thread(target=user_input_listener, daemon=True).start()

    while True:
        conn, addr = server_socket.accept()
        stop_event.clear()  # Ensure stop event is cleared before handling a new client
        client_thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        client_thread.start()

if __name__ == "__main__":
    start_server()

