import collections
import cv2
from datetime import datetime, timezone
import struct


# This function returns the syntax necessary for setting up the IR cameras
def gstreamer_pipeline(sensor_id, width, height):
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), width={width}, height={height}, format=NV12, framerate={framerate}/1 ! "
        f"nvvidconv flip-method=0 ! "
        f"video/x-raw, width={width}, height={height}, format=BGRx ! "
        f"videoconvert ! video/x-raw, format=GRAY8 ! appsink"
    )


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


class camera:
    def __init__(self, ID, camera_width, camera_height, buffer_length, framerate):
        self.width = camera_width
        self.height = camera_height
        self.ID = ID

        # Current_buffer starts out at one
        current_buffer = 0

        # Initializing camera objects
        self.cap = cv2.VideoCapture(
            gstreamer_pipeline(self.ID, self.width, self.height), cv2.CAP_GSTREAMER
        )

        # Buffer size is the amount of objects that can be stored in the buffer, and
        # buffer_length is the amount of time that a buffer should take up
        self.buffer_size = buffer_length * framerate

        # This is the list of buffers
        self.data_buffer_list = collections.deque()
        self.meta_buffer_list = collections.deque()

        # Appending initial buffer to the list of buffers
        self.data_buffer_list.append(collections.deque(maxlen=self.buffer_size))
        self.meta_buffer_list.append(collections.deque(maxlen=self.buffer_size))

    def append_data(self):
        # Setting current buffer
        current_buffer = len(self.data_buffer_list) - 1

        # Getting data from camera object
        ret, frame = self.cap.read()

        # Handling case where camera object is unable to read frame
        if not (ret):
            print(
                f"In camera.append_data() -- Unable to grab frame from camera {self.ID}"
            )
            return False

        # If a frame is retrieved
        else:
            # Getting time of capture metadata
            time_now = datetime.now()
            time_since_epoch = unix_time_millis(time_now)
            time_since_epoch_packed = struct.pack("d", time_since_epoch)

            # Time stamp overlay to frames
            timestamp = time_now.strftime("%Y-%m-%d_%H-%M-%S.%f")[:-3]
            cv2.putText(
                frame,
                timestamp,
                (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

            # Flattenning the frame to a byte array for transmission
            frame_bytes = frame.tobytes()

            # Appending data to current buffer
            self.data_buffer_list[current_buffer].append(frame_bytes)
            self.meta_buffer_list[current_buffer].append(time_since_epoch_packed)

            # If the current buffer grows to its max size, increment current_buffer
            # to indicate using the next buffer
            if len(self.data_buffer_list[current_buffer]) >= self.buffer_size:
                self.data_buffer_list.append(collections.deque(maxlen=self.buffer_size))
                self.meta_buffer_list.append(collections.deque(maxlen=self.buffer_size))

            return True

    def get_data(self):
        # Only attempt to get data if the bottom buffer has data, and also if there is more than one
        # buffer in the buffer list
        # --> This is so that the zeroeth buffer is not both getting filled and taken from at the same time
        if len(self.data_buffer_list) > 1 and len(self.data_buffer_list[0]) > 0:
            # Getting data and metadata off the zeroeth buffer
            data = self.data_buffer_list[0].popleft()
            metadata = self.meta_buffer_list[0].popleft()

            # If the zeroeth buffer has a length of zero, then pop it off of the buffer list
            if len(self.data_buffer_list[0] <= 0):
                self.data_buffer_list.popleft()
                self.meta_buffer_list.popleft()

            # Return the gathered data
            return (data, metadata)

        # Case where data cannot be retrieved due to current buffer lengths
        else:
            # Return false to indicate that data was not gathered
            return False
