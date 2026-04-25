import schedule
import time
import subprocess
from loguru import logger
from datetime import datetime


def run_pipeline():
    """Run the direct pipeline — no proxy needed."""
    logger.info(
        f"Starting pipeline at "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    try:
        result = subprocess.run(
            ["python", "scrapers/run_pipeline.py"],
            capture_output=False,
            cwd="/home/jeenamolabraham/Desktop/pricehawk"
        )
        if result.returncode == 0:
            logger.info("Pipeline completed successfully!")
        else:
            logger.error("Pipeline failed!")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")


if __name__ == "__main__":
    logger.info("PriceHawk scheduler started!")
    logger.info("Pipeline runs every 24 hours")

    # Run immediately on start
    run_pipeline()

    # Schedule every 24 hours
    schedule.every(24).hours.do(run_pipeline)

    while True:
        schedule.run_pending()
        time.sleep(60)