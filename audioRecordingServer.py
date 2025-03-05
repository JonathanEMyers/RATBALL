import socket
import alsaaudio as aa
import threading

# Defining Networking Parameters
HOST = '127.0.0.1';
PORT = 36783;

# Defining Audio Parameters
channels = 1;
rate = 44100;
format = aa.PCM_FORMAT_S16_LE;
chunkSize = 882 * 2;
metadataSize = 26;

# Defining Frequency Stream Parameters
frequency = 200.0;

# Program Counter to Stop Program After X Seconds
stopCounter = 0;
stopProgram = False;

# Creating Server
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen()
print(f"Listening on {HOST}:{PORT}...")

conn, addr = server_socket.accept()
print(f"Connected by {addr}")

conn2, addr2 = server_socket.accept()
print(f"Connected by {addr2}")

# Was encountering some issues where recv was running too fast,
# and the metadata could not be decoded, so this is here to ensure
# that all data is recieved before attempting to encode
def recv_all(sock, size):
    data = b""
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            return None  # Handle closed connection
        data += packet
    return data


def audioClient():
    # Opening audio storage file
    with open("audioOne.raw", "wb") as fAudio:
        # Opening metadata storage file
        with open("audioOne.txt", "w") as fMeta:
            print("Opened file!")

            # Attempting to recieve TCP packets from jetson
            try:
                while True:

                    # Recieving entire packet
                    totalPacket = recv_all(conn, metadataSize + chunkSize)
                    if totalPacket is None:
                        print("Connection closed")
                        break

                    if totalPacket.startswith(b"STOP_TRANSMISSION"):
                        print("Recieved stopping transmission request!s")
                        conn.close()
                        conn2.close()
                        server_socket.close()
                        fAudio.close()
                        fMeta.close()
                        break
                    
                    # print(len(totalPacket))

                    metadata = totalPacket[:26].decode("utf-8")
                    data = totalPacket[26:]

                    fAudio.write(data)
                    fMeta.write(metadata + "\n")

                # print("Recieved and written!")
                    
                    # Legacy code from sending frequencies
                    # if(frequency < 500):
                    #     frequency = frequency + 1.0;
                    # else:
                    #     frequency = 200.0;

                    # s.sendall(struct.pack('!f', frequency));

            except KeyboardInterrupt:
                print("Stopping");
            finally:
                conn.close()
                conn2.close()
                server_socket.close()
                fAudio.close()
                fMeta.close()


def stoppingClient():
    while True:
        try:
            stop_signal = conn2.recv(4)
            if stop_signal:
                print("Stop signal received! Forwarding to audio client...")
                conn.sendall(stop_signal)  # Send stop signal to recording client
                break  # Stop listening after sending
        except:
            break

# Start threads to handle each client
audioThread = threading.Thread(target=audioClient, daemon=True)
stopThread = threading.Thread(target=stoppingClient, daemon=True)

audioThread.start()
stopThread.start()

# Keep server alive
try:
    while True:
        pass
except KeyboardInterrupt:
    print("Shutting down server.")
    server_socket.close()