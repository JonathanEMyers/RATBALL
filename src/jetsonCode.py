# Insert import functions
import alsaaudio as aa
import sounddevice as sd
import struct, threading, socket, time, collections, yaml
import numpy as np
from yaml import SafeLoader
from datetime import datetime, timezone
import cv2
import sys  # For getting size of datatypes
import Microphone

# Open settings file and gather necessary information
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

# Calculate and/or define necessary initial parameters for code
audioChunkSize = int(audioRate / framerate)
speakerFrequency = 0
frameCounter = 1
bufferSize = bufferLength * framerate

metadataSize = 2 * 8 + 4       # UPDATE FOR EACH NEW PIECE OF DATA -- Known metadata size (in bytes) at transmission
                                #   - Six timestamps, (8 bytes each), one for each:
                                #       - One microphone
                                #       - Four placeholder (blank) sensor channels
                                #       - Time of transmission
                                #   - One four-byte int
                                #       - For the frame counter



# Define flags
beginTermination =  False
endTermination = False
whichBuffer = True

# Define sensor objects (2 optical, 2 camera, microphone, speaker, placeholders)
mic = Microphone.Microphone(bufferSize, audioRate, audioNumChannels, audioFormat, framerate)

# Connect to Ingestor Server
ingestSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ingestSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # So the system does not wait so long after the program terminates to close the socket
ingestSocket.bind((ingestHostIP, ingestJetsonPort))
ingestSocket.connect((ingestHostIP, ingestListenerPort))
print("In jetsonCode -- Connected to ingestor!")

# Connect to BMI Server
BMISocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
BMISocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # So the system does not wait so long after the program terminates to close the socket
BMISocket.bind((BMIHostIP, BMIJetsonPort))
BMISocket.connect((BMIHostIP, BMIListenerPort))
print("In jetsonCode -- Connected to BMI!")






                    # Helper functions (recvAll, any compression, metadata generation, etc.)

# This is a function to make sure the entire data is recieved
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


# Uses sounddevice outputstream because alsaaudio pcm write was having issues
# with discontinuites creating weird harmonics, causing distorted sound.
# This allows constant audio stream and also phase shift of the waveform.
def audioCallback(outdata, frames, time, status):
    global speakerFrequency
    t = (np.arange(frames) + audioCallback.phase) / audioRate
    wave = speakerAmplitude * np.sin(2 * np.pi * speakerFrequency * t)
    outdata[:] = wave.reshape(-1, 1)
    audioCallback.phase += frames  # Keep track of phase
audioCallback.phase = 0  # Initial phase





                    # Thread-associated functions

def gatherSensorData():
    global beginTermination
    global whichBuffer
    frameInterval = 1/framerate
    expStartTime = time.perf_counter()

    while(not beginTermination):

        # Take time with perf_counter()
        startTime = time.perf_counter()

        # Append new frame to camera buffers

        # Append new ODOM reading to ODOM buffers

        # Append new audio to mic object buffer
        audioAdditionSuccess = mic.appendMicData(whichBuffer)

        # Append similated lick reading to lick sensor object buffer

        # Append simulated Misc. sensor readings to misc. sensor object buffers

        # Switching whichBuffer flag
        if(whichBuffer and len(mic.dataBufferOne) >= bufferSize):
            whichBuffer = False
        
        elif(not whichBuffer and len(mic.dataBufferTwo) >= bufferSize):
            whichBuffer = True


        # Take time with perf_counter()
        endTime = time.perf_counter()

        # Wait the difference between elapsed time and 1/framerate seconds
        timeDelta = endTime - startTime
        timeToWait = frameInterval - timeDelta

        print(f'frameCount: {mic.frameCount}, timeToWait: {timeToWait}, timeSinceStart: {endTime - expStartTime}')

        # time.sleep(max(0, timeToWait))

        # Time.sleep is not very accurate, so using a busy loop with perf_counter()
        while(time.perf_counter() - startTime < frameInterval):
            pass





def sendSensorData():
    global whichBuffer
    global beginTermination
    global endTermination
    global frameCounter

    endTermination = False
    
    dataExists = True

    # Keep sending data until finished sending all data
    while(not endTermination):

        # Case where experiment is still going
        if(not beginTermination):
            if((not whichBuffer) and (len(mic.dataBufferOne) > 0)): 

                dataExists = True

                # Pull camera metadata from camera metadata buffer one
                # Pull camera data from camera data buffer one
                
                # Pull ODOM metadata from ODOM metadata buffer one
                # Pull ODOM data from ODOM data buffer one

                # Pull audio metadata from audio metadata buffer one
                # Pull audio data from audio data buffer one
                audioMetadata, audioData = mic.popMicData(whichBuffer)

                # Pull lick metadata from lick metadata buffer one
                # Pull lick data from lick data buffer one

            elif(whichBuffer and (len(mic.dataBufferTwo) > 0)):

                dataExists = True

                # Pull camera metadata from camera metadata buffer two
                # Pull camera data from camera data buffer two
                
                # Pull ODOM metadata from ODOM metadata buffer two
                # Pull ODOM data from ODOM data buffer two

                # Pull audio metadata from audio metadata buffer two
                # Pull audio data from audio data buffer two
                audioMetadata, audioData = mic.popMicData(whichBuffer)

                # Pull lick metadata from lick metadata buffer two
                # Pull lick data from lick data buffer two

            # Program has not stopped yet but there is no data in buffers at the moment
            else:
                dataExists = False

        # Case where experiment has ended, but just clearing out the buffer
        else:

            # There are items still in buffer one
            if(len(mic.dataBufferOne) > 0):
                dataExists = True

                # Pull camera metadata from camera metadata buffer one
                # Pull camera data from camera data buffer one
                
                # Pull ODOM metadata from ODOM metadata buffer one
                # Pull ODOM data from ODOM data buffer one

                # Pull audio metadata from audio metadata buffer one
                # Pull audio data from audio data buffer one
                audioMetadata, audioData = mic.popMicData(False)

                # Pull lick metadata from lick metadata buffer one
                # Pull lick data from lick data buffer one

            # There are items still in buffer two
            elif(len(mic.dataBufferTwo) > 0):
                dataExists = True

                # Pull camera metadata from camera metadata buffer two
                # Pull camera data from camera data buffer two
                
                # Pull ODOM metadata from ODOM metadata buffer two
                # Pull ODOM data from ODOM data buffer two

                # Pull audio metadata from audio metadata buffer two
                # Pull audio data from audio data buffer two
                audioMetadata, audioData = mic.popMicData(True)

                # Pull lick metadata from lick metadata buffer two
                # Pull lick data from lick data buffer two

            # Data is finished transmission
            else:
                endTermination = True
                dataExists = False  

                # Sending stop transmission
                print("In jetsonCode.sendAudio() -- No data left, sending endTermination trigger!")
                try:
                    totalPacket = b'END_STOP' + bytearray(metadataSize + (2 * audioChunkSize) - len(b"END_STOP"))
                    ingestSocket.sendall(totalPacket)
                    print("In jetsonCode.sendAudio() -- Sent endTermination trigger!")
                    endTermination = True

                except Exception as e:
                    print(f"In jetsonCode.sendAudio() -- Error in sendAudio(): {e}")

        if(dataExists):

            # Pack frame counter
            frameCountPacked = struct.pack(">I", frameCounter)
            # Take time snapshot for sent time
            sentTime = datetime.now()
            sentTimeSinceEpoch = unix_time_millis(sentTime)
            sentTimeSinceEpochPacked = struct.pack('d', sentTimeSinceEpoch)

            # Assemble total packet
            #   - packedFrameCounter + sentTime + camMeta + ODOMMeta + audioMeta + lickMeta + camData + ODOMData + audioData + lickData
            totalPacket = frameCountPacked + sentTimeSinceEpochPacked + audioMetadata + audioData

            # Send total packet over ingestor connection
            ingestSocket.sendall(totalPacket)
        
            frameCounter += 1
    
    # Closing all connections and such to stop program
    print("In jetsonCode.sendAudio() -- Program has successfully concluded!")
    time.sleep(2)
    ingestSocket.close()
    BMISocket.close()

        


def recieveStop():
    global beginTermination
    global speakerFrequency

    print("In jetsonCode.recieveStop() -- Stopping thread is executing.")


    while(not beginTermination):
        message = recvAll(BMISocket, 10)

        if(message.startswith(b'BEGIN_STOP')):
            print("In jetsonCode.recieveStop() -- Received beginTermination trigger!")
            beginTermination = True
        else:
            speakerFrequency = struct.unpack('>f', message[:4])[0]
            extraBytes = message[4:]


def speakerPlayback():
    global startTermination
    global speakerFrequency

    with sd.OutputStream(callback=audioCallback, samplerate=audioRate, blocksize=speakerBlockSize, channels=1):
        while not beginTermination:
            time.sleep(.1)



# Start threads only if we have a connection
recordingThread = threading.Thread(target=gatherSensorData, daemon=True)
recordingThread.start()

sendingThread = threading.Thread(target=sendSensorData, daemon=True)
sendingThread.start()

stoppingThread = threading.Thread(target=recieveStop, daemon=True)
stoppingThread.start()

speakerThread = threading.Thread(target=speakerPlayback, daemon=True)
speakerThread.start()

# The join function waits to close the main thread until the thread that the join
# function is being called on finishes. I was encountering issues with the main thread
# doing this and it was throwing errors.
stoppingThread.join()
recordingThread.join()
sendingThread.join()
speakerThread.join()

