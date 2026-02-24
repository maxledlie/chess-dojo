import time
import structlog

logger = structlog.get_logger()


def main():
    try:
        while True:
            time.sleep(3)
            logger.info("Matchmaker heartbeat")

    except Exception as e:
        logger.error("Unhandled exception", exc_info=e)
