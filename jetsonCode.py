import alsaaudio as aa
import sounddevice as sd
import threading
import socket
import time
import collections
import numpy as np
import struct
import yaml
from yaml import SafeLoader
from datetime import datetime


# TO-DO:
#   - When I can use the jetson, mic, and speaker, assign the specific PCM/output devices

settingsFilePath = '/home/jemyers/RBProjects/experimentation/25_03_21_AudioStreaming/settings.yaml'
audioFilePath = '/home/jemyers/RBProjects/experimentation/25_03_21_AudioStreaming/TestAudio.raw'
audioMetaFilePath = '/home/jemyers/RBProjects/experimentation/25_03_21_AudioStreaming/TestAudio.yaml'


# Getting Networking and Audio Parameters from Settings File
with open(settingsFilePath, 'r') as settingsFile:
    data = list(yaml.load(settingsFile, Loader=SafeLoader))
    
    # Network settings
    ingestHostIP = data[0]['ingestorSettings']['ingestorIPAddress']
    ingestListenerPort = data[0]['ingestorSettings']['ingestorListenerPort']
    ingestJetsonPort = data[1]['jetsonSettings']['ingestorJetsonCommPort']

    BMIHostIP = data[2]["BMISettings"]["BMIIPAddress"]
    BMIListenerPort = data[2]['BMISettings']['BMIListenerPort']
    BMIJetsonPort = data[1]['jetsonSettings']["BMIJetsonCommPort"]

    # Microphone Settings
    CHANNELS = data[4]['audioSettings']['channels']
    RATE = data[4]['audioSettings']['rate']

    if('S16_LE' in data[4]['audioSettings']['format']):
        FORMAT = aa.PCM_FORMAT_S16_LE
    
    bufferLength = data[3]['bufferSettings']['bufferLength']
    framerate = data[3]['bufferSettings']['framerate']

    # Speaker Settings
    speakerAmplitude = data[5]['speakerSettings']['amplitude']
    speakerBlockSize = data[5]['speakerSettings']['blockSize']

    settingsFile.close()


# Set capture parameters
CHUNK_SIZE = int(RATE / framerate)
metadataSize = 26 + 26 + 4     # 26 for both timestamps and 4 for the frameCount integer
frameCounter = 1


# Setting Buffer Parameters
bufferSize = bufferLength * framerate
audioBufferOne = collections.deque(maxlen=bufferSize)
audioMetaBufferOne = collections.deque(maxlen=bufferSize)
audioBufferTwo = collections.deque(maxlen=bufferSize)
audioMetaBufferTwo = collections.deque(maxlen=bufferSize)
whichBuffer = True             # True for bufferOne, False for bufferTwo
beginStop = False


# Set Speaker Parameters
speakerFrequency = 0


# Open PCM Device for Microphone (have to include a retry because of late booting of virtual audio card on startup)
print("In jetsonCode.py -- Attempting to start capture device.")
maxRetries = 10
for attempt in range(maxRetries):
    try:
        micInput = aa.PCM(type=aa.PCM_CAPTURE, 
                          mode=aa.PCM_NORMAL, 
                         channels=CHANNELS, 
                         rate=RATE, 
                         format=FORMAT, 
                         periodsize=CHUNK_SIZE)
        break
    except aa.ALSAAudioError as e:
        print(f"In jetsonCode.py -- [Attempt {attempt+1}] ALSA not ready: {e}")
        time.sleep(1)
else:
    raise RuntimeError("In jetsonCode.py -- Failed to initialize ALSAAudioDevice after multiple attempts.")

print("In jetsonCode.py -- Started microphone capture device.")


# Connecting to Ingestor Server
ingestSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ingestSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # So the system does not wait so long after the program terminates to close the socket
ingestSocket.bind((ingestHostIP, ingestJetsonPort))
ingestSocket.connect((ingestHostIP, ingestListenerPort))
print("In jetsonCode -- Connected to ingestor!")


# Connecting to BMI Server
BMISocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
BMISocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # So the system does not wait so long after the program terminates to close the socket
BMISocket.bind((BMIHostIP, BMIJetsonPort))
BMISocket.connect((BMIHostIP, BMIListenerPort))
print("In jetsonCode -- Connected to BMI!")







                ## Defining Functions ##



# This is a function to make sure the entire data is recieved
def recvAll(sock, size):
    data = b""
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            return None  # Handle closed connection
        data += packet
    return data










# recordAudio() is a function to input audio from an ALSAaudio device
# and put it in one of two buffers that can be accessed globally.
#
# The buffers are both lists in the collections library, which are essentially 
# double ended lists that can be accessed from both sides. Each time a section
# of audio is recorded, the length of which specified by the CHUNK_SIZE variable,
# it appends this to the designated buffer.
#
# It utilizes the whichBuffer global flag variable, if whichBuffer is true
# it will push audio data into buffer one, if it is false it will push audio
# data into buffer two.
#
# Furthermore, once one of the buffers are filled up, a global flag associated
# with that buffer will be marked true so this condition can be known by other 
# functions. The whichBuffer flag will also be toggled when one of the buffers
# is filled.
def recordAudio():
    global whichBuffer
    global beginStop

    while(not beginStop):
        # print("In jetsonCode.recordAudio() -- Entered recordAudio while loop!")

        # Getting data from microphone
        length, data = micInput.read()

        if length:
            # print(f"Buffer One Size: {len(audioBufferOne)}, Buffer Two Size: {len(audioBufferTwo)}")
            # Print statements for chatter
            # print("In jetsonCode.recordAudio() -- Got audio data!")
            # print("Length of audio buffer one:")
            # print(len(audioBufferOne))
            # print(len(audioMetaBufferOne))
            # print("Length of audio buffer two")
            # print(len(audioBufferTwo))
            # print(len(audioMetaBufferTwo))
            # print("\n")

            # whichBuffer being true means stack up bufferOne and transmit from bufferTwo
            if(whichBuffer == True):

                # Appending audio data and metadata to associated lists
                audioBufferOne.append(data)
                now = datetime.now()
                timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f").encode("utf-8")
                audioMetaBufferOne.append(timestamp)

                # Switching flag to indicate bufferOne is full
                if(len(audioBufferOne) >= bufferSize):
                    # print("Size of bufferOne at full:")
                    # print(len(audioBufferOne))
                    whichBuffer = False

            # whichBuffer being false means stack up bufferTwo and transmit from bufferOne
            elif(whichBuffer == False):

                # Appending audio data and metadata to associated lists
                audioBufferTwo.append(data)
                now = datetime.now()
                timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f").encode("utf-8")
                audioMetaBufferTwo.append(timestamp)
                
                # Switching flag to indicate bufferTwo is full
                if(len(audioBufferTwo) >= bufferSize):
                    whichBuffer = True
                    # print("Size of bufferTwo at full:")
                    # print(len(audioBufferTwo))

            else:
                print("In jetsonCode.recordAudio() -- Unsupported flag value!")
            







# sendAudio() is a function to take audio from one of the two buffer discussed
# in recordAudio(), and send them over the network.
#
# The two buffers are double ended lists in the collections library, and therefore
# can be accessed using the popleft() function. This is used to pop audio data
# off of the buffers. The audio chunk that is popped off will then be sent over
# the network. Once the specified buffer by the global whichBuffer variable 
# (discused more thoroughly in recordAudio()) reaches a length of zero, which means
# that all data has been sent, it will toggle the bufferXFull variables.
def sendAudio():
    global whichBuffer
    global beginStop
    global frameCounter
    endStop = False

    # For future me: I am trying to send a packet of info that contains the datetime
    # stamp for a buffer unload, as well as the length of the buffer so that the receiver
    # knows how many packets to accept.
    #
    # There should not be anything sent until bufferOne is full, so I can utilize this
    # to have the second message to be sent (after the initial recording datetime stamp above)
    # to have a known length, i.e. 26 bytes for datetime plus 2^x for 498 or 500 or however
    # many items there are in the buffer.
    #
    # Implement a for loop in the reciever code to iterate however large buffer is so that it
    # knows when the buffer is empty and can accept a new metadata packet.

    while(not endStop):
        # print("In jetsonCode.sendAudio(): Entered sendAudio while loop!")

        # Handling condition if program was told to stop via transmission from BMI (forwarded from Ingestor)
        if(beginStop == True):
            # print("jetsonCode.py -- Entered beginStop if statement!")

            # endStop flag becomes true once all data is saved from buffers (to prevent data loss on shutdown)
            while(not endStop):

                # Take all information out of bufferOne first
                if(len(audioBufferOne) > 0):
                    data = audioBufferOne.popleft()
                    metadata = audioMetaBufferOne.popleft()
                    now = datetime.now()
                    timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f").encode("utf-8")
                    frameCountPacked = struct.pack(">I", frameCounter)
                    totalPacket = metadata + timestamp + frameCountPacked + data
                    frameCounter = frameCounter + 1
                    # print("BufferOne still full!")

                # Then take all information out of bufferTwo
                elif(len(audioBufferTwo) > 0):
                    data = audioBufferTwo.popleft()
                    metadata = audioMetaBufferTwo.popleft()
                    now = datetime.now()
                    timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f").encode("utf-8")
                    frameCountPacked = struct.pack(">I", frameCounter)
                    totalPacket = metadata + timestamp + frameCountPacked + data
                    frameCounter = frameCounter + 1
                    # print("BufferTwo still full!")

                # If data gathering from buffers was successful
                if data:
                    # print(totalPacket)
                    try:
                        ingestSocket.sendall(totalPacket)
                        # print("Packet sent!")
                    except Exception as e:
                        print(f"Error in jetsonCode.sendAudio(): {e}")

                    # Setting data back to null so it doesn't send the same data infinitely                            
                    data = None

                # No more data in buffers, so it is safe to send transmission finished message to Ingestor
                else:
                    print("In jetsonCode.sendAudio() -- No data left, sending endStop trigger!")
                    try:
                        totalPacket = b'END_STOP' + bytearray(metadataSize + (2 * CHUNK_SIZE) - len(b"END_STOP"))
                        ingestSocket.sendall(totalPacket)
                        print("In jetsonCode.sendAudio() -- Sent endStop trigger!")
                        endStop = True

                    except Exception as e:
                        print(f"In jetsonCode.sendAudio() -- Error in sendAudio(): {e}")
            
            

        # Getting audio data and metadata from buffer one
        elif(not whichBuffer and len(audioBufferOne) > 0):
            data = audioBufferOne.popleft()
            metadata = audioMetaBufferOne.popleft()
            now = datetime.now()
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f").encode("utf-8")
            frameCountPacked = struct.pack(">I", frameCounter)
            totalPacket = metadata + timestamp + frameCountPacked + data
            frameCounter = frameCounter + 1
            # print(len(data))
            # print(len(metadata))
            # print(len(totalPacket))

        # Getting audio data and metadata from buffer two
        elif(whichBuffer and len(audioBufferTwo) > 0):
            data = audioBufferTwo.popleft()
            metadata = audioMetaBufferTwo.popleft()
            now = datetime.now()
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f").encode("utf-8")
            frameCountPacked = struct.pack(">I", frameCounter)
            totalPacket = metadata + timestamp + frameCountPacked + data
            frameCounter = frameCounter + 1
            # print(len(data))
            # print(len(metadata))
            # print(len(totalPacket))

        # Buffer indicated by whichBuffer is empty, will probably occur at the start of a program run
        else:
            data = None
            # print("In jetsonCode.sendAudio() -- Audio buffers are empty, probably just started program!")

        # Sending data over TCP
        if data:
            try:
                ingestSocket.sendall(totalPacket)
                # print("Packet sent!")
            except Exception as e:
                print(f"In jetsonCode.sendAudio() -- {e}")
                break
    
    # Closing all connections and such to stop program
    print("In jetsonCode.sendAudio() -- Program has successfully concluded!")
    time.sleep(2)
    ingestSocket.close()
    BMISocket.close()
    







def recieveStop():
    global beginStop
    global speakerFrequency

    print("In jetsonCode.recieveStop() -- Stopping thread is executing.")


    while(not beginStop):
        message = recvAll(BMISocket, 10)

        if(message.startswith(b'BEGIN_STOP')):
            print("In jetsonCode.recieveStop() -- Received beginStop trigger!")
            beginStop = True
        else:
            speakerFrequency = struct.unpack('>f', message[:4])[0]
            extraBytes = message[4:]
            







# Uses sounddevice outputstream because alsaaudio pcm write was having issues
# with discontinuites creating weird harmonics, causing distorted sound.
# This allows constant audio stream and also phase shift of the waveform.
def audioCallback(outdata, frames, time, status):
    global speakerFrequency
    t = (np.arange(frames) + audioCallback.phase) / RATE
    wave = speakerAmplitude * np.sin(2 * np.pi * speakerFrequency * t)
    outdata[:] = wave.reshape(-1, 1)
    audioCallback.phase += frames  # Keep track of phase
audioCallback.phase = 0  # Initial phase







# Opens an output stream to the speaker device, and waits until the beginStop transmission is sent 
# from the BMI to stop the playback.
def speakerPlayback():
    global beginStop
    global speakerFrequency

    with sd.OutputStream(callback=audioCallback, samplerate=RATE, blocksize=speakerBlockSize, channels=1):
        while not beginStop:
            time.sleep(.1)
    









# Start threads only if we have a connection
recordingThread = threading.Thread(target=recordAudio, daemon=True)
recordingThread.start()

sendingThread = threading.Thread(target=sendAudio, daemon=True)
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