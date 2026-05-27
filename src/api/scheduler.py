import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


def start_scheduler():
    from src.scraper.engine import run_scraper
    from src.discord.notifications import send_morning_summary, send_evening_checkin

    # Career page scrapers every 10 minutes
    scheduler.add_job(
        run_scraper,
        trigger=IntervalTrigger(minutes=10),
        id="scraper_10min",
        replace_existing=True,
        max_instances=1,
    )

    # Morning summary at 9:00 AM daily
    scheduler.add_job(
        send_morning_summary,
        trigger=CronTrigger(hour=9, minute=0),
        id="morning_summary",
        replace_existing=True,
    )

    # Evening check-in at 6:00 PM daily
    scheduler.add_job(
        send_evening_checkin,
        trigger=CronTrigger(hour=18, minute=0),
        id="evening_checkin",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    scheduler.shutdown(wait=False)
