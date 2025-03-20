import socket
import alsaaudio as aa
import threading
import struct
import yaml
from datetime import datetime

# Defining Networking Parameters
ingestHostIP = '127.0.0.1'  # IP for ingestor, which is hosting the server with both the BMI and Jetson
ingestListenerPort = 36783  # Port for the listener on the ingestor host server

# Defining Audio Parameters
channels = 1
rate = 44100
format = aa.PCM_FORMAT_S16_LE
chunkSize = 882 * 2         # Multiplied by two because each sample is 16-bit
metadataSize = 26 + 26 + 4  # 26*2 for time taken and time received, and 4 for framecount

# Defining Frequency Stream Parameters
frequency = 200.0

# Flags to begin and end stopping program
beginStop = False
endStop = False

# Creating Server
ingestorSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ingestorSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
ingestorSocket.bind((ingestHostIP, ingestListenerPort))
ingestorSocket.listen()
print(f"In audioRecordingServer -- Listening on {ingestHostIP}:{ingestListenerPort}...")

# Accepting connection to audio recording client
jetsonConn, jetsonAddr = ingestorSocket.accept()
print(f"In audioRecordingServer -- Jetson is connected by {jetsonAddr}")

# Accepting connection to stop program client
BMIConn, BMIAddr = ingestorSocket.accept()
print(f"In audioRecordingServer -- BMI is connected by {BMIAddr}")







                    ## Defining Functions ##



# Was encountering some issues where recv was running too fast,
# and the metadata was getting decoded before it was ready, so this 
# is here to ensure that all data is recieved before attempting to encode
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
    lastTime = 0
    currentTime = 0

    # Opening audio storage file
    with open("audioOne.raw", "wb") as fAudio:

        # Opening metadata storage file
        with open("audioOne.yaml", "w") as fMeta:
            print("In audioRecordingServer.audioClient() -- Opened files!")

            # Attempting to recieve TCP packets from jetson
            while(not endStop):

                # Recieving entire packet
                totalPacket = recvAll(jetsonConn, metadataSize + chunkSize)
                now = datetime.now()

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
                    metadata = totalPacket[:metadataSize]
                    data = totalPacket[metadataSize:]

                    # Splitting metadata into respective elements
                    timeTaken = metadata[:26].decode("utf-8")
                    timeSent = metadata[26:52].decode("utf-8")
                    frameCountPacked = metadata[52:]         # Unpacks integer with struct
                    frameCount = struct.unpack(">I", frameCountPacked)[0]
                    timeReceived = now.strftime("%Y-%m-%d %H:%M:%S.%f")

                    # Calculating jitter between previous and current timeTakens
                    currentTime = (int(timeTaken[11:12]) * 60 * 60 * 1000) + (int(timeTaken[14:15]) * 60 * 1000) + (int(timeTaken[17:18]) * 1000) + int(timeTaken[20:])
                    timeDelta = currentTime - lastTime

                    lastTime = currentTime

                    # Creating metadata struct
                    metaEntry = {
                        "Frame_Instance": {
                            "Frame_Count": frameCount,
                            "Time_Taken": timeTaken,
                            "Time_Sent": timeSent,
                            "Time_Received": timeReceived,
                            "Time_Delta": timeDelta
                        }
                    }

                    # Writing data into files
                    fAudio.write(data)
                    yaml.dump([metaEntry], fMeta, default_flow_style=False, allow_unicode=True)
    
    # Program has stopped, so it is safe to close all openings
    jetsonConn.close()
    BMIConn.close()
    ingestorSocket.close()
    fAudio.close()
    fMeta.close()







# Because sendall() does not communicate from client to client, this forwards
# the stop flag transmission incoming from the BMI to the Jetson.
def stoppingClient():
    while True:
        break

        # Legacy code to support forwarding stopping signal to audio client
        # try:
        #     stopSignal = BMIConn.recv(10)
        #     if stopSignal:
        #         print("In audioRecordingServer.stoppingClient() -- Stop signal received! Forwarding to audio client...")
        #         jetsonConn.sendall(stopSignal)
        #         break
        # except:
        #     print("Error in audioRecordingServer.stoppingClient() -- Unable to send forward stop program flag!")
        #     break











# Start threads to handle each client
audioThread = threading.Thread(target=audioClient, daemon=True)
stopThread = threading.Thread(target=stoppingClient, daemon=True)

audioThread.start()
stopThread.start()

# Refer to audioRecordingClient to see why I do this.
stopThread.join()
audioThread.join()