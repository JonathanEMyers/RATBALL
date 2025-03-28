#!/bin/bash

# Set the path to your virtual environment
VENV_PATH="/home/jemyers/RBProjects/experimentation/25_03_21_AudioStreaming/audio"
source "$VENV_PATH/bin/activate"
pip install -r './requirements.txt'

# Start the server in the background
printf '%s\n\n' "Starting server..."
python3 ./ingestorCode.py &
SERVER_PID="$!"
sleep 2  # Wait for server to initialize

# Start the sensor data client in the background
printf '%s\n\n' "Starting sensor data client..."
python3 ./jetsonCode.py &
SENSOR_PID="$!"
sleep 2  # Wait for client to connect

# Start the stopping client (after some delay)
printf '%s\n\n' "Triggering client shutdown..."
python3 BMICode.py &
STOP_PID="$!"

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