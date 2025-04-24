import threading
import time
import sys
import os
import datetime

self_path = os.path.abspath(__file__)
self_dir = os.path.split(self_path)[0]
sys.path.append(os.path.join(self_dir, '../src'))
from sensor import Sensor

sensor_manifest = [Sensor(0x17), Sensor(0x67)]
for sensor in sensor_manifest:
    sensor.begin()

def unix_time_millis(dt):
    """formats timestamps as milliseconds-since-epoch (double-precision float, only requires 8 bytes)"""
    unix_epoch = datetime.fromtimestamp(0, timezone.utc)

    if dt.tzinfo is None:
        # make dt offset-aware in UTC if it's naive
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # convert to UTC if it's aware in a different timezone
        dt = dt.astimezone(timezone.utc)
    return (dt - unix_epoch).total_seconds() * 1000.0


class SensorPlotter():
    def __init__(self, dataClass):
        self._dataClass = dataClass
        self.hLine = plt.plot(0,0)
        self.ani = FuncAnimation(plt.gcf(), self.run, interval = 1000, repeat=True)

    def run(self, i):
        self.hLine.set_data(self._dataClass.x, self._dataClass.y)
        self.hLine.axes.relim()
        self.hLine.axes.autoscale_view()


class SensorData():
    def __init__(self):
        self.time = []
        self.x = []
        self.y = []
        self.h = []


class SensorPoll(threading.Thread):
    def __init__(self, sensor_data, i2c_address):
        threading.Thread.__init__(self)

        self.device = qwiic_otos.QwiicOTOS(address=i2c_address)
        self._sensor_data = sensor_data
        self._period = 0.25
        self._nextCall = time.time()

        self.device.begin()

    def run(self):
        while True:
            data = self.device.getPosVelAcc()
            self._sensor_data.time.append(unix_time_millis(datetime.now()))
            self._sensor_data.x.append(data.x)
            self._sensor_data.y.append(data.y)
            self._sensor_data.h.append(data.h)
            self._nextCall = self._nextCall + self._period
            time.sleep(self._nextCall - time.time())


data = SensorData()
plotter = SensorPlotter(data)
poller = SensorPoll(data, 0x17)

poller.start()
plt.show()


