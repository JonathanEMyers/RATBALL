import numpy as np
import sounddevice as sd
import time

class Speaker:
    def __init__(self, frequency, samplerate, blocksize, update_rate):
        self.frequency = frequency
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.update_rate = update_rate
        self.phase = 0
        self.stream = None
        self.running = False

    # This function is used to generate data for the audio stream callback
    def audio_callback(self, outdata, frames, time_info, status):
        freq = self.frequency
        t = (np.arange(frames) + self.phase) / self.samplerate
        wave = 0.5 * np.sin(2 * np.pi * freq * t)
        outdata[:] = wave.reshape(-1, 1)
        self.phase += frames

    def set_frequency(self, frequency):
        self.frequency = frequency

    def start(self):
        # Make sure the speaker knows it is running
        self.running = True

        # Make the stream object
        self.stream = sd.OutputStream(
            callback=self.audio_callback,
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            channels=1
        )

        # Start the stream
        self.stream.start()

    # Function to stop the speaker stream
    def stop(self):
        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
        print("Speaker stopped.")
