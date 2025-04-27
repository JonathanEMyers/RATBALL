# camera.py
from __future__ import annotations

import cv2

# print(cv2.getBuildInformation())
import threading
import time
from datetime import datetime, timezone
from typing import Iterable, Tuple, Optional

from buffers import DoubleBuffer


# slams out crappy frames as fast as possible
def gstreamer_dyn_pipeline(sensor_id: int, width: int, height: int, fps: int) -> str:
    """Jetson CSI → GRAY8 pipeline string optimized for low-latency network transfer."""
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        # f"nvarguscamerasrc sensor-id={sensor_id} num-buffers=150 ! "
        f"video/x-raw(memory:NVMM), width={width}, height={height}, "
        f"format=NV12, framerate={fps}/1 ! "
        # f"nvvidconv flip-method=0 ! "
        f"nvvidconv flip-method=2 ! "
        # f"video/x-raw, width={width}, height={height}, format=BGRx ! "
        f"videoconvert ! video/x-raw, format=GRAY8 ! appsink"
    )


# saves mp4 to a predetermined (absolute) path
def gstreamer_static_pipeline(
    sensor_id: int, width: int, height: int, fps: int, outpath: str
) -> str:
    """Jetson CSI → h264 pipeline string optimized for high quality output file for out-of-band transfer."""
    return (
        f"nvarguscamerasrc sensor-id{sensor_id} ! "
        f"video/x-raw(memory:NVMM),width={width},height={height},framerate={fps}/1 ! "
        # convert out of NVMM so the overlay element can work
        f"nvvidconv ! video/x-raw,format=BGRx ! "
        # overlay buffer-time in h:mm:ss.mmm format
        f"timeoverlay time-mode=running-time halignment=left valignment=top "
        'font-desc="Monospace, 28" shaded-background=true ! '
        # duplicate the annotated stream: one branch goes to file, the other to OpenCV
        f"tee name=t "
        f"t. ! queue ! videoconvert ! "
        f"x264enc speed-preset=ultrafast tune=zerolatency bitrate=8000 ! "
        f"mp4mux ! filesink location={outpath} sync=false "
        f"t. ! queue ! videoconvert ! appsink emit-signals=true drop=true"
    )


FrameRecord = Tuple[bytes, bytes]


class Camera:
    """
    Single-producer / single-consumer camera wrapper using a DoubleBuffer.

    Producer: internal thread created by `start()`
    Consumer: call `.drain()` from any other thread / async task
    """

    __slots__ = (
        "sensor_id",
        "width",
        "height",
        "fps",
        "output_dir",
        "_capture_is_static",
        "_buffer",
        "_cap",
        "_stop_event",
        "_thread",
    )

    def __init__(
        self,
        sensor_id: int,
        width: int,
        height: int,
        *,
        framerate: int = 30,
        buffer_seconds: int = 10,
        output_dir: Optional[str] = None,
    ) -> None:
        self.sensor_id = sensor_id
        self.width = width
        self.height = height
        self.fps = framerate
        self.output_dir = output_dir

        self._capture_is_static = True if output_dir is not None else False

        # capacity = frames per second × seconds per ring
        capacity = framerate * buffer_seconds
        self._buffer: DoubleBuffer[FrameRecord] = DoubleBuffer(capacity)

        # if `output_dir` is provided, write frames at that location and tee to cv2
        self._cap = (
            cv2.VideoCapture(
                gstreamer_dyn_pipeline(sensor_id, width, height, framerate),
                cv2.CAP_GSTREAMER,
            )
            if output_dir is None
            else cv2.VideoCapture(
                gstreamer_static_pipeline(
                    sensor_id, width, height, framerate, output_dir
                ),
                cv2.CAP_GSTREAMER,
            )
        )

        if not self._cap.isOpened():
            raise RuntimeError(f"Camera {sensor_id} failed to open")

        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._capture_loop, name=f"Cam{sensor_id}", daemon=True
        )

    # ------------------------------------------------------------------ API

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2.0)
        self._cap.release()

    def drain(self) -> Iterable[FrameRecord]:
        """Yield all queued (frame, timestamp) pairs in FIFO order."""
        yield from self._buffer.drain()

    def pop(self) -> FrameRecord:
        """Remove and return (frame, timestamp) pair from buffer in FIFO order."""
        if self._buffer.ready():
            return self._buffer.pop()
        else:
            pass

    # ----------------------------------------------------------- internals

    def _capture_loop(self) -> None:
        if self._capture_is_static:
            pass
        else:
            """Producer thread"""
            frame_interval = 1.0 / self.fps
            next_frame_time = time.monotonic()

            while not self._stop_event.is_set():
                # Busy-wait until the next frame deadline
                sleep_time = next_frame_time - time.monotonic()
                if sleep_time > 0:
                    time.sleep(sleep_time)

                ret, frame = self._cap.read()
                # Correct img orientation
                # frame = cv2.flip(frame, 0)

                next_frame_time += frame_interval

                if not ret:
                    # Simple error handling: skip this frame
                    print(f"skipped frame @ ival:{frame_interval}")
                    continue

                # Generate metadata
                ts = datetime.now(timezone.utc)
                # ms_since_epoch = unix_time_millis(ts)
                ns_since_epoch = time.perf_counter_ns()
                # ts_packed = struct.pack("d", ms_since_epoch)

                cv2.putText(
                    frame,
                    ts.strftime("%H:%M:%S.%f")[:-3],
                    (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (255, 255, 255),
                    2,
                )

                try:
                    self._buffer.put(
                        (frame.tobytes(), ns_since_epoch), drop_if_full=False
                    )
                except BufferError:
                    # Both rings full and drop_if_full=False → we block
                    # OR propagate – choose policy appropriate for experiment
                    pass
