import alsaaudio as aa
import threading
import socket
import time
import collections
import numpy as np
import time
from datetime import datetime

# Set capture parameters
FORMAT = aa.PCM_FORMAT_S16_LE
CHANNELS = 1
RATE = 44100
CHUNK_SIZE = 882
numSeconds = 10

# Setting Buffer Parameters
bufferSize = numSeconds * 50
audioBufferOne = collections.deque(maxlen=bufferSize)
audioMetaBufferOne = collections.deque(maxlen=bufferSize)
audioBufferTwo = collections.deque(maxlen=bufferSize)
audioMetaBufferTwo = collections.deque(maxlen=bufferSize)
whichBuffer = True             # True for bufferOne, False for bufferTwo

# Set Speaker Parameters
periodLength = .5 # Seconds
amplitude = .1
periodSize = 1024
t = np.linspace(0, periodLength, RATE)

# Open PCM Device for Microphone
micInput = aa.PCM(type=aa.PCM_CAPTURE, mode=aa.PCM_NORMAL)
micInput.setchannels(CHANNELS)
micInput.setrate(RATE)
micInput.setformat(FORMAT)
micInput.setperiodsize(CHUNK_SIZE)

# Open PCM Device for Speaker
speaker = aa.PCM(type=aa.PCM_PLAYBACK, mode=aa.PCM_NORMAL);
speaker.setchannels(CHANNELS);
speaker.setrate(RATE);
speaker.setformat(FORMAT);
speaker.setperiodsize(periodSize);

# Defining Server Parameters
HOST = '127.0.0.1'
PORT = 36783

# Creating Server
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen()
print(f"Listening on {HOST}:{PORT}...")

conn, addr = server_socket.accept()
print(f"Connected by {addr}")


# Defining Functions


# This is a function to generate a waveform to be played over the speaker.
#
# The waveform will be a sine wave with a designated frequency, the value
# of which will be sent over the network from the BMI.
# 
# A frequency of -1 designates no data to be output to the speaker.
def generateWaveform(frequency):
    if(frequency != -1):
    
        sineWave = amplitude * np.sin(2 * np.pi * frequency * t);
        audioData = sineWave.astype('float32').tobytes();
    else:
        audioData = -1
    
    return(audioData)


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


    while True:
        # Getting data from microphone
        length, data = micInput.read()

        if length:
            # Print statements for chatter
            print("Length of audio buffer one:")
            print(len(audioBufferOne))
            print(len(audioMetaBufferOne))
            print("Length of audio buffer two")
            print(len(audioBufferTwo))
            print(len(audioMetaBufferTwo))
            print("\n")

            # Appending audio data to associated list depending on the value of whichBuffer
            if(whichBuffer == True):
                # Appending audio data and metadata to associated lists
                audioBufferOne.append(data)
                now = datetime.now()
                timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f").encode("utf-8")
                audioMetaBufferOne.append(timestamp)

                # Switching flag to indicate bufferOne is full
                if(len(audioBufferOne) >= bufferSize):
                    whichBuffer = False

            elif(whichBuffer == False):

                # Appending audio data and metadata to associated lists
                audioBufferTwo.append(data)
                now = datetime.now()
                timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f").encode("utf-8")
                audioMetaBufferTwo.append(timestamp)
                
                # Switching flag to indicate bufferTwo is full
                if(len(audioBufferTwo) >= bufferSize):
                    whichBuffer = True

            else:
                print("In recordAudio() -- Unsupported flag value!")
            


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

    while True:

        # Getting audio data and metadata from buffer one
        if(not whichBuffer and len(audioBufferOne) > 0):
            data = audioBufferOne.popleft()
            metadata = audioMetaBufferOne.popleft()
            totalPacket = metadata + data
            # print(len(data))
            # print(len(metadata))
            # print(len(totalPacket))

        # Getting audio data and metadata from buffer two
        elif(whichBuffer and len(audioBufferTwo) > 0):
            data = audioBufferTwo.popleft()
            metadata = audioMetaBufferTwo.popleft()
            totalPacket = metadata + data
            # print(len(data))
            # print(len(metadata))
            # print(len(totalPacket))

        # Buffer indicated by whichBuffer is empty, will probably occur at the start of a program run
        elif(not whichBuffer and len(audioBufferOne) <= 0):
            data = None
        elif(whichBuffer and len(audioBufferTwo) <= 0):
            data = None
        else:
            data = None

        # Sending data over TCP
        if data:
            try:
                conn.sendall(totalPacket)
            except Exception as e:
                print(f"Error in sendAudio(): {e}")
                break
        else:
            time.sleep(0.001)

# def recieveFrequency():
#     while True:
#         frequency = conn.recv(4)
#         frequency = struct.unpack('!f', frequency)[0]
#         print(frequency)

#         audioData = generateWaveform(frequency)

#         speaker.write(audioData)


# Start threads only if we have a connection
print("Started Server!")
recordingThread = threading.Thread(target=recordAudio, daemon=True)
recordingThread.start()

sendingThread = threading.Thread(target=sendAudio, daemon=True)
sendingThread.start()

# receiveFrequencyThread = threading.Thread(target = recieveFrequency, daemon=True)
# receiveFrequencyThread.start()

try:
    while True:
        # print("Sleeping")
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping!")
    conn.close()
    server_socket.close()
