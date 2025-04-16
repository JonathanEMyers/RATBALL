#!/bin/bash

set -e

cleanup_on_exit() {
		if [[ -n "$STOP_PID" ]] ; then kill -9 "$STOP_PID" ; fi
		if [[ -n "$SENSOR_PID" ]] ; then kill -9 "$SENSOR_PID" ; fi
		if [[ -n "$SERVER_PID" ]] ; then kill -9 "$SERVER_PID" ; fi
        printf '\n%s\n\n' "Received interrupt, killing all server PIDs. Goodbye!"
}
trap cleanup_on_exit INT

# Set the path to your virtual environment
VENV_PATH="/home/ratball/code/venv"
source "$VENV_PATH/bin/activate"
pip install -r './requirements.txt' > /dev/null 2>&1 

# Start the server in the background
printf '%s\n\n' "Starting server..."
python3 ./opticalSensorServer.py &
SERVER_PID="$!"
#sleep 2  # Wait for server to initialize

# Start the sensor data client in the background
printf '%s\n\n' "Starting sensor data client..."
python3 opticalSensorClient.py &
SENSOR_PID="$!"
sleep 2  # Wait for client to connect

# Start the stopping client (after some delay)
python3 programStopClient.py &
STOP_PID="$!"

# Wait for stop client to finish
wait $STOP_PID && printf '%s\n' 'Sensor client and server have shut down.'
sleep 5

# Stop the sensor client gracefully
printf '%s\n\n' "Stopping sensor client..."
if ps -p "$SENSOR_PID" > /dev/null
then
    kill $SENSOR_PID
else
    printf '%s\n\n' 'Optical sensor client already stopped!'
fi

# Stop the server
printf '%s\n\n' "Stopping server..."
if ps -p "$SERVER_PID" > /dev/null
then
    kill $SERVER_PID
else
    printf '%s\n\n' 'Optical sensor server already stopped!'
fi

printf '%s\n\n' "All processes stopped."

