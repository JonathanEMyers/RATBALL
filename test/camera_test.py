from datetime import datetime
from os import makedirs
from src.camera import Camera


def gstreamer_dual_tiled_pipeline(
        sensor_id: int,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        font_size: int = 28,
) -> str:
    """
    Jetson CSI-2 dual-camera preview (sensor-id 0 & 1) tiled side-by-side
    in a single window with timestamp overlays.
    """
    return (
        # --- compositor first so we can attach the two branches later ---
        f'nvcompositor name=comp sink_0::xpos=0 sink_0::ypos=0 '
        f'sink_1::xpos={width} sink_1::ypos=0 ! '
        f'nvvidconv ! videoconvert ! autovideosink sync=false '
        # --- branch 0 ---------------------------------------------------
        f'nvarguscamerasrc sensor-id={sensor_id} ispdigitalgainrange="1 1" ! '
        f'video/x-raw(memory:NVMM),width={width},height={height},framerate={fps}/1 ! '
        f'nvvidconv ! video/x-raw,format=BGRx ! '
        f'timeoverlay time-mode=running-time halignment=left valignment=top '
        f'font-desc=\"Monospace, {font_size}\" shaded-background=true ! '
        f'queue ! comp.sink_0 ! '
        # --- branch 1 ---------------------------------------------------
        f'nvarguscamerasrc sensor-id={sensor_id} ispdigitalgainrange="1 1" ! '
        f'video/x-raw(memory:NVMM),width={width},height={height},framerate={fps}/1 ! '
        f'nvvidconv ! video/x-raw,format=BGRx ! '
        f'timeoverlay time-mode=running-time halignment=left valignment=top '
        f'font-desc="Monospace, {font_size}" shaded-background=true ! '
        f'queue ! comp.sink_1'
    )

cam_kwargs = {"width": 1280, "height": 720, "framerate": 30}

camera_manifest = (
    Camera(0, **cam_kwargs, gstreamer_dual_tiled_pipeline(sensor_id=0)),
    Camera(1, **cam_kwargs, gstreamer_dual_tiled_pipeline(sensor_id=1)),
)


capture_active = False
try:
    for idx, cam in enumerate(camera_manifest):
        if not capture_active:
            cam.start()
    capture_active = True
except (KeyboardInterrupt, BrokenPipeError):
    print("\nShutting down gracefully…", file=sys.stderr)
finally:
    for cam in camera_manifest:
        cam.stop()

