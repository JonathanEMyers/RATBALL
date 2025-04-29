# RATBALL Telemetry Client

## Background
This repo consists of a Python client for collecting, annotating, transmitting, and terminating odometric, visual, and audial data streams originating from the RATBALL (Research and Training Behavioral Analysis Locomation Lab) omni-directional treadmill platform for use in neurological imaging studies of head-fixed laboratory mice.

The RATBALL sensor array consists of two I2C optical tracking odometry sensors (Sparkfun, PixArt PAA5160E1), two CSI/MIPI near-IR/visible light cameras (Seeed Studio IMX219-160 8MP), and support for a speaker for audio playback.

## System Requirements
- NVidia Jetson (Orin series) with M.2 NVMe SSD 
- Jetson Linux R36 (JetPack >=6.0)
- [`uv` Python package/project manager](https://github.com/astral-sh/uv)
- OpenCV `4.10.0` compiled with GStreamer capability 
  - [Installation script available](https://github.com/RATBALL-Org/RATBALL/blob/main/scripts/install_opencv_with_gstreamer_cap.sh) [TODO: credit original source]


## Installation
#### OpenCV
If OpenCV is already installed on your system, make sure that it was compiled with GStreamer support:
```python
import cv2
print(cv2.getBuildInformation())
```  
Running the above script should print out all compilation options enabled for your build. Under the "Video I/O" header, you should see a line indicating whether or not GStreamer capability is enabled:
```
GStreamer:                   YES (1.26.0)
```
If the ouput is "YES", you're good to go!


<details>
<summary>*What to do if your OpenCV build lacks GStreamer support* (click to expand)</summary>

1. Run the provided installer script to compile and build a compatible OpenCV version by navigating your shell to the root directory of the repo and running the following command:
    ```sh
    ./scripts/install_opencv_with_gstreamer_cap.sh
    ```
    The script will prompt a Y/N response on whether you would like to remove any existing opencv distribution packages (strongly recommended).

2. Source the following file in your active shell to update values for the `$LD_LIBRARY_PATH` and `$PYTHONPATH` environment variables, i.e.:
    ```sh
    source ./scripts/opencv_paths.profile
    ```

	_Optional:_  
    To persist environment variable updates after the current shell session ends, append the profile file to your shell's `.*rc` file.
    ```sh
    # For single-user BASH:
    cat ./scripts/opencv_paths.profile >> $HOME/.profile

    # For single-user ZSH:
    cat ./scripts/opencv_paths.profile >> $HOME/.zprofile

    # System-wide (not recommended):
    cat ./scripts/opencv_paths.profile >> /etc/profile
    ```

3. Permit `uv` to use the system `site-packages` installation of OpenCV by running the following command from the repo root directory:
    ```sh
    sed -i 's/include-system-site-packages = false/include-system-site-packages = true/' .venv/pyvenv.cfg
    ```

At this point, the output of `cv2.getBuildInformation()` should report that GStreamer support is enabled!

</details>

---
#### Project

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

