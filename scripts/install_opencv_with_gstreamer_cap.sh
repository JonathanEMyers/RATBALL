#!/usr/bin/env bash
# Script for compiling and building OpenCV with GStreamer capability
# NOTE: Only Debian/Ubuntu Linux supported

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
if [[ -z "$SCRIPT_DIR" ]] ; then
    printf '%s\n' 'Could not resolve working directory, exiting!'
    exit 1
fi

version="4.10.0"
opencv_gst_workdir=$(mktemp -d 2>/dev/null || mktemp -d -t 'opencv_gst_workdir')
opencv_profile_path=$SCRIPT_DIR/opencv_paths.profile



set -e

for (( ; ; ))
do
    echo "Do you want to remove the default OpenCV (yes/no)?"
    echo "('Y' will run apt purge to remove all *libopencv* packages)" 
    read rm_old

    if [ "$rm_old" = "yes" ]; then
        echo "** Remove other OpenCV first"
        sudo apt -y purge *libopencv*
	break
    elif [ "$rm_old" = "no" ]; then
	break
    fi
done


echo "------------------------------------"
echo "⇒ Install dependencies (step 1/4)"
echo "------------------------------------"
sudo apt-get update
sudo apt-get install -y build-essential cmake git libgtk2.0-dev pkg-config libavcodec-dev libavformat-dev libswscale-dev
sudo apt-get install -y libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev python3.10-dev python3-numpy
sudo apt-get install -y libtbb2 libtbb-dev libjpeg-dev libpng-dev libtiff-dev libv4l-dev v4l-utils qv4l2
sudo apt-get install -y curl


echo "------------------------------------"
echo "⇒ Download OpenCV "${version}" (step 2/4)"
echo "------------------------------------"
mkdir -p $opencv_gst_workdir
pushd ${opencv_gst_workdir}
curl -L https://github.com/opencv/opencv/archive/${version}.zip -o opencv-${version}.zip
curl -L https://github.com/opencv/opencv_contrib/archive/${version}.zip -o opencv_contrib-${version}.zip
unzip opencv-${version}.zip
unzip opencv_contrib-${version}.zip
rm opencv-${version}.zip opencv_contrib-${version}.zip
pushd opencv-${version}/


echo "------------------------------------"
echo "⇒ Build OpenCV "${version}" (step 3/4)"
echo "------------------------------------"
mkdir release
pushd release/
cmake -D WITH_CUDA=ON \
      -D WITH_CUDNN=ON \
      -D CUDA_ARCH_BIN="8.7" \
      -D CUDA_ARCH_PTX="" \
      -D OPENCV_GENERATE_PKGCONFIG=ON \
      -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib-${version}/modules \
      -D WITH_GSTREAMER=ON \
      -D WITH_LIBV4L=ON \
      -D BUILD_opencv_python3=ON \
      -D BUILD_TESTS=OFF \
      -D BUILD_PERF_TESTS=OFF \
      -D BUILD_EXAMPLES=OFF \
      -D CMAKE_BUILD_TYPE=RELEASE \
      -D CMAKE_INSTALL_PREFIX=/usr/local ..
make -j$(nproc)
sudo make install

popd
popd
popd

echo "------------------------------------"
echo "** Install OpenCV "${version}" (4/4)"
echo "------------------------------------"
touch $opencv_profile_path
echo 'export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH' >> $opencv_profile_path
echo 'export PYTHONPATH=/usr/local/lib/python3.10/site-packages/:$PYTHONPATH' >> $opencv_profile_path


echo "OpenCV "${version}" with GStreamer support installed successfully."
echo "NOTE: paths exported in '${opencv_profile_path}' must be added to the shell environment before use."
echo "      To add to the current shell, run:"
echo "          source ${opencv_profile_path}"
echo "      To permanently add to the environment, redirect to your shell rc file, e.g.:"
echo "          cat ${opencv_profile_path} > $HOME/.bashrc"

