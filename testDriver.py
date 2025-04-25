# Insert import functions
import alsaaudio as aa
import sounddevice as sd
import struct, threading, socket, time, collections, yaml
import numpy as np
from yaml import SafeLoader
from datetime import datetime, timezone
import cv2
import sys  # For getting size of datatypes
import Microphone
import blankSensor
from testClass import testClass

framerate = 30
frameCount = 0
objectOne = testClass(0, 1280, 720, 30, framerate)
stop_event = threading.Event()







                    # Thread-associated functions

def gatherSensorData():
    global beginExperiment
    global beginTermination
    global whichBuffer
    frameInterval = 1/framerate
    expStartTime = time.perf_counter()
    nextFrameTime = expStartTime
    
    while not stop_event.is_set():

        # Take time with perf_counter()
        startTime = time.perf_counter()
        # print(f"Frame: {frameCount}, Ideal: {nextFrameTime}, Actual: {startTime}, ExpTime: {nextFrameTime - expStartTime}")
        # print(f"Buffer List Size: {len(objectOne.data_buffer_list)}, Buffer Zero Size: {len(objectOne.data_buffer_list[0])}")

        objectOne.append_data()

        # Take time with perf_counter()
        endTime = time.perf_counter()

        # Wait the difference between elapsed time and 1/framerate seconds
        nextFrameTime += frameInterval

        # time.sleep(max(0, timeToWait))

        # Time.sleep is not very accurate, so using a busy loop with perf_counter()
        while(time.perf_counter() < nextFrameTime):
            pass





def sendSensorData():
    while not stop_event.is_set():
        print(f"Buffer List Size: {len(objectOne.data_buffer_list)}, Buffer Zero Size: {len(objectOne.data_buffer_list[0])}")
        objectOne.get_data()

        time.sleep(.01)




# Start threads only if we have a connection
recordingThread = threading.Thread(target=gatherSensorData, daemon=True)
recordingThread.start()

sendingThread = threading.Thread(target=sendSensorData, daemon=True)
sendingThread.start()

try:
    while True:
        time.sleep(0.5)  # Main thread idle/watching
except KeyboardInterrupt:
    print("\nKeyboardInterrupt caught! Stopping threads...")
    stop_event.set()  # Signal threads to stop

# The join function waits to close the main thread until the thread that the join
# function is being called on finishes. I was encountering issues with the main thread
# doing this and it was throwing errors.
recordingThread.join()
sendingThread.join()

