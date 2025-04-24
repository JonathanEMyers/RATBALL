import collections
import time
import alsaaudio as aa
from datetime import datetime, timezone
import struct


class Microphone:
    def __init__(self, bufSize, rate, channels, format_str, framerate, maxRetries=10):
        format_map = {
            "S16_LE": aa.PCM_FORMAT_S16_LE,
            "U8": aa.PCM_FORMAT_U8,
            "S32_LE": aa.PCM_FORMAT_S32_LE,
            # add more as needed
        }

        if format_str not in format_map:
            raise ValueError(f"Unsupported audio format string: {format_str}")

        self.format = format_map[format_str]
        self.bufferSize = bufSize
        self.chunkSize = int(rate / framerate)

        self.metaBufferOne = collections.deque(maxlen=bufSize)
        self.metaBufferTwo = collections.deque(maxlen=bufSize)

        self.dataBufferOne = collections.deque(maxlen=bufSize)
        self.dataBufferTwo = collections.deque(maxlen=bufSize)

        for attempt in range(maxRetries):
            try:
                self.micInput = aa.PCM(
                    type=aa.PCM_CAPTURE,
                    mode=aa.PCM_NORMAL,
                    channels=channels,
                    rate=rate,
                    format=self.format,
                    periodsize=self.chunkSize,
                )
                break
            except aa.ALSAAudioError as e:
                print(f"[Attempt {attempt + 1}] ALSA not ready: {e}")
                time.sleep(1)
        else:
            raise RuntimeError("Failed to initialize ALSA PCM after multiple attempts.")

        # Just for debugging purposes
        self.frameCount = 0

    def append_mic_data(self, whichBuffer):
        length, data = self.micInput.read()
        timestamp = self.unix_time_millis(datetime.now())
        timestampPacked = struct.pack("d", timestamp)

        if not length:
            return False

        if whichBuffer and len(self.dataBufferOne) < self.bufferSize:
            self.dataBufferOne.append(data)
            self.metaBufferOne.append(timestampPacked)
            self.frameCount += 1
            return True
        elif not whichBuffer and len(self.dataBufferTwo) < self.bufferSize:
            self.dataBufferTwo.append(data)
            self.metaBufferTwo.append(timestampPacked)
            self.frameCount += 1
            return True
        else:
            return False

    def pop_mic_data(self, whichBuffer):
        if not whichBuffer and self.dataBufferOne:
            return (self.metaBufferOne.popleft(), self.dataBufferOne.popleft())
        elif whichBuffer and self.dataBufferTwo:
            return (self.metaBufferTwo.popleft(), self.dataBufferTwo.popleft())
        else:
            return (None, None)

    @staticmethod
    def unix_time_millis(dt):
        """formats timestamps as milliseconds-since-epoch (double-precision float, only requires 8 bytes)"""
        unix_epoch = datetime.fromtimestamp(0, timezone.utc)

        if dt.tzinfo is None:
            # make dt offset-aware in UTC if it's naive
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            # convert to UTC if it's aware in a different timezone
            dt = dt.astimezone(timezone.utc)
        return (dt - unix_epoch).total_seconds() * 1000.0
