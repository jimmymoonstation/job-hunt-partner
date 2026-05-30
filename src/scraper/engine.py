"""
Scraper engine: orchestrates Brave Search + career page scrapers,
deduplicates results, and persists new jobs to the database.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.database import SessionLocal
from src.api.models import Job, SearchConfig
from src.scraper import brave, career_pages
from src.scraper.career_pages import scrape_linkedin_only

logger = logging.getLogger(__name__)


@dataclass
class RunStats:
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime = None
    sources_checked: int = 0
    new_jobs: int = 0
    duplicates_skipped: int = 0
    errors: int = 0

    def finish(self):
        self.finished_at = datetime.utcnow()

    @property
    def duration_seconds(self) -> float:
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return 0.0


# In-memory run history (last 50 runs)
_run_history: list[RunStats] = []
_is_running = False


def get_status() -> dict:
    last = _run_history[-1] if _run_history else None
    return {
        "last_run": last.finished_at if last else None,
        "jobs_found_last_run": last.new_jobs if last else 0,
        "total_runs": len(_run_history),
        "errors_last_run": last.errors if last else 0,
        "is_running": _is_running,
    }


async def run_scraper() -> RunStats:
    global _is_running
    if _is_running:
        logger.info("Scraper already running, skipping")
        return RunStats()

    _is_running = True
    stats = RunStats()

    try:
        config = _load_config()
        titles = json.loads(config.titles_json) if config else []
        locations = json.loads(config.locations_json) if config else []
        keywords = json.loads(config.keywords_json) if config else []
        levels = json.loads(config.levels_json) if config else []

        if not titles:
            logger.info("No search titles configured — skipping scraper run")
            stats.finish()
            return stats

        # Layer 1: Brave Search (broad web)
        brave_jobs = await brave.search_jobs(titles, locations, keywords)
        stats.sources_checked += 1

        # Layer 2: Career pages (targeted)
        career_jobs = await career_pages.scrape_all(titles, locations, levels)
        stats.sources_checked += len(career_pages.GREENHOUSE_COMPANIES) + len(career_pages.LEVER_COMPANIES)

        all_jobs = brave_jobs + career_jobs
        logger.info(f"Raw results: {len(brave_jobs)} brave + {len(career_jobs)} career pages")

        # Persist
        new_jobs_list, new_count, dup_count = _save_jobs_with_list(all_jobs)
        stats.new_jobs = new_count
        stats.duplicates_skipped = dup_count

        # Notify Discord about new finds
        if new_jobs_list:
            from src.discord.notifications import notify_new_jobs
            import asyncio
            asyncio.ensure_future(notify_new_jobs(new_jobs_list))

    except Exception as e:
        logger.error(f"Scraper run failed: {e}", exc_info=True)
        stats.errors += 1
    finally:
        stats.finish()
        _is_running = False
        _run_history.append(stats)
        if len(_run_history) > 50:
            _run_history.pop(0)

    logger.info(
        f"Scraper done in {stats.duration_seconds:.1f}s — "
        f"{stats.new_jobs} new, {stats.duplicates_skipped} dupes"
    )
    return stats


_linkedin_running = False


async def run_linkedin_scraper() -> RunStats:
    """
    LinkedIn-only scrape run for high-frequency (every 5 min) polling.
    Uses f_TPR=r300 (last 5 minutes) + geoId=90000084 (SF Bay Area) —
    matches the 5-min poll interval for minute-level freshness.
    """
    global _linkedin_running
    if _linkedin_running:
        logger.info("LinkedIn scraper already running, skipping")
        return RunStats()

    _linkedin_running = True
    stats = RunStats()

    try:
        config = _load_config()
        titles = json.loads(config.titles_json) if config else []
        locations = json.loads(config.locations_json) if config else []
        levels = json.loads(config.levels_json) if config else []

        if not titles:
            stats.finish()
            return stats

        jobs = await scrape_linkedin_only(titles, locations, levels)
        logger.info(f"LinkedIn poll: {len(jobs)} raw results")

        new_jobs_list, new_count, dup_count = _save_jobs_with_list(jobs)
        stats.new_jobs = new_count
        stats.duplicates_skipped = dup_count

        if new_jobs_list:
            from src.discord.notifications import notify_new_jobs
            import asyncio
            asyncio.ensure_future(notify_new_jobs(new_jobs_list))

    except Exception as e:
        logger.error(f"LinkedIn scraper run failed: {e}", exc_info=True)
        stats.errors += 1
    finally:
        stats.finish()
        _linkedin_running = False

    if stats.new_jobs:
        logger.info(f"LinkedIn: {stats.new_jobs} new jobs saved")

    return stats


def _load_config() -> SearchConfig | None:
    with SessionLocal() as db:
        return db.query(SearchConfig).filter_by(is_active=True).first()


def _is_already_applied(db, company_name: str, job_title: str, url: str, original_url: str | None) -> bool:
    """
    Return True if this job is effectively a duplicate of one the user already applied to.
    Checks:
      1. Exact URL match against existing job URLs and original_urls (cross-source dedup)
      2. Same (company, title) as a job that already has an application
    """
    from sqlalchemy import func, text as sa_text
    from src.api.models import Application

    # Cross-source URL dedup: new job's URL matches an existing job's original_url,
    # or new job's original_url matches an existing job's URL
    url_checks = [url]
    if original_url:
        url_checks.append(original_url)

    for u in url_checks:
        exists = db.query(Job).filter(
            (Job.url == u) | (Job.original_url == u)
        ).first()
        if exists:
            return True

    # Company+title dedup against applied jobs
    co_norm  = company_name.strip().lower()
    ttl_norm = job_title.strip().lower()
    applied_match = (
        db.query(Job)
        .join(Application, Application.job_id == Job.id)
        .filter(
            func.lower(func.trim(Job.company_name)) == co_norm,
            func.lower(func.trim(Job.job_title))    == ttl_norm,
        )
        .first()
    )
    return applied_match is not None


def _save_jobs(raw_jobs: list[dict]) -> tuple[int, int]:
    _, new_count, dup_count = _save_jobs_with_list(raw_jobs)
    return new_count, dup_count


def _save_jobs_with_list(raw_jobs: list[dict]) -> tuple[list[dict], int, int]:
    new_count = 0
    dup_count = 0
    saved: list[dict] = []

    with SessionLocal() as db:
        for data in raw_jobs:
            # Skip jobs that duplicate something the user already applied to
            if _is_already_applied(
                db,
                data["company_name"],
                data["job_title"],
                data["url"],
                data.get("original_url"),
            ):
                dup_count += 1
                continue

            try:
                job = Job(
                    company_job_id=data["company_job_id"],
                    company_name=data["company_name"],
                    job_title=data["job_title"],
                    location=data.get("location"),
                    level=data.get("level"),
                    url=data["url"],
                    original_url=data.get("original_url"),
                    source=data["source"],
                    description=data.get("description"),
                    posted_at=data.get("posted_at"),
                )
                # Use a nested savepoint so a constraint violation on one row
                # doesn't invalidate the entire session / previously-added rows.
                with db.begin_nested():
                    db.add(job)
                new_count += 1
                saved.append(data)
            except IntegrityError:
                dup_count += 1
            except Exception as e:
                logger.warning(f"Failed to save job: {e}")

        if new_count > 0:
            db.commit()

    return saved, new_count, dup_count
