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
import cv2


# TO-DO:
#   - When I can use the jetson, mic, and speaker, assign the specific PCM/output devices


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
audioMetaSize = 26              # 26 for capture timestamp size
videoMetaSize = 26              # 26 for capture timestamp
otherMetaSize = 26 + 4          # 26 for sending timestamp and 4 for frame count
metadataSize = audioMetaSize + videoMetaSize + otherMetaSize
frameCounter = 1


# Set Speaker Parameters
speakerFrequency = 0


# Open PCM Device for Microphone
micInput = aa.PCM(type=aa.PCM_CAPTURE, 
                  mode=aa.PCM_NORMAL, 
                  channels=CHANNELS, 
                  rate=RATE, 
                  format=FORMAT, 
                  periodsize=CHUNK_SIZE)


# Setting Buffer Parameters
bufferSize = bufferLength * framerate
audioBufferOne = collections.deque(maxlen=bufferSize)
audioMetaBufferOne = collections.deque(maxlen=bufferSize)
audioBufferTwo = collections.deque(maxlen=bufferSize)
audioMetaBufferTwo = collections.deque(maxlen=bufferSize)

camZeroBufferOne = collections.deque(maxlen=bufferSize)
camOneBufferOne = collections.deque(maxlen=bufferSize)
videoMetaBufferOne = collections.deque(maxlen=bufferSize)
camZeroBufferTwo = collections.deque(maxlen=bufferSize)
camOneBufferTwo = collections.deque(maxlen=bufferSize)
videoMetaBufferTwo = collections.deque(maxlen=bufferSize)

whichAudioBuffer = True             # True for bufferOne, False for bufferTwo
whichVideoBuffer = True
beginStop = False

# Define camera pipeline
def gstreamer_pipeline(sensor_id=0, width=1280, height=720):
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), width={width}, height={height}, format=NV12, framerate={framerate}/1 ! "
        f"nvvidconv flip-method=0 ! "
        f"video/x-raw, width={width}, height={height}, format=BGRx ! "
        f"videoconvert ! video/x-raw, format=BGR ! appsink"
    )


# Initalize both cameras
cap0 = cv2.VideoCapture(gstreamer_pipeline(sensor_id=0), cv2.CAP_GSTREAMER)
cap1 = cv2.VideoCapture(gstreamer_pipeline(sensor_id=1), cv2.CAP_GSTREAMER)


if not (cap0.isOpened() and cap1.isOpened()):
    print("Error: Could not open one or both cameras.")
    cap0.release()
    cap1.release()
    exit()



# Connecting to Server
ingestSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ingestSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # So the system does not wait so long after the program terminates to close the socket
ingestSocket.bind((ingestHostIP, ingestJetsonPort))
ingestSocket.connect((ingestHostIP, ingestListenerPort))
print("In audioRecordingClient -- Connected to ingestor!")


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










# recordAudio() is a function to input audio from an ALSAaudio device
# and put it in one of two buffers that can be accessed globally.
#
# The buffers are both lists in the collections library, which are essentially 
# double ended lists that can be accessed from both sides. Each time a section
# of audio is recorded, the length of which specified by the CHUNK_SIZE variable,
# it appends this to the designated buffer.
#
# It utilizes the whichAudioBuffer global flag variable, if whichAudioBuffer is true
# it will push audio data into buffer one, if it is false it will push audio
# data into buffer two.
#
# Furthermore, once one of the buffers are filled up, a global flag associated
# with that buffer will be marked true so this condition can be known by other 
# functions. The whichAudioBuffer flag will also be toggled when one of the buffers
# is filled.
def recordAudio():
    global whichAudioBuffer
    global beginStop

    while(not beginStop):
        # print("In audioRecordingClient.recordAudio() -- Entered recordAudio while loop!")

        # Getting data from microphone
        length, data = micInput.read()

        if length:
            # print(f"Buffer One Size: {len(audioBufferOne)}, Buffer Two Size: {len(audioBufferTwo)}")
            # Print statements for chatter
            # print("In audioRecordingClient.recordAudio() -- Got audio data!")
            # print("Length of audio buffer one:")
            # print(len(audioBufferOne))
            # print(len(audioMetaBufferOne))
            # print("Length of audio buffer two")
            # print(len(audioBufferTwo))
            # print(len(audioMetaBufferTwo))
            # print("\n")

            # whichAudioBuffer being true means stack up bufferOne and transmit from bufferTwo
            if(whichAudioBuffer == True):

                # Appending audio data and metadata to associated lists
                audioBufferOne.append(data)
                now = datetime.now()
                timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f").encode("utf-8")
                audioMetaBufferOne.append(timestamp)

                # Switching flag to indicate bufferOne is full
                if(len(audioBufferOne) >= bufferSize):
                    # print("Size of bufferOne at full:")
                    # print(len(audioBufferOne))
                    whichAudioBuffer = False

            # whichAudioBuffer being false means stack up bufferTwo and transmit from bufferOne
            elif(whichAudioBuffer == False):

                # Appending audio data and metadata to associated lists
                audioBufferTwo.append(data)
                now = datetime.now()
                timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f").encode("utf-8")
                audioMetaBufferTwo.append(timestamp)
                
                # Switching flag to indicate bufferTwo is full
                if(len(audioBufferTwo) >= bufferSize):
                    whichAudioBuffer = True
                    # print("Size of bufferTwo at full:")
                    # print(len(audioBufferTwo))

            else:
                print("In audioRecordingClient.recordAudio() -- Unsupported flag value!")








def recordVideo():
    global whichVideoBuffer
    global beginStop

    startTime = time.perf_counter()
    frameCount = 0
    frameInterval = 1/framerate


    while(not beginStop):
        
        frameStart = time.perf_counter()

        ret0, frame0 = cap0.read()
        ret1, frame1 = cap1.read()

        if ret0 and ret1:
            # print(f"Buffer One Size: {len(audioBufferOne)}, Buffer Two Size: {len(audioBufferTwo)}")
            # Print statements for chatter
            # print("In audioRecordingClient.recordAudio() -- Got audio data!")
            # print("Length of audio buffer one:")
            # print(len(audioBufferOne))
            # print(len(audioMetaBufferOne))
            # print("Length of audio buffer two")
            # print(len(audioBufferTwo))
            # print(len(audioMetaBufferTwo))
            # print("\n")

            # Timestamping for metadata and frames
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.%f")[:-3]
            cv2.putText(frame0, timestamp, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
            cv2.putText(frame1, timestamp, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

            frameZeroBytes = frame0.tobytes()
            frameOneBytes = frame1.tobytes()

            # whichVideoBuffer being true means stack up bufferOne and transmit from bufferTwo
            if(whichVideoBuffer == True):

                # Appending audio data and metadata to associated lists
                camZeroBufferOne.append(frameZeroBytes)
                camOneBufferOne.append(frameOneBytes)
                videoMetaBufferOne.append(timestamp)

                # Switching flag to indicate bufferOne is full
                if(len(camZeroBufferOne) >= bufferSize or len(camOneBufferOne) >= bufferSize):
                    whichVideoBuffer = False

            # whichVideoBuffer being false means stack up bufferTwo and transmit from bufferOne
            elif(whichVideoBuffer == False):

                # Appending audio data and metadata to associated lists
                camZeroBufferTwo.append(frameZeroBytes)
                camOneBufferTwo.append(frameOneBytes)
                videoMetaBufferTwo.append(timestamp)
                
                # Switching flag to indicate bufferTwo is full
                if(len(camZeroBufferTwo) >= bufferSize or len(camOneBufferTwo) >= bufferSize):
                    whichVideoBuffer = True

            else:
                print("In audioRecordingClient.recordAudio() -- Unsupported flag value!")
            
        frameCount += 1
        elapsedTime = time.perf_counter() - frameStart
        sleepTime = max(0, frameInterval - elapsedTime)
        time.sleep(sleepTime)
            







# sendData() is a function to take audio from one of the two buffer discussed
# in recordAudio(), and send them over the network.
#
# The two buffers are double ended lists in the collections library, and therefore
# can be accessed using the popleft() function. This is used to pop audio data
# off of the buffers. The audio chunk that is popped off will then be sent over
# the network. Once the specified buffer by the global whichBuffer variable 
# (discused more thoroughly in recordAudio()) reaches a length of zero, which means
# that all data has been sent, it will toggle the bufferXFull variables.
def sendData():
    global whichAudioBuffer
    global whichVideoBuffer
    global beginStop
    global frameCounter
    endStop = False
    isAudioData = True
    isVideoData = True

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
        # print("In audioRecordingClient.sendData(): Entered sendData while loop!")

        # Handling condition if program was told to stop via transmission from BMI (forwarded from Ingestor)
        if(beginStop == True):
            # print("audioRecordingClient.py -- Entered beginStop if statement!")

            # endStop flag becomes true once all data is saved from buffers (to prevent data loss on shutdown)
            while(not endStop):

                # Getting audio data -- Get data out of buffer one first, then two
                if(len(audioBufferOne) > 0):
                    audioData = audioBufferOne.popleft()
                    audioMetadata = audioMetaBufferOne.popleft()
                    isAudioData = True
                elif(len(audioBufferTwo) > 0):
                    audioData = audioBufferTwo.popleft()
                    audioMetadata = audioMetaBufferTwo.popleft()
                    isAudioData = True
                else:
                    audioData = bytearray(2 * CHUNK_SIZE)                               # In case there is no more audio data but there is still video data
                    audioMetadata = b'No_Data_Available_________'    
                    isAudioData = False  


                # Getting video data -- Get data out of buffer one first, then two
                if(len(camZeroBufferOne) > 0 and len(camOneBufferOne) > 0):
                    videoData = camZeroBufferOne.popleft() + camOneBufferOne.popleft()
                    videoMetadata = videoMetaBufferOne.popleft()
                    isVideoData = True
                elif(len(camZeroBufferTwo) > 0 and len(camOneBufferTwo) > 0):
                    videoData = camZeroBufferTwo.popleft() + camOneBufferTwo.popleft()
                    videoMetadata = videoMetaBufferTwo.popleft()
                    isVideoData = True
                else:
                    videoData = bytearray(1280 * 720 * 3) + bytearray(1280 * 720 * 3)   # In case there is no more video data but there is still audio data
                    videoMetadata = b'No_Data_Available_________'
                    isVideoData = False


                # Assembling total packet and sending it
                if(isVideoData or isAudioData):
                    now = datetime.now()
                    sentTime = now.strftime("%Y-%m-%d %H:%M:%S.%f").encode("utf-8")
                    frameCountPacked = struct.pack(">I", frameCounter)

                    totalPacket = frameCountPacked + sentTime + audioMetadata + videoMetadata + audioData + videoData

                    try:
                        ingestSocket.sendall(totalPacket)
                        # print("Packet sent!")
                    except Exception as e:
                        print(f"Error in audioRecordingClient.sendData(): {e}")

                    # Setting data back to null so it doesn't send the same data infinitely                            
                    totalPacket = None
                    frameCounter += 1

                # No more data in buffers, so it is safe to send transmission finished message to Ingestor
                else:
                    print("In audioRecordingClient.sendData() -- No data left, sending endStop trigger!")
                    try:
                        stopMessage = b"END_STOP"

                        totalPacket = stopMessage + bytearray((metadataSize) + (2 * CHUNK_SIZE) + (2 * 1280 * 720 * 3) - len(stopMessage))

                        ingestSocket.sendall(totalPacket)
                        print("In audioRecordingClient.sendData() -- Sent endStop trigger!")
                        endStop = True

                    except Exception as e:
                        print(f"In audioRecordingClient.sendData() -- Error in sendData(): {e}")
            
            
        else:
            # Getting audio data
            if(not whichAudioBuffer and len(audioBufferOne) > 0):
                audioData = audioBufferOne.popleft()
                audioMetadata = audioMetaBufferOne.popleft()
                isAudioData = True
            elif(whichAudioBuffer and len(audioBufferTwo)):
                audioData = audioBufferTwo.popleft()
                audioMetadata = audioMetaBufferTwo.popleft()
                isAudioData = True
            else:
                audioData = bytearray(2 * CHUNK_SIZE)                               # In case there is no more audio data but there is still video data
                audioMetadata = bytearray(audioMetaSize)    
                isAudioData = False                    
            
            # Getting video data
            if(not whichVideoBuffer and len(camZeroBufferOne) > 0 and len(camOneBufferOne) > 0):
                videoData = camZeroBufferOne.popleft() + camOneBufferOne.popleft()
                videoMetadata = videoMetaBufferOne.popleft()
                isVideoData = True
            elif(whichVideoBuffer and len(camZeroBufferTwo) > 0 and len(camOneBufferTwo) > 0):
                videoData = camZeroBufferTwo.popleft() + camOneBufferTwo.popleft()
                videoMetadata = videoMetaBufferTwo.popleft()
                isVideoData = True
            else:
                videoData = bytearray(1280 * 720 * 3) + bytearray(1280 * 720 * 3)   # In case there is no more video data but there is still audio data
                videoMetadata = bytearray(videoMetaSize)
                isVideoData = False

        # Assembling packet and sending it
        if(isVideoData or isAudioData):    # Checking if there is either video or audio data, because if there is neither then there is no point in sending
            now = datetime.now()
            sentTime = now.strftime("%Y-%m-%d %H:%M:%S.%f").encode("utf-8")
            frameCountPacked = struct.pack(">I", frameCounter)

            totalPacket = frameCountPacked + sentTime + audioMetadata + videoMetadata + audioData + videoData

            try:
                ingestSocket.sendall(totalPacket)
                # print("Packet sent!")
            except Exception as e:
                print(f"In audioRecordingClient.sendData() -- {e}")
                break

            frameCounter += 1

        
        
        
        
        #### FOR REFERENCE ON 3 Apr 2025, GET RID OF SOON
        
        # # Getting audio data and metadata from buffer one
        # elif(not whichAudioBuffer and len(audioBufferOne) > 0):
        #     data = audioBufferOne.popleft()
        #     metadata = audioMetaBufferOne.popleft()
        #     now = datetime.now()
        #     timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f").encode("utf-8")
        #     frameCountPacked = struct.pack(">I", frameCounter)
        #     totalPacket = metadata + timestamp + frameCountPacked + data
        #     frameCounter = frameCounter + 1
        #     # print(len(data))
        #     # print(len(metadata))
        #     # print(len(totalPacket))

        # # Getting audio data and metadata from buffer two
        # elif(whichAudioBuffer and len(audioBufferTwo) > 0):
        #     data = audioBufferTwo.popleft()
        #     metadata = audioMetaBufferTwo.popleft()
        #     now = datetime.now()
        #     timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f").encode("utf-8")
        #     frameCountPacked = struct.pack(">I", frameCounter)
        #     totalPacket = metadata + timestamp + frameCountPacked + data
        #     frameCounter = frameCounter + 1
        #     # print(len(data))
        #     # print(len(metadata))
        #     # print(len(totalPacket))

        # # Buffer indicated by whichAudioBuffer is empty, will probably occur at the start of a program run
        # else:
        #     data = None
        #     # print("In audioRecordingClient.sendData() -- Audio buffers are empty, probably just started program!")

        # # Sending data over TCP
        # if data:
        #     try:
        #         ingestSocket.sendall(totalPacket)
        #         # print("Packet sent!")
        #     except Exception as e:
        #         print(f"In audioRecordingClient.sendData() -- {e}")
        #         break
    
    # Closing all connections and such to stop program
    print("In audioRecordingClient.sendData() -- Program has successfully concluded!")
    time.sleep(2)
    ingestSocket.close()
    BMISocket.close()
    BMIConn.close()
        







def recieveStop():
    global beginStop
    global speakerFrequency

    print("In audioRecordingClient.recieveStop() -- Stopping thread is executing.")


    while(not beginStop):
        message = recvAll(BMIConn, 10)

        if(message.startswith(b'BEGIN_STOP')):
            print("In audioRecordingClient.recieveStop() -- Received beginStop trigger!")
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

sendingThread = threading.Thread(target=sendData, daemon=True)
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