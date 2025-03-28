import socket
import time
import numpy as np
import struct
import yaml
from yaml import SafeLoader

with open('settings.yaml', 'r') as settingsFile:
    data = list(yaml.load(settingsFile, Loader=SafeLoader))
    
    # Network settings
    ingestHostIP = data[0]['ingestorSettings']['ingestorIPAddress']
    ingestListenerPort = data[0]['ingestorSettings']['ingestorListenerPort']
    ingestjetsonBMIPort = data[1]['jetsonSettings']['ingestorJetsonCommPort']
    ingestBMIPort = data[2]['BMISettings']['ingestorBMICommPort']

    jetsonHostIP = data[1]['jetsonSettings']['jetsonIPAddress']
    jetsonListenerPort = data[1]['jetsonSettings']['jetsonListenerPort']
    jetsonBMIPort = data[2]['BMISettings']['jetsonBMICommPort']

    BMIIPAddress = data[2]['BMISettings']['BMIIPAddress']

    settingsFile.close()



# Connecting to Server
ingestSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ingestSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
ingestSocket.bind((ingestHostIP, ingestBMIPort))
ingestSocket.connect((ingestHostIP, ingestListenerPort))
print("In programStopClient -- Connected to Ingestor!")

# Connecting to Peer-to-Peer Server
jetsonSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
jetsonSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
jetsonSocket.bind((jetsonHostIP, jetsonBMIPort))
jetsonSocket.connect((jetsonHostIP, jetsonListenerPort))
print("In programStopClient -- Connected to Jetson!")

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
    jetsonSocket.sendall(packedFrequency + expansionBytes)
    time.sleep(1/30)
    frequency += 100

frequency = 0
packedFrequency = struct.pack('>f', frequency)
jetsonSocket.sendall(packedFrequency + expansionBytes)
time.sleep(20)


# Transmitting stop flag
jetsonSocket.sendall(beginStopMessage)
print("In programStopClient -- Sent beginStop trigger!")
ingestSocket.close()
jetsonSocket.close()