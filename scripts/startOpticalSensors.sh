#!/usr/bin/env bash

set -e

# Most portable way to resolve script path, see: https://stackoverflow.com/a/246128
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# Sanity-check: make sure our resolved path isn't empty
if [[ -z "$SCRIPT_DIR" ]] ; then
	printf '%s\n' 'Could not resolve working directory, exiting!'
	exit 1
fi

# Compute the path to project root relative to resolved dir of this script
PROJECT_ROOT_PATH="$SCRIPT_DIR/.."

# Make sure we shut down all servers even after an interrupt
cleanup_on_exit() {
        printf '\n%s\n\n' "Received interrupt, killing all server PIDs."
	if [[ -n "$STOP_PID" ]]   ; then kill -9 "$STOP_PID"   ; fi
	if [[ -n "$SENSOR_PID" ]] ; then kill -9 "$SENSOR_PID" ; fi
	if [[ -n "$SERVER_PID" ]] ; then kill -9 "$SERVER_PID" ; fi
        printf '\n%s\n\n' "Goodbye!"
}
trap cleanup_on_exit INT


# Check for existence of venv, create one if not found
VENV_PATH="$PROJECT_ROOT_PATH/.venv"
if [[ ! -d "$VENV_PATH" ]] ; then 
	uv venv
fi

# Pull all dependencies
uv sync

SRC_DIR="$PROJECT_ROOT_PATH/src"


# Start the server in the background
printf '%s\n\n' "Starting server..."
uv run "$SRC_DIR/sensor-server.py" &
SERVER_PID="$!"
sleep 2

# Start the sensor data client in the background
printf '%s\n\n' "Starting sensor data client..."
uv run "$SRC_DIR/sensor-client.py" &
SENSOR_PID="$!"
sleep 2

# Start the stopping client (after some delay)
uv run "$SRC_DIR/terminator.py" &
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

