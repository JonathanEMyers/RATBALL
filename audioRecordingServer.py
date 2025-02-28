import socket
import alsaaudio as aa
import struct

# Defining Networking Parameters
HOST = '127.0.0.1';
PORT = 36783;

# Defining Audio Parameters
channels = 1;
rate = 44100;
format = aa.PCM_FORMAT_S16_LE;
chunkSize = 882 * 2;
metadataSize = 26;

# Defining Frequency Stream Parameters
frequency = 200.0;

# Accepting information
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT));
    print("Connected!");

    # Opening audio storage file
    with open("audioOne.raw", "wb") as fAudio:
        # Opening metadata storage file
        with open("audioOne.txt", "w") as fMeta:
            print("Opened file!")

            # Attempting to recieve TCP packets from jetson
            try:
                while True:
                    totalPacket = s.recv(metadataSize + chunkSize)
                    metadata = totalPacket[:26].decode("utf-8")
                    data = totalPacket[26:]

                    fAudio.write(data)
                    fMeta.write(metadata)
                    
                    # Legacy code from sending frequencies
                    # if(frequency < 500):
                    #     frequency = frequency + 1.0;
                    # else:
                    #     frequency = 200.0;

                    # s.sendall(struct.pack('!f', frequency));

            except KeyboardInterrupt:
                print("Stopping");
            finally:
                s.close()
                fAudio.close()
                fMeta.close()