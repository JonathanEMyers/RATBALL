import collections
import cv2
import os
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



class testClass:
    def __init__(self, ID, camera_width, camera_height, buffer_length, framerate):
        self.width = camera_width
        self.height = camera_height
        self.ID = ID

        # Current_buffer starts out at one
        
        # Buffer size is the amount of objects that can be stored in the buffer, and
        # buffer_length is the amount of time that a buffer should take up
        self.buffer_size = buffer_length

        # This is the list of buffers
        self.data_buffer_list = collections.deque()
        self.meta_buffer_list = collections.deque()

        # Appending initial buffer to the list of buffers
        self.data_buffer_list.append(collections.deque(maxlen=self.buffer_size))
        self.meta_buffer_list.append(collections.deque(maxlen=self.buffer_size))


    def append_data(self):

        current_buffer = len(self.data_buffer_list) - 1

        # Generating fake frame data
        frame_bytes = bytearray(1280*720)

        time_now = datetime.now()
        time_since_epoch = unix_time_millis(time_now)
        time_since_epoch_packed = struct.pack('d', time_since_epoch)

        # Appending data to current buffer
        self.data_buffer_list[current_buffer].append(frame_bytes)
        self.meta_buffer_list[current_buffer].append(time_since_epoch_packed)

        print(current_buffer)

        # If the current buffer grows to its max size, append another buffer to the buffer list
        if(len(self.data_buffer_list[current_buffer]) >= self.buffer_size):
            self.data_buffer_list.append(collections.deque(maxlen=self.buffer_size))
            self.meta_buffer_list.append(collections.deque(maxlen=self.buffer_size))

        return(True)





    def get_data(self):

        # Only attempt to get data if the bottom buffer has data, and also if there is more than one
        # buffer in the buffer list
        # --> This is so that the zeroeth buffer is not both getting filled and taken from at the same time
        if(len(self.data_buffer_list) > 1 and len(self.data_buffer_list[0]) > 0):

            # Getting data and metadata off the zeroeth buffer
            data = self.data_buffer_list[0].popleft()
            metadata = self.meta_buffer_list[0].popleft()

            # If the zeroeth buffer has a length of zero, then pop it off of the buffer list
            if(len(self.data_buffer_list[0]) <= 0):
                self.data_buffer_list.popleft()
                self.meta_buffer_list.popleft()
            
            # Return the gathered data
            return(data, metadata)
        
        # Case where data cannot be retrieved due to current buffer lengths
        else:
            # Return false to indicate that data was not gathered
            return(False)