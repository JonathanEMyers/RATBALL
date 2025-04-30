from src.speaker import Speaker
import time

speaker = Speaker(300, 44100, 8192, 30)
speaker.start()

frequency = 0
while(frequency < 10000):
    speaker.set_frequency(frequency)
    frequency += 500
    time.sleep(1)

speaker.stop()