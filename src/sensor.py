# Sparkfun libraries for OTOS sensor tx/rx:
import qwiic_otos

from collections import deque
from datetime import datetime
import os.path
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from .utils import unix_time_millis


class Sensor:
    BUF_SIZE = 36

    def __init__(self, address):
        self.address = address
        self.device = qwiic_otos.QwiicOTOS(address=self.address)
        self.data_buffer = deque(maxlen=self.BUF_SIZE)
        self.meta_buffer = deque(maxlen=self.BUF_SIZE)

        if not self.device.is_connected():
            raise ConnectionError(
                f"Sensor at address {hex(self.address)} not connected."
            )

    def begin(self):
        self.device.begin()

    def poll_data(self):
        data = self.device.getPosVelAcc()
        if data:
            metadata = unix_time_millis(datetime.now())
            self.data_buffer.append(data)
            self.meta_buffer.append(metadata)

    def get_next(self):
        if len(self.data_buffer) > 0:
            return self.meta_buffer.popleft(), self.data_buffer.popleft()
        return None, None

