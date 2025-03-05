#!/bin/bash

# Set the path to your virtual environment
VENV_PATH="~/RBProjects/experimentation/25_02_11_NetworkingWithPython"

# Activate the virtual environment
source "$VENV_PATH/bin/activate"

# Start the server in the background
echo "Starting server..."
python3 audioRecordingServer.py &
SERVER_PID=$!
sleep 2  # Wait for server to initialize

# Start the audio recording client in the background
echo "Starting audio recording client..."
python3 audioRecordingClient.py &
AUDIO_PID=$!
sleep 2  # Wait for client to connect

# Start the stopping client (after some delay)
echo "Starting stop client..."
python3 programStopClient.py &
STOP_PID=$!

# Wait for stop client to finish
wait $STOP_PID

# Stop the audio client gracefully
echo "Stopping audio client..."
kill $AUDIO_PID

# Stop the server
echo "Stopping server..."
kill $SERVER_PID

echo "All processes stopped."

# Deactivate the virtual environment
deactivate