import alsaaudio as aa
import threading
import socket
import time
import collections
import numpy as np
import struct
from datetime import datetime

# Set capture parameters
FORMAT = aa.PCM_FORMAT_S16_LE
CHANNELS = 1
RATE = 44100
CHUNK_SIZE = 882
numSeconds = 10
metadataSize = 26 + 26 + 4     # 26 for both timestamps and 4 for the frameCount integer
frameCounter = 1

# Setting Buffer Parameters
bufferSize = numSeconds * 50
audioBufferOne = collections.deque(maxlen=bufferSize)
audioMetaBufferOne = collections.deque(maxlen=bufferSize)
audioBufferTwo = collections.deque(maxlen=bufferSize)
audioMetaBufferTwo = collections.deque(maxlen=bufferSize)
whichBuffer = True             # True for bufferOne, False for bufferTwo
beginStop = False

# Set Speaker Parameters
periodLength = .5 # Seconds
amplitude = .1
periodSize = 1024
t = np.linspace(0, periodLength, RATE)

# Open PCM Device for Microphone
micInput = aa.PCM(type=aa.PCM_CAPTURE, 
                  mode=aa.PCM_NORMAL, 
                  channels=CHANNELS, 
                  rate=RATE, 
                  format=FORMAT, 
                  periodsize=CHUNK_SIZE)

# Open PCM Device for Speaker
speaker = aa.PCM(type=aa.PCM_PLAYBACK, 
                 mode=aa.PCM_NORMAL, 
                 channels=CHANNELS, 
                 rate=RATE, 
                 format=FORMAT, 
                 periodsize=periodSize)


# Defining Server Parameters
ingestHostIP = '127.0.0.1'
ingestListenerPort = 36783
ingestPort = 36784

# Connecting to Server
ingestSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ingestSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # So the system does not wait so long after the program terminates to close the socket
ingestSocket.bind(('127.0.0.1', ingestPort))
ingestSocket.connect((ingestHostIP, ingestListenerPort))
print("In audioRecordingClient -- Connected to ingestor!")

# Defining Client-to-Client Parameters
jetsonHostIP = '127.0.0.1'  # IP Address of Jetson -- Jetson is hosting this connection
jetsonListenerPort = 36786    # Listener port for jetson server

# Establishing Peer-to-Peer Server
BMISocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # Socket for jetson-bmi connection, named as such
BMISocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
BMISocket.bind((jetsonHostIP, jetsonListenerPort))
BMISocket.listen(1)

BMIConn, BMIAddr = BMISocket.accept()
print(f"In audioRecordingClient -- Connected to BMI through {BMIAddr}")







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
    global beginStop

    while(not beginStop):
        # print("In audioRecordingClient.recordAudio() -- Entered recordAudio while loop!")

        # Getting data from microphone
        length, data = micInput.read()

        if length:
            # Print statements for chatter
            # print("In audioRecordingClient.recordAudio() -- Got audio data!")
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
                print("In audioRecordingClient.recordAudio() -- Unsupported flag value!")
            







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
        # print("In audioRecordingClient.sendAudio(): Entered sendAudio while loop!")

        # Handling condition if program was told to stop via transmission from BMI (forwarded from Ingestor)
        if(beginStop == True):
            # print("audioRecordingClient.py -- Entered beginStop if statement!")

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
                    # print("Got data!")
                    try:
                        ingestSocket.sendall(totalPacket)
                        # print("Packet sent!")
                    except Exception as e:
                        print(f"Error in audioRecordingClient.sendAudio(): {e}")

                    # Setting data back to null so it doesn't send the same data infinitely                            
                    data = None

                # No more data in buffers, so it is safe to send transmission finished message to Ingestor
                else:
                    print("In audioRecordingClient.sendAudio() -- No data left, sending endStop trigger!")
                    try:
                        totalPacket = b'END_STOP' + bytearray(metadataSize + (2 * CHUNK_SIZE) - len(b"END_STOP"))
                        ingestSocket.sendall(totalPacket)
                        print("In audioRecordingClient.sendAudio() -- Sent endStop trigger!")
                        endStop = True

                    except Exception as e:
                        print(f"In audioRecordingClient.sendAudio() -- Error in sendAudio(): {e}")
            
            

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
            # print("In audioRecordingClient.sendAudio() -- Audio buffers are empty, probably just started program!")

        # Sending data over TCP
        if data:
            try:
                ingestSocket.sendall(totalPacket)
                # print("Packet sent!")
            except Exception as e:
                print(f"In audioRecordingClient.sendAudio() -- {e}")
                break
    
    # Closing all connections and such to stop program
    print("In audioRecordingClient.sendAudio() -- Program has successfully concluded!")
    time.sleep(2)
    ingestSocket.close()
    BMISocket.close()
    BMIConn.close()
        







def recieveStop():
    global beginStop

    print("In audioRecordingClient.recieveStop() -- Stopping thread is executing.")

    stopMessage = recvAll(BMIConn, 10)

    if(stopMessage.startswith(b'BEGIN_STOP')):
        print("In audioRecordingClient.recieveStop() -- Received beginStop trigger!")
        beginStop = True
    else:
        print("In audioRecordingClient.recieveStop() -- Error: Did not receive beginStop trigger.")
    








# def recieveFrequency():
#     while True:
#         frequency = conn.recv(4)
#         frequency = struct.unpack('!f', frequency)[0]
#         print(frequency)

#         audioData = generateWaveform(frequency)

#         speaker.write(audioData)












# Start threads only if we have a connection
recordingThread = threading.Thread(target=recordAudio, daemon=True)
recordingThread.start()

sendingThread = threading.Thread(target=sendAudio, daemon=True)
sendingThread.start()

stoppingThread = threading.Thread(target=recieveStop, daemon=True)
stoppingThread.start()

# The join function waits to close the main thread until the thread that the join
# function is being called on finishes. I was encountering issues with the main thread
# doing this and it was throwing errors.
stoppingThread.join()
recordingThread.join()
sendingThread.join()

# receiveFrequencyThread = threading.Thread(target = recieveFrequency, daemon=True)
# receiveFrequencyThread.start()