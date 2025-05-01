import sys
import cv2
from datetime import datetime
from os import makedirs

def gstreamer_dyn_pipeline(sensor_id: int, width: int = 1280, height: int = 720, fps: int = 30, font_size: int = 28) -> str:
    """Jetson CSI → GRAY8 pipeline string (semi-)optimized for low-latency network transfer."""
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), width={width}, height={height}, "
        f"format=NV12, framerate={fps}/1 ! "
        f"nvvidconv flip-method=2 ! "
        f"videoconvert ! video/x-raw, format=GRAY8 ! appsink sync=false"
    )

camera_manifest = (
    cv2.VideoCapture(gstreamer_dyn_pipeline(sensor_id=0), cv2.CAP_GSTREAMER),
    cv2.VideoCapture(gstreamer_dyn_pipeline(sensor_id=1), cv2.CAP_GSTREAMER),
)

cv2.namedWindow("cam0", cv2.WINDOW_AUTOSIZE)
cv2.namedWindow("cam1", cv2.WINDOW_AUTOSIZE)

try:
    frames = 0
    while frames < 10000:
        for idx, cam in enumerate(camera_manifest):
            ret, img = cam.read()
            frames += 1
            cv2.imshow(f"cam{idx}", img)
            if cv2.waitKey(1) == ord('q'):
                break
except (KeyboardInterrupt, BrokenPipeError):
    print("\nShutting down gracefully…", file=sys.stderr)
#finally:
    #for cam in camera_manifest:
        #cap.stop()

