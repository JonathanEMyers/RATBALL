# Import functions
import alsaaudio as aa
import sounddevice as sd
import struct, threading, socket, time, collections, yaml, csv
import numpy as np
from yaml import SafeLoader
from datetime import datetime, timezone
import cv2
import sys  # For getting size of datatypes
import Microphone

# Open settings file and gather all necessary variables
settingsFilename = "settings.yaml"

with open(settingsFilename, 'r') as settingsFile:
    data = list(yaml.load(settingsFile, Loader=SafeLoader))
    
    # Network settings
    ingestHostIP = data[0]['ingestorSettings']['ingestorIPAddress']
    ingestListenerPort = data[0]['ingestorSettings']['ingestorListenerPort']
    ingestJetsonPort = data[1]['jetsonSettings']['ingestorJetsonCommPort']

    BMIHostIP = data[2]["BMISettings"]["BMIIPAddress"]
    BMIListenerPort = data[2]['BMISettings']['BMIListenerPort']
    BMIJetsonPort = data[1]['jetsonSettings']["BMIJetsonCommPort"]

    # Microphone Settings
    audioNumChannels = data[4]['audioSettings']['channels']
    audioRate = data[4]['audioSettings']['rate']

    if('S16_LE' in data[4]['audioSettings']['format']):
        audioFormat = aa.PCM_FORMAT_S16_LE
    
    bufferLength = data[3]['bufferSettings']['bufferLength']
    framerate = data[3]['bufferSettings']['framerate']

    # Speaker Settings
    speakerAmplitude = data[5]['speakerSettings']['amplitude']
    speakerBlockSize = data[5]['speakerSettings']['blockSize']

    settingsFile.close()

# Define necessary parameters not in settings file
audioChunkSize = int(audioRate / framerate)
audioDataFilepath = "25_04_19_Audio.raw"
audioMetaFilepath = "25_04_19_Audio.csv"
blankDataFilepath = "25_04_19_Blank.csv"


metadataSize = 6 * 8 + 4       # UPDATE FOR EACH NEW PIECE OF DATA -- Known metadata size (in bytes) at transmission
                                #   - Six timestamps, (8 bytes each), one for each:
                                #       - One microphone
                                #       - Four placeholder (blank) sensor channels
                                #       - Time of transmission
                                #   - One four-byte int
                                #       - For the frame counter

dataSize = 2*audioChunkSize + 4*8       # UPDATE FOR EACH NEW PIECE OF DATA
                                        #   - 2*audiochunksize for 16-bit LE format single channel
                                        #   - 4*8 for 4 eight-byte blank channel expansion slots

# Define flags
beginTermination = False
endTermination = False

# Set up TCP listener
ingestorSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ingestorSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
ingestorSocket.bind((ingestHostIP, ingestListenerPort))
ingestorSocket.listen()
print(f"In ingestorCode -- Listening on {ingestHostIP}:{ingestListenerPort}...")

# Accept socket connection from BMI
BMIConn, BMIAddr = ingestorSocket.accept()
print(f"In ingestorCode -- BMI is connected by {BMIAddr}")

# Accept socket connection from Jetson
jetsonConn, jetsonAddr = ingestorSocket.accept()
print(f"In ingestorCode -- Jetson is connected by {jetsonAddr}")



# Helper functions

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

# This is a function to determine the time since epoch
unix_epoch = datetime.fromtimestamp(0, timezone.utc)
def unix_time_millis(dt):
    """formats timestamps as milliseconds-since-epoch (double-precision float, only requires 8 bytes)"""
    if dt.tzinfo is None:
        # make dt offset-aware in UTC if it's naive
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # convert to UTC if it's aware in a different timezone
        dt = dt.astimezone(timezone.utc)
    return (dt - unix_epoch).total_seconds() * 1000.0




# Thread-associated functions
def handleJetson():
    global beginTermination
    global endTermination

    # Open all necessary files (metadata files, audio file, sensor data file, etc.)
    with (
        open(audioDataFilepath, "wb") as fAudio,
        open(audioMetaFilepath, "w", newline='') as fAudioMeta,
        open(blankDataFilepath, "w", newline='') as fBlank
    ):
        audioWriter = csv.writer(fAudioMeta)
        blankWriter = csv.writer(fBlank)
        audioWriter.writerow(["Frame Count", "Reception Time", "Sent Time", "Taken time"])
        blankWriter.writerow(["Frame Count", "Reception Time", "Sent Time", "Lick Sensor Taken Time", "Lick Sensor Value", "Sensor One Taken Time", "Sensor One Value", "Sensor Two Taken Time", "Sensor Two Value", "Sensor Three Taken Time", "Sensor Three Value"])
        print("In ingestorCode.handleJetson() -- Opened files!")

        while(not endTermination):
            # Receive total packet
            totalPacket = recvAll(jetsonConn, metadataSize + dataSize)


            # Establish time of reception
            receptionTime = datetime.now()
            receptionTimeSinceEpoch = unix_time_millis(receptionTime)

            if(totalPacket is None):
                pass

            elif(totalPacket[:8] == b'END_STOP'):
                endTermination = True

            else:
                # Splitting packet into metadata and data
                metadata = totalPacket[:metadataSize]
                data = totalPacket[metadataSize:]

                # Splitting metadata into individual elements
                #   - Ex: audioMetadata = metadata[26:54] --> The indexes are determined on the jetson side
                frameCountPacked = metadata[:4]
                frameCount = struct.unpack(">I", frameCountPacked)[0]

                timeSentPacked = metadata[4:12]
                timeSent = struct.unpack('d', timeSentPacked)[0]

                audioTimeTakenPacked = metadata[12:20]
                audioTimeTaken = struct.unpack('d', audioTimeTakenPacked)[0]

                lickTimeTakenPacked = metadata[20:28]
                lickTimeTaken = struct.unpack('d', lickTimeTakenPacked)[0]

                blankOneTimeTakenPacked = metadata[28:36]
                blankOneTimeTaken = struct.unpack('d', blankOneTimeTakenPacked)[0]

                blankTwoTimeTakenPacked = metadata[36:44]
                blankTwoTimeTaken = struct.unpack('d', blankTwoTimeTakenPacked)[0]

                blankThreeTimeTakenPacked = metadata[44:52]
                blankThreeTimeTaken = struct.unpack('d', blankThreeTimeTakenPacked)[0]


                # Splitting data into individual elements
                #   - Same idea as the metadata splitting
                #   - Video data should be last so we dont have to use massive index values
                lickData = data[:8]
                blankOneData = data[8:16]
                blankTwoData = data[16:24]
                blankThreeData = data[24:32]
                audioData = data[32:]

                # Reformat video metadata and append it to file
                # Reshape video data and create a file for it

                # Reformat ODOM metadata and append it to file
                # Reformat ODOM data and append it to file

                # Reformat audio metadata and append it to file
                audioWriter.writerow([frameCount, receptionTimeSinceEpoch, timeSent, audioTimeTaken])
                blankWriter.writerow([frameCount, receptionTimeSinceEpoch, timeSent, lickTimeTaken, lickData, blankOneTimeTaken, blankOneData, blankTwoTimeTaken, blankTwoData, blankThreeTimeTaken, blankThreeData])
                # print(f"{frameCount},{receptionTime},{audioTimeTaken}")
                # Reformat audio data and append it to file 
                fAudio.write(audioData)


    # Transmission is finished, close all openings
    print("In ingestorCode.handleJetson() -- Received endTermination trigger, shutting down!")
    jetsonConn.close()
    BMIConn.close()
    ingestorSocket.close()
    fAudio.close()
    fAudioMeta.close()


jetsonThread = threading.Thread(target=handleJetson, daemon=True)

jetsonThread.start()

jetsonThread.join()