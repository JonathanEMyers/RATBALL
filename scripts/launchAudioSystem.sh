#!/bin/bash

# Had issues with initializing ALSAaudio, so waiting for it to start here:
echo "Waiting for ALSA to initialize..."
for i in {1..120}; do
    if arecord -l | grep -q "^card "; then
        echo "ALSA initialized successfully."
        break
    fi
    echo "ALSA not ready, retrying..."
    sleep 2
done

if ! arecord -l | grep -q "^card "; then
    echo "ALSA not ready after retries, exiting."
    exit 1
fi
sleep 2
echo "Starting audio system..."

# Set the path to your virtual environment
VENV_PATH="/home/jemyers/RBProjects/experimentation/25_04_19_FINALCODE/env"
FILES_PATH="/home/jemyers/RBProjects/experimentation/25_04_19_FINALCODE"
source "$VENV_PATH/bin/activate"
pip install -r '/home/jemyers/RBProjects/experimentation/25_04_19_FINALCODE/requirements.txt'

# Start the server in the background
printf '%s\n\n' "Starting server..."
python3 /home/jemyers/RBProjects/experimentation/25_04_19_FINALCODE/ingestorCode.py &
SERVER_PID="$!"
sleep 2  # Wait for server to initialize

# Start the stopping client (after some delay)
printf '%s\n\n' "Triggering stopping client..."
python3 /home/jemyers/RBProjects/experimentation/25_04_19_FINALCODE/BMICode.py &
STOP_PID="$!"
sleep 2

# Start the sensor data client in the background (after some delay)
printf '%s\n\n' "Starting sensor data client..."
python3 /home/jemyers/RBProjects/experimentation/25_04_19_FINALCODE/jetsonCode.py &
SENSOR_PID="$!"


# Wait for stop client to finish
wait $STOP_PID

sleep 5

# Stop the sensor client gracefully
printf '%s\n\n' "Stopping sensor client..."
if ps -p "$SENSOR_PID" > /dev/null
then
    kill $SENSOR_PID
else
    printf '%s\n\n' 'Audio client already stopped!'
fi

# Stop the server
printf '%s\n\n' "Stopping server..."
if ps -p "$SERVER_PID" > /dev/null
then
    kill $SERVER_PID
else
    printf '%s\n\n' 'Audio server already stopped!'
fi

printf '%s\n\n' "All processes stopped."