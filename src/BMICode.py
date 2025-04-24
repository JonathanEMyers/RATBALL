import socket
import time
import numpy as np
import struct
import yaml
from yaml import SafeLoader

settingsFilename = "settings.yaml"

with open(settingsFilename, 'r') as settingsFile:
    data = list(yaml.load(settingsFile, Loader=SafeLoader))
    
    # Network settings
    ingestHostIP = data[0]['ingestorSettings']['ingestorIPAddress']
    ingestListenerPort = data[0]['ingestorSettings']['ingestorListenerPort']
    ingestBMIPort = data[2]['BMISettings']['ingestorBMICommPort']

    BMIHostIP = data[2]['BMISettings']['BMIIPAddress']
    BMIListenerPort = data[2]['BMISettings']['BMIListenerPort']
    BMIJetsonPort = data[1]['jetsonSettings']['BMIJetsonCommPort']

    settingsFile.close()



# Connecting to Server
ingestSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ingestSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
ingestSocket.bind((ingestHostIP, ingestBMIPort))
ingestSocket.connect((ingestHostIP, ingestListenerPort))
print("In BMICode -- Connected to Ingestor!")


# Establishing Peer-to-Peer Server
jetsonSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # Socket for jetson-bmi connection, named as such
jetsonSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
jetsonSocket.bind((BMIHostIP, BMIListenerPort))
jetsonSocket.listen(1)

jetsonConn, jetsonAddr = jetsonSocket.accept()
print(f"In BMICode -- Connected to Jetson through {jetsonAddr}")


# Defining stop message
beginStopMessage = b'BEGIN_STOP' # Message can be changed, just a prototype

# Waiting to simulate experiment time
numMinutes = 0
numSeconds = 20

# Defining speaker frequency
frequency = 500

# Byte array for possible expansion later down the line
expansionBytes = b'000000'


# Sending various frequencies
while(frequency < 10000):
    packedFrequency = struct.pack('>f', frequency)
    jetsonConn.sendall(packedFrequency + expansionBytes)
    time.sleep(1/30)
    frequency += 100

frequency = 0
packedFrequency = struct.pack('>f', frequency)
jetsonConn.sendall(packedFrequency + expansionBytes)
time.sleep(31)


# Transmitting stop flag
jetsonConn.sendall(beginStopMessage)
print("In BMICode -- Sent beginStop trigger!")
ingestSocket.close()
jetsonConn.close()
jetsonSocket.close()