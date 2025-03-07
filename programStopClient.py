import socket
import time
import numpy as np

# Defining Server Parameters
HOST = '127.0.0.1'
PORT = 36783

# Connecting to Server
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT));
print("In programStopClient -- Connected!");

# Defining stop message
beginStopMessage = b'BEGIN_STOP'

# Waiting 10 seconds to simulate a short experiment
time.sleep(300)

# Transmitting stop flag
s.sendall(beginStopMessage)
print("In programStopClient -- Sent beginStop trigger!")
s.close()