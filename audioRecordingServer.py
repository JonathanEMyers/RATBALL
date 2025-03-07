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

# Flags to begin and end stopping program
beginStop = False;
endStop = False;

# Creating Server
serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
serverSocket.bind((HOST, PORT))
serverSocket.listen()
print(f"In audioRecordingServer -- Listening on {HOST}:{PORT}...")

# Accepting connection to audio recording client
conn, addr = serverSocket.accept()
print(f"In audioRecordingServer -- Connected by {addr}")

# Accepting connection to stop program client
conn2, addr2 = serverSocket.accept()
print(f"In audioRecordingServer -- Connected by {addr2}")

# Was encountering some issues where recv was running too fast,
# and the metadata could not be decoded, so this is here to ensure
# that all data is recieved before attempting to encode
def recvAll(sock, size):
    data = b""
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            return None  # Handle closed connection
        data += packet
    return data


def audioClient():
    global endStop

    # Opening audio storage file
    with open("audioOne.raw", "wb") as fAudio:

        # Opening metadata storage file
        with open("audioOne.txt", "w") as fMeta:
            print("In audioRecordingServer.audioClient() -- Opened files!")

            # Attempting to recieve TCP packets from jetson
            while(not endStop):

                # Recieving entire packet
                totalPacket = recvAll(conn, metadataSize + chunkSize)

                # Packet not recieved
                if(totalPacket is None):
                    pass
                    # print("Connection closed")

                # Transmission includes program stop program flag from Jetson
                elif(totalPacket[:8] == b'END_STOP'):
                    print("In audioRecordingServer.audioClient() -- Recieved endStop trigger!")
                    endStop = True

                # Transmission is normal data
                else:
                    # Splitting packet into metadata and data
                    metadata = totalPacket[:26].decode("utf-8")
                    data = totalPacket[26:]

                    # Writing data into files
                    fAudio.write(data)
                    fMeta.write(metadata + "\n")
    
    # Program has stopped, so it is safe to close all openings
    conn.close()
    conn2.close()
    serverSocket.close()
    fAudio.close()
    fMeta.close()

# Because sendall() does not communicate from client to client, this forwards
# the stop flag transmission incoming from the BMI to the Jetson.
def stoppingClient():
    while True:
        try:
            stopSignal = conn2.recv(10)
            if stopSignal:
                print("In audioRecordingServer.stoppingClient() -- Stop signal received! Forwarding to audio client...")
                conn.sendall(stopSignal)
                break
        except:
            print("Error in audioRecordingServer.stoppingClient() -- Unable to send forward stop program flag!")
            break

# Start threads to handle each client
audioThread = threading.Thread(target=audioClient, daemon=True)
stopThread = threading.Thread(target=stoppingClient, daemon=True)

audioThread.start()
stopThread.start()

# Refer to audioRecordingClient to see why I do this.
stopThread.join()
audioThread.join()