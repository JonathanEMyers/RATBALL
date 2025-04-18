import collections
import alsaaudio as aa
from datetime import datetime, timezone

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
        

        
    def appendMicData(self, whichBuffer):
        length, data = self.micInput.read()

        if(whichBuffer and len(self.dataBufferOne) < self.bufferSize):
            self.dataBufferOne.append(data)
            self.metaBufferOne.append(b'00000000')

        elif(not whichBuffer and len(self.dataBufferTwo) < self.bufferSize):
            self.dataBufferTwo.append(data)
            self.metaBufferTwo.append(b'00000000')

        else:
            return("In Microphone.appendMicData() -- Both buffers are full!")
        


    

    def popMicData(self, whichBuffer):
        
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
        



    

    


