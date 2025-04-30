import qwiic_otos
import threading
import time
import os
from ..src.sensor import Sensor
from src.utils import unix_time_millis
from dataclasses import dataclass
from datetime import datetime, timezone

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
matplotlib.use('qtagg')

self_path = os.path.abspath(__file__)
self_dir = os.path.split(self_path)[0]
# sys.path.append(os.path.join(self_dir, '../src'))

sensor_manifest = [Sensor(0x17), Sensor(0x67)]
for sensor in sensor_manifest:
    sensor.begin()


class SensorPlotter():
    def __init__(self, sensor_data):
        self._sensor_data = sensor_data
        self.lines = [plt.plot(0,0)[0] for _ in range(4)]
        self.ani = FuncAnimation(plt.gcf(), self.run, interval = 10, repeat=True)

    def run(self, i):
        vecs = [self._sensor_data.pos, self._sensor_data.vel]
        for j, line in enumerate(self.lines):
            for x, y, _ in vecs[j]:
                line.set_data(self._sensor_data.time, x)
                line.set_data(self._sensor_data.time, y)
            line.axes.relim()
            line.axes.autoscale_view()



@dataclass(frozen=True, slots=True)
class SensorData():
    time = [float]
    pos = qwiic_otos.Pose2D
    vel = qwiic_otos.Pose2D


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
            pos, vel = self.device.getPosVelAcc()
            self._sensor_data.time.append(unix_time_millis(datetime.now()))
            self._sensor_data.pos.append(pos)
            self._sensor_data.vel.append(vel)

            self._nextCall = self._nextCall + self._period
            time.sleep(self._nextCall - time.time())



data = SensorData()
plotter = SensorPlotter(data)
poller = SensorPoll(data, 0x17)

poller.start()
plt.show()


