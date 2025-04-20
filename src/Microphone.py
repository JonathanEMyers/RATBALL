import collections
import alsaaudio as aa
from datetime import datetime, timezone
import struct

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



class Microphone:
    def __init__(self, bufSize, rate, channels, format, framerate):
        self.metaBufferOne = collections.deque(maxlen=bufSize)
        self.metaBufferTwo = collections.deque(maxlen=bufSize)

        self.dataBufferOne = collections.deque(maxlen=bufSize)
        self.dataBufferTwo = collections.deque(maxlen=bufSize)

        chunkSize = int(rate / framerate)

        self.micInput = aa.PCM(type=aa.PCM_CAPTURE, 
                               mode=aa.PCM_NORMAL, 
                               channels=channels, 
                               rate=rate, 
                               format=format, 
                               periodsize=chunkSize)
        
        self.bufferSize = bufSize

        # Just for debugging purposes
        self.frameCount = 0
        

        
    def appendMicData(self, whichBuffer):
        length, data = self.micInput.read()
        timeNow = datetime.now()
        timeSinceEpoch = unix_time_millis(timeNow)
        timeSinceEpochPacked = struct.pack('d', timeSinceEpoch)

        if(whichBuffer and len(self.dataBufferOne) < self.bufferSize):
            self.dataBufferOne.append(data)
            self.metaBufferOne.append(timeSinceEpochPacked)
            self.frameCount += 1
            return(True)

        elif(not whichBuffer and len(self.dataBufferTwo) < self.bufferSize):
            self.dataBufferTwo.append(data)
            self.metaBufferTwo.append(timeSinceEpochPacked)
            self.frameCount += 1
            return(True)

        else:
            return(False)
        



    def popMicData(self, whichBuffer):

        # print(f"whichBuffer = {whichBuffer}")
        # print(f"DB1={len(self.dataBufferOne)}, MB1={len(self.metaBufferOne)}, DB2={len(self.dataBufferTwo)}, MB2={len(self.metaBufferTwo)}")
        
        if(not whichBuffer and len(self.dataBufferOne) > 0):
            data = self.dataBufferOne.popleft()
            metadata = self.metaBufferOne.popleft()

            return(metadata, data)

        elif(whichBuffer and len(self.dataBufferTwo) > 0):
            data = self.dataBufferTwo.popleft()
            metadata = self.metaBufferTwo.popleft()

            return(metadata, data)

        else:
            return("In Microphone.popMicData() -- Specified buffer is empty!")
        



    

    


