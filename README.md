# RATBALL Telemetry Client

## Background
This repo consists of a Python client for collecting, annotating, transmitting, and terminating odometric and visual data streams originating from the RATBALL ([TODO: expand]) omni-directional treadmill platform for use in neurological imaging studies of head-fixed laboratory mice.

The RATBALL sensor array consists of two I2C optical odometry and tracking sensors (Sparkfun, PixArt [TODO: detail]) and two CSI/MIPI near-IR/visible light cameras (Seeed Studio [TODO: detail]).

## System Requirements
- NVidia Jetson (Orin series) with M.2 NVMe SSD 
- Jetson Linux R36 (JetPack >=6.0)
- [`uv` Python package/project manager](https://github.com/astral-sh/uv)
- OpenCV `4.10.0` compiled with GStreamer capability 
  - [Installation script available](https://github.com/RATBALL-Org/RATBALL/blob/main/scripts/install_opencv_with_gstreamer_cap.sh) [TODO: attribute derivative source]


## Installation
(0.) If OpenCV is already installed on your system, make sure that it was compiled with GStreamer support:
```python
import cv2
print(cv2.getBuildInformation())
```
If your build supports GStreamer, running the above script should output build information containing indicating GStreamer capability (under the "Video I/O" header), i.e.:
```
    GStreamer:                   YES (1.26.0)
```
If this instead reports "NO", you will need to run the provided installer script to compile and build a compatible OpenCV version by navigating your shell to the root directory of the repo and running the following command:
```sh
./scripts/install_opencv_with_gstreamer_cap.sh
```

The script will prompt a Y/N response on whether you would like to remove any existing opencv distribution packages; this is strongly recommended.

Finally, source the following file in the active shell to set the correct values for the `$LD_LIBRARY_PATH` and `$PYTHONPATH` environment variables, i.e.:
```sh
source ./scripts/opencv_paths.profile
```
To persist changes to these environment variables beyond the current shell session, the profile file may be appended to your shell RC file, i.e.:
```sh
# For single-user BASH:
cat ./scripts/opencv_paths.profile >> $HOME/.profile

# For single-user ZSH:
cat ./scripts/opencv_paths.profile >> $HOME/.zprofile

# System-wide (not recommended):
cat ./scripts/opencv_paths.profile >> /etc/profile

```

1. Run the client entrypoint (`uv run` automatically initializes a project-local virtual environment and installs dependencies):
```sh
uv run main.py
```

2. Run the server entrypoint:
[TODO]


## Client Architecture
[TODO: 1-line summary]

### Architectural Diagram
[TODO: diagram, desc.]

### Data capture
[TODO: desc.]

### Event loop
[TODO: desc.]

### Networking
[TODO: desc.]

### Ingestor and Brain-Machine-Interface Servers
[TODO: desc.]


## License
[TODO]

## Acknowledgments
[TODO]

