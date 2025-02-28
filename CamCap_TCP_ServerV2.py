 # 
 # File: CamCap_TCP_Server.py
 # Copy: Copyright (c) 2025 Tyler C. Brasher
 # BlazerID: brashert
 # Vers: 1.0.0 02/13/2025 TCB - Original Coding
 # Desc: Server for Jetson camera streaming over TCP/IP
 # 


import socket # Networking library
import struct #  s t r u c t u r e s
import pickle # object serialization
import threading # make the CPU not panic
import os # interface with operating system

# Server configuration
HOST = "192.168.2.57"  # Listen on all network interfaces
PORT = 10000
SAVE_DIR = "captured_frames"

# Ensure save directory exists
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

frame_counter = 0  # Global frame counter

def receive_full_data(conn, size):
    """ Ensure full data is received from the socket. """
    data = b""
    while len(data) < size:
        packet = conn.recv(min(4096, size - len(data)))  # Don't read past needed size
        if not packet:
            return None  # Client disconnected
        data += packet
    return data

def handle_client(conn, addr):
    global frame_counter
    print(f"Connected to {addr}")
    try:
        while True:
            # Receive the 4-byte frame size header
            packed_msg_size = receive_full_data(conn, 4)
            if not packed_msg_size:
                break  # Client disconnected

            msg_size = struct.unpack(">L", packed_msg_size)[0]
            print(f"Expecting frame size: {msg_size} bytes")

            # Receive the actual frame data
            data = receive_full_data(conn, msg_size)
            if not data:
                break  # Client disconnected

            # Deserialize the received frame
            try:
                frame_dict = pickle.loads(data)
            except pickle.UnpicklingError:
                print("Error: Corrupt frame received, skipping.")
                continue

            # Save frames
            for cam, encoded_frame in frame_dict.items():
                frame_path = os.path.join(SAVE_DIR, f"{cam}_{frame_counter}.jpg")
                with open(frame_path, "wb") as f:
                    f.write(encoded_frame)
                print(f"Saved frame {frame_counter} from {cam}")

            frame_counter += 1  # Increment frame count

    except Exception as e:
        print(f"Error with {addr}: {e}")
    finally:
        frame_counter = 0
        print(f"Connection closed: {addr}")
        conn.close()


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"Server listening on {HOST}:{PORT}")
    
    while True:
        conn, addr = server_socket.accept()
        client_thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        client_thread.start()

if __name__ == "__main__":
    start_server()

