import socket
import alsaaudio as aa
import threading
import struct
import yaml
from yaml import SafeLoader
from datetime import datetime
import os
import cv2
import numpy as np

# Getting Networking and Audio Parameters from Settings File
with open('settings.yaml', 'r') as settingsFile:
    data = list(yaml.load(settingsFile, Loader=SafeLoader))
    
    # Network settings
    ingestHostIP = data[0]['ingestorSettings']['ingestorIPAddress']
    ingestListenerPort = data[0]['ingestorSettings']['ingestorListenerPort']
    ingestJetsonPort = data[1]['jetsonSettings']['ingestorJetsonCommPort']
    jetsonHostIP = data[1]['jetsonSettings']['jetsonIPAddress']
    jetsonListenerPort = data[1]['jetsonSettings']['jetsonListenerPort']

    # Microphone Settings
    channels = data[4]['audioSettings']['channels']
    rate = data[4]['audioSettings']['rate']
    framerate = data[3]['bufferSettings']['framerate']
    chunkSize = 2 * int(rate / framerate)

    # Speaker Settings
    speakerAmplitude = data[5]['speakerSettings']['amplitude']
    speakerBlockSize = data[5]['speakerSettings']['blockSize']

    settingsFile.close()


# Defining Audio Parameters
audioMetaSize = 26
videoMetaSize = 26
metadataSize = audioMetaSize + videoMetaSize + 26 + 4       # 26 for timeSent and 4 for frameCount

# Defining Frequency Stream Parameters
frequency = 200.0

# Flags to begin and end stopping program
beginStop = False
endStop = False

# Defining path for camera frames
SAVE_DIR = "captured_frames"

if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

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
    lastAudioTime = 0
    lastVideoTime = 0
    currentAudioTime = 0
    currentVideoTime = 0

    # Opening audio storage file
    with open("audioOne.raw", "wb") as fAudio:

        # Opening metadata storage file
        with open("audioOne.yaml", "w") as fMeta:
            print("In audioRecordingServer.audioClient() -- Opened files!")

            # Attempting to recieve TCP packets from jetson
            while(not endStop):

                # Recieving entire packet
                totalPacket = recvAll(jetsonConn, metadataSize + chunkSize + 2*1280*720*3)
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

                    # Splitting data into audio and video elements
                    audioData = data[:chunkSize]
                    camZeroFlat = data[chunkSize:(1280*720*3 + chunkSize)]
                    camOneFlat = data[(1280*720*3 + chunkSize):]

                    # Splitting metadata into respective elements
                    frameCountPacked = metadata[:4]
                    timeSent = metadata[4:(4+26)]
                    audioTimeTaken = metadata[(4+26):(4+26+26)]
                    videoTimeTaken = metadata[(4+26+26):]

                    frameCount = struct.unpack(">I", frameCountPacked)[0]
                    timeReceived = now.strftime("%Y-%m-%d %H:%M:%S.%f")

                    # Calculating jitter between previous and current timeTakens
                    currentAudioTime = (int(audioTimeTaken[11:12]) * 60 * 60 * 1000) + (int(audioTimeTaken[14:15]) * 60 * 1000) + (int(audioTimeTaken[17:18]) * 1000) + int(audioTimeTaken[20:])
                    currentVideoTime = (int(videoTimeTaken[11:12]) * 60 * 60 * 1000) + (int(videoTimeTaken[14:15]) * 60 * 1000) + (int(videoTimeTaken[17:18]) * 1000) + int(videoTimeTaken[20:])
                    
                    audioTimeDelta = currentAudioTime - lastAudioTime
                    videoTimeDelta = currentVideoTime - lastVideoTime

                    lastAudioTime = currentAudioTime
                    lastVideoTime = currentVideoTime

                    # Reshaping camera data into original shape
                    camZeroInt = np.frombuffer(camZeroFlat, dtype=np.uint8)
                    camZeroData = camZeroInt.reshape((720, 1280, 3))

                    camOneInt = np.frombuffer(camOneFlat, dtype=np.uint8)
                    camOneData = camOneInt.reshape((720, 1280, 3))

                    # Generating filenames for camera frames
                    camZeroFilename = os.path.join(SAVE_DIR, f"cam0_frame_{frameCount}.raw")
                    camOneFilename = os.path.join(SAVE_DIR, f"cam1_frame_{frameCount}.raw")

                    # Writing audio data into file -- If array is all zeros then there was only video data
                    if(audioData != bytearray(chunkSize)):
                        fAudio.write(audioData)
                    else:
                        print("In audioRecordingServer.audioClient() -- No audio data received!")
                        audioTimeTaken = "NULL"
                        audioTimeDelta = "NULL"
                    
                    # Writing video data into file -- If array is all zeros then there was only audio data
                    if(camZeroFlat != bytearray(1280 * 720 * 3) and camOneFlat != bytearray(1280 * 720 * 3)):
                        camZeroData.tofile(camZeroFilename)
                        camOneData.tofile(camOneFilename)
                    else:
                        print("In audioRecordingServer.audioClient() -- No audio data received!")
                        videoTimeTaken = "NULL"
                        videoTimeDelta = "NULL"


                    # Creating metadata struct
                    metaEntry = {
                        "Frame_Instance": {
                            "Frame_Count": frameCount,
                            "Audio_Time_Taken": audioTimeTaken,
                            "Video_Time_Taken": videoTimeTaken,
                            "Time_Sent": timeSent,
                            "Time_Received": timeReceived,
                            "Audio_Time_Delta": audioTimeDelta,
                            "Video_Time_Delta": videoTimeDelta
                        }
                    }

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