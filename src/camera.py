# camera.py
from __future__ import annotations

import cv2

# print(cv2.getBuildInformation())
import threading
import time
from datetime import datetime, timezone
from os import makedirs
from typing import Iterable, Tuple, Optional

from buffers import DoubleBuffer


# slams out crappy frames as fast as possible
def gstreamer_dyn_pipeline(sensor_id: int, width: int, height: int, fps: int) -> str:
    """Jetson CSI → GRAY8 pipeline string (semi-)optimized for low-latency network transfer."""
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), width={width}, height={height}, "
        f"format=NV12, framerate={fps}/1 ! "
        f"nvvidconv flip-method=2 ! "
        f"videoconvert ! video/x-raw, format=GRAY8 ! appsink"
    )


# saves mp4 to a predetermined (absolute) path
def gstreamer_static_pipeline_mp4(
    sensor_id: int, width: int, height: int, fps: int, outpath: str, bitrate: int = 2000
) -> str:
    """Jetson CSI → h264 MP4 pipeline string optimized for high quality output file."""
    return (
        f'nvarguscamerasrc sensor-id={sensor_id} ispdigitalgainrange="1 1" ! '
        f"video/x-raw(memory:NVMM), width={width}, height={height}, framerate={fps}/1 ! "
        # convert out of NVMM so the overlay element can work
        f"nvvidconv ! video/x-raw, format=BGRx ! "
        # overlay buffer-time in h:mm:ss.mmm format
        f"timeoverlay time-mode=running-time halignment=left valignment=top "
        f'font-desc="Monospace, 28" shaded-background=true ! '
        # split the streams (don't cross them)
        f"tee name=t "
        # first branch goes to appsink (opencv)
        f"t. ! queue ! videoconvert ! video/x-raw, format=BGR !"
        f"appsink emit-signals=true "
        #        f"drop=true max-buffers=30 "
        # second branch streams to filesink (output mp4)
        f"t. ! queue ! nvvidconv ! video/x-raw, format=I420 ! "
        f"x264enc tune=zerolatency speed-preset=ultrafast bitrate={bitrate} ! mp4mux !"
        f'filesink location="{outpath}.mp4" sync=false '
    )


# saves mkv to a predetermined (absolute) path
def gstreamer_static_pipeline_mkv(
    sensor_id: int, width: int, height: int, fps: int, outpath: str, bitrate: int = 2000
) -> str:
    """Jetson CSI → h264 Matroska pipeline string optimized for high quality output file."""
    return (
        f'nvarguscamerasrc sensor-id={sensor_id} ispdigitalgainrange="1 1" ! '
        f"video/x-raw(memory:NVMM), width={width}, height={height}, framerate={fps}/1 ! "
        # convert out of NVMM so the overlay element can work
        f"nvvidconv flip-method=2 ! video/x-raw, format=BGRx ! "
        # overlay buffer-time in h:mm:ss.mmm format
        f"timeoverlay time-mode=running-time halignment=left valignment=top "
        f'font-desc="Monospace, 28" shaded-background=true ! '
        # split the streams (don't cross them!!)
        f"tee name=t "
        # first branch goes to appsink (opencv)
        f"t. ! queue ! videoconvert ! video/x-raw, format=BGR !"
        f"appsink emit-signals=true "
        #        f"drop=true max-buffers=30 "
        # second branch streams to filesink (output mp4)
        f"t. ! queue ! nvvidconv ! video/x-raw, format=I420 ! "
        # no on-board hardware encoders, use x264 and output to Matroska container
        f"x264enc tune=zerolatency speed-preset=ultrafast bitrate={bitrate} ! "
        f'splitmuxsink location="{outpath}.mkv" muxer=matroskamux '
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
        "capture_id",
        "width",
        "height",
        "fps",
        "output_dir",
        "frame_ival_multiplier",
        "_outpath",
        "_capture_is_static",
        "_buffer",
        "_cap",
        "_stop_event",
        "_thread",
    )

    def __init__(
        self,
        sensor_id: int,
        capture_id: str,
        width: int,
        height: int,
        framerate: int = 30,
        buffer_seconds: int = 10,
        output_dir: Optional[str] = None,
        frame_ival_multiplier = 2,
    ) -> None:
        self.sensor_id = sensor_id
        self.capture_id = capture_id
        self.width = width
        self.height = height
        self.fps = framerate
        self.output_dir = output_dir
        self.frame_ival_multiplier = frame_ival_multiplier

        self._outpath = (
            f"{output_dir}/{capture_id}_cam{sensor_id}" if output_dir is not None else None
        )

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
            if self._outpath is None
            else cv2.VideoCapture(
                gstreamer_static_pipeline_mkv(
                    sensor_id, width, height, framerate, self._outpath
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


    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2.0)
        self._cap.release()

    # ------------------------------------------------------------------ API (chunked video transfer strategy)

        # TODO: send fixed-interval mkv or mp4 video chunks

    # ------------------------------------------------------------------ API (per-frame transfer strategy)

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
            ret, frame = self._cap.read()
            if not ret:
                print("[static pipeline] no frame available yet, continuing")
            try:
                ns_since_epoch = time.perf_counter_ns()
                self._buffer.put((frame.tobytes(), ns_since_epoch), drop_if_full=False)
            except BufferError:
                pass
        else:
            """Producer thread"""
            frame_interval = 2.0 / self.fps
            next_frame_time = time.monotonic()

            while not self._stop_event.is_set():
                # Busy-wait until the next frame deadline
                sleep_time = next_frame_time - time.monotonic()
                if sleep_time > 0:
                    time.sleep(sleep_time)

                ret, frame = self._cap.read()
                if not ret:
                    # Simple error handling: skip this frame
                    print(f"skipped frame @ ival:{frame_interval}")
                    continue

                next_frame_time += frame_interval
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

