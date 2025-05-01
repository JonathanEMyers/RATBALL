import sys
import argparse
from loguru import logger

from src.config import RatballConfig
from src.governors import SensorGovernor, SpeakerGovernor, CameraGovernor
from src.ingestor import IngestorService

parser = argparse.ArgumentParser()
parser.add_argument("--ingestor", help="run the Ingestor service", action="store_true")


logger_format = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</> | "
    "<level><bold>{level: <8}</></> | "
    "<cyan>{name}</>:<cyan>{function}</>:<purple>{line}</> | "
    "<level>{message}</level>"
    "\n<red>{exception}</>"
)

def init_logger(is_multiprocess: bool = False) -> None:
    # remove default log handler
    logger.remove()

    # log to both stderr/console and a rotating+compressed log file (capped at 200 MB)
    logger.add(
        sys.stderr,
        format=logger_format,
        enqueue=is_multiprocess,
    )
    logger.add(RatballConfig().data_paths.logs, rotation="200 MB", compression="zip")


def run_ratball_client():
    init_logger(is_multiprocess=True)

    sensor_gov = SensorGovernor()
    sensor_gov.run()

    speaker_gov = SpeakerGovernor()
    speaker_gov.run()

    camera_gov = CameraGovernor()
    camera_gov.run()


def run_ingestor_service():
    init_logger()

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

