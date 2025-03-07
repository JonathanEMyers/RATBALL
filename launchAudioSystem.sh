#!/bin/bash

# Set the path to your virtual environment
VENV_PATH="~/RBProjects/experimentation/25_02_11_NetworkingWithPython"

# Start the server in the background
echo "In launchAudioSystem -- Starting server..."
python3 audioRecordingServer.py &
SERVER_PID=$!
sleep 2  # Wait for server to initialize

# Start the audio recording client in the background
echo "In launchAudioSystem -- Starting audio recording client..."
python3 audioRecordingClient.py &
AUDIO_PID=$!
sleep 2  # Wait for client to connect

# Start the stopping client (after some delay)
echo "In launchAudioSystem -- Starting stop client..."
python3 programStopClient.py &
STOP_PID=$!

# # Wait for stop client to finish
wait $STOP_PID

sleep 5

# # # Stop the audio client gracefully
# echo "In launchAudioSystem -- Stopping audio client..."
# kill $AUDIO_PID

# # # Stop the server
# echo "In launchAudioSystem -- Stopping server..."
# kill $SERVER_PID

echo "In launchAudioSystem -- All processes stopped."