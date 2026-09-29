import logging

from apscheduler.schedulers.background import BackgroundScheduler

from backend.ingestion.pipeline import run_frequent_ingestion, run_slow_ingestion
from backend.notifier.job import run_notification_job

logger = logging.getLogger(__name__)


def scrape_and_notify() -> None:
    stats = run_frequent_ingestion()
    logger.info("Frequent ingestion complete: %s", stats)
    notified = run_notification_job()
    logger.info("Sent %d announcement notifications", notified)


def scrape_slow() -> None:
    stats = run_slow_ingestion()
    logger.info("Slow ingestion complete: %s", stats)


def start_scheduler(interval_minutes: int = 60, slow_interval_minutes: int = 10080) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(scrape_and_notify, "interval", minutes=interval_minutes, id="scrape_and_notify")
    scheduler.add_job(scrape_slow, "interval", minutes=slow_interval_minutes, id="scrape_slow")
    scheduler.start()
    return scheduler
