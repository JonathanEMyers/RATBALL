import sys
from loguru import logger

from src.config import RatballConfig
from src.governors import SensorGovernor, SpeakerGovernor, CameraGovernor


def init_logger():
    # remove default log handler
    logger.remove()

    # log to both stderr/console and a rotating+compressed log file (capped at 200 MB)
    logger.add(
        sys.stderr,
        format="{time} | <level><bold>{level}</></> | <cyan>{thread}</> | <red>{exception}</> | {message}",
    )
    logger.add(RatballConfig().data_paths.logs, rotation="200 MB", compression="zip")


def main():
    init_logger()

    sensor_gov = SensorGovernor()
    sensor_gov.run()

    speaker_gov = SpeakerGovernor()
    speaker_gov.run()

    camera_gov = CameraGovernor()
    camera_gov.run()


if __name__ == "__main__":
    main()

