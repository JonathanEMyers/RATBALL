import sys
import argparse
from loguru import logger

from src.config import RatballConfig
from src.governors import SensorGovernor, SpeakerGovernor, CameraGovernor
from src.ingestor import IngestorService

parser = argparse.ArgumentParser()
parser.add_argument("--ingestor", help="run the Ingestor service", action="store_true")

def init_logger():
    # remove default log handler
    logger.remove()

    # log to both stderr/console and a rotating+compressed log file (capped at 200 MB)
    logger.add(
        sys.stderr,
        format="{time} | <level><bold>{level}</></> | <cyan>{thread}</> | <red>{exception}</> | {message}",
    )
    logger.add(RatballConfig().data_paths.logs, rotation="200 MB", compression="zip")


def run_ratball_client():
    init_logger()

    sensor_gov = SensorGovernor()
    sensor_gov.run()

    speaker_gov = SpeakerGovernor()
    speaker_gov.run()

    camera_gov = CameraGovernor()
    camera_gov.run()


def run_ingestor_service():
    ingestor_srv = IngestorService()
    ingestor_srv.start()

def main():
    args = parser.parse_args()
    if args.ingestor:
        logger.info("Starting Ingestor service")
        run_ingestor_service()
    else:
        logger.info("Starting RATBALL client")
        run_ratball_client()

if __name__ == "__main__":
    main()

