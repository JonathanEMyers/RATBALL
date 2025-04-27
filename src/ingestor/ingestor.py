from threading import Thread, Event
from ..config import RatballConfig


# RATBALL Ingestor Server
# Responsible for consuming and handling socket transfers from RATBALL client:
#  - Odometry sensor data -> redirects to CSV files
#  - Camera image data    -> outputs still frames and/or chunked video to storage
#
# Also listens for termination signal from BMI server, upon which:
#  - Socket connections are closed and other transient system resources are freed
#  - Data file post-processing is performed (i.e. chunked video collation, frame decomposition, CSV data statistics, etc.)


class IngestorWorker(Thread):
    def __init__(self, *args, **kwargs):
        super(IngestorWorker, self).__init__(*args, **kwargs)
        self._cfg = RatballConfig()

        self._sock_jetson = None
        self._sock_bmi = None

        self._rx_complete = Event()
        self._term_flag = Event()


    def _init_sockets(self):

        pass

    def _consume_camera_feed(self):
        pass

    def _consume_sensor_feed(self):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def run(self):
        pass


