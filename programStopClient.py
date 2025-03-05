import socket
import time
import numpy as np

# Defining Server Parameters
HOST = '127.0.0.1'
PORT = 36783

# Connecting to Server
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT));
print("Connected!");


time.sleep(10)

s.sendall(bytearray(4))
print("Sent stopping message!")
s.close()