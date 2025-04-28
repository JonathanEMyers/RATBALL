import qwiic_otos
import threading
import time
import sys
import os
from datetime import datetime, timezone
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

matplotlib.use("qtagg")

self_path = os.path.abspath(__file__)
self_dir = os.path.split(self_path)[0]
sys.path.append(os.path.join(self_dir, "../src"))
from sensor import Sensor

sensor_manifest = [Sensor(0x17), Sensor(0x67)]
for sensor in sensor_manifest:
    sensor.begin()


def unix_time_millis(dt):
    unix_epoch = datetime.fromtimestamp(0, timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return (dt - unix_epoch).total_seconds() * 1000.0


class SensorPlotter:
    def __init__(self, sensor_data):
        self._sensor_data = sensor_data
        self.lines = [plt.plot(0, 0)[0] for _ in range(4)]
        self.ani = FuncAnimation(plt.gcf(), self.run, interval=10, repeat=True)

    def run(self, i):
        vals = [
            self._sensor_data.x,
            self._sensor_data.vx,
            self._sensor_data.y,
            self._sensor_data.vy,
        ]
        for j, line in enumerate(self.lines):
            line.set_data(self._sensor_data.time, vals[j])
            line.axes.relim()
            line.axes.autoscale_view()


class SensorData:
    def __init__(self):
        self.time = []
        self.x = []
        self.vx = []
        self.y = []
        self.vy = []
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
            self._sensor_data.x.append(data[0].x)
            self._sensor_data.vx.append(data[1].x)
            self._sensor_data.y.append(data[0].y)
            self._sensor_data.vy.append(data[1].y)
            self._sensor_data.h.append(data[0].h)
            self._nextCall = self._nextCall + self._period
            time.sleep(self._nextCall - time.time())


data = SensorData()
plotter = SensorPlotter(data)
poller = SensorPoll(data, 0x17)

poller.start()
plt.show()
