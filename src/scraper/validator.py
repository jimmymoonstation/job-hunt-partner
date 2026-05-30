"""
Job link validator — periodically checks that active job postings are still live.

Logic per URL:
  1. HTTP status 404/410  → dead
  2. Redirect to a non-job page (homepage, search results) → dead
  3. Page text contains known "job closed" phrases → dead
  4. For standard ATS (Greenhouse, Lever, Ashby): hit the public API endpoint
     directly — more reliable than scraping HTML.

Only unapplied jobs are checked (applied jobs stay visible regardless).
Jobs are processed in small batches with jitter to avoid thundering-herd on
any single domain. The run is skipped if the main scraper is already running.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

import httpx

from src.api.database import SessionLocal
from src.api.models import Application, Job

logger = logging.getLogger(__name__)

# ── "Job no longer available" signal phrases ──────────────────────────────────
_CLOSED_PHRASES = re.compile(
    r"(no longer (accepting|available|active|taking)|"
    r"position (has been |is )(filled|closed|removed)|"
    r"job (has been |is )?(closed|removed|expired|no longer available)|"
    r"this (role|position|opening|requisition) (has been |is )?(filled|closed|removed)|"
    r"we.re no longer|we are no longer|"
    r"no longer exist|page (not|no longer) found|"
    r"job not found|posting not found|"
    r"this job listing (has|is)|"
    r"expired job|job expired|"
    r"404|this page (could not|cannot) be found)",
    re.IGNORECASE,
)

# Paths that indicate a redirect to a search/home page rather than a job
_SEARCH_REDIRECT_RE = re.compile(
    r"(^/$|/jobs/?$|/careers/?$|/search|/job-search|/job-listings)",
    re.IGNORECASE,
)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


# ── Per-ATS fast checks ───────────────────────────────────────────────────────

async def _check_greenhouse(client: httpx.AsyncClient, url: str) -> bool:
    """Return True if the job is still live on Greenhouse."""
    # Greenhouse URLs: boards.greenhouse.io/{slug}/jobs/{id}  or
    #                  job-boards.greenhouse.io/{slug}/jobs/{id}
    m = re.search(r"greenhouse\.io/([^/?#]+)/jobs/(\d+)", url)
    if not m:
        return True  # can't parse — assume alive
    slug, job_id = m.group(1), m.group(2)
    try:
        r = await client.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}",
            timeout=10,
        )
        return r.status_code == 200
    except Exception:
        return True  # network error → assume alive, check next time


async def _check_lever(client: httpx.AsyncClient, url: str) -> bool:
    """Return True if the Lever posting is still live."""
    m = re.search(r"jobs\.lever\.co/([^/?#]+)/([0-9a-f-]{36})", url)
    if not m:
        return True
    slug, posting_id = m.group(1), m.group(2)
    try:
        r = await client.get(
            f"https://api.lever.co/v0/postings/{slug}/{posting_id}",
            timeout=10,
        )
        return r.status_code == 200
    except Exception:
        return True


async def _check_ashby(client: httpx.AsyncClient, url: str) -> bool:
    """Return True if the Ashby posting is still live."""
    m = re.search(r"jobs\.ashbyhq\.com/([^/?#]+)/([0-9a-f-]{36})", url)
    if not m:
        return True
    slug, job_id = m.group(1), m.group(2)
    try:
        r = await client.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}?jobPostingId={job_id}",
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            # Ashby returns the job or an error dict
            return bool(data.get("jobPosting") or data.get("id"))
        return False
    except Exception:
        return True


async def _check_generic(client: httpx.AsyncClient, url: str) -> bool:
    """
    Generic HTTP check: fetch the URL and look for dead-job signals.
    Returns True = alive, False = dead.
    """
    try:
        r = await client.get(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
            timeout=15,
            follow_redirects=True,
        )
    except Exception:
        return True  # network error — assume alive

    if r.status_code in (404, 410):
        return False

    # Detect redirect to a search/home page
    final_path = urlparse(str(r.url)).path.rstrip("/")
    if _SEARCH_REDIRECT_RE.search(final_path):
        return False

    # Scan page text for closed-job phrases (first 8 KB is enough)
    text_sample = r.text[:8192]
    if _CLOSED_PHRASES.search(text_sample):
        return False

    return True


async def _is_job_alive(client: httpx.AsyncClient, job: Job) -> bool:
    """Route to the most precise checker available for this job's source."""
    # Prefer the company's own URL (original_url) over the aggregator URL
    check_url = job.original_url or job.url

    if "greenhouse.io" in check_url:
        return await _check_greenhouse(client, check_url)
    if "lever.co" in check_url:
        return await _check_lever(client, check_url)
    if "ashbyhq.com" in check_url:
        return await _check_ashby(client, check_url)

    # For LinkedIn, Workday, Amazon, custom sites — generic HTTP check
    return await _check_generic(client, check_url)


# ── Main entry point ──────────────────────────────────────────────────────────

_is_validating = False


async def run_validation(batch_size: int = 50, max_age_days: int = 30) -> dict:
    """
    Check active, unapplied job postings and mark dead ones inactive.

    Prioritises older postings (most likely to have expired).
    Only processes up to `batch_size` jobs per run to stay lightweight.
    Skips jobs posted within the last 24 h (almost certainly still live).
    """
    global _is_validating
    if _is_validating:
        logger.info("Validator already running, skipping")
        return {"checked": 0, "deactivated": 0}

    _is_validating = True
    checked = 0
    deactivated = 0

    try:
        with SessionLocal() as db:
            applied_ids = {r[0] for r in db.query(Application.job_id).all()}
            cutoff_new  = datetime.utcnow() - timedelta(hours=24)
            cutoff_old  = datetime.utcnow() - timedelta(days=max_age_days)

            jobs = (
                db.query(Job)
                .filter(
                    Job.is_active == True,
                    Job.id.notin_(applied_ids),
                    Job.discovered_at < cutoff_new,    # skip brand-new postings
                    Job.discovered_at > cutoff_old,    # skip very stale (already pruned)
                )
                .order_by(Job.discovered_at.asc())     # oldest first
                .limit(batch_size)
                .all()
            )

        if not jobs:
            logger.info("Validator: no jobs to check")
            return {"checked": 0, "deactivated": 0}

        logger.info(f"Validator: checking {len(jobs)} jobs")

        # Semaphore limits concurrent outbound connections
        sem = asyncio.Semaphore(8)

        async def check_one(job: Job):
            nonlocal checked, deactivated
            async with sem:
                alive = await _is_job_alive(client, job)
                checked += 1
                if not alive:
                    with SessionLocal() as db2:
                        j = db2.query(Job).get(job.id)
                        if j:
                            j.is_active = False
                            db2.commit()
                    deactivated += 1
                    logger.info(f"Validator: deactivated [{job.id}] {job.company_name} — {job.job_title}")
                # Small per-request jitter to avoid bursting a single domain
                await asyncio.sleep(0.3)

        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            await asyncio.gather(*[check_one(j) for j in jobs])

    except Exception as e:
        logger.error(f"Validator run failed: {e}", exc_info=True)
    finally:
        _is_validating = False

    logger.info(f"Validator done: {checked} checked, {deactivated} deactivated")
    return {"checked": checked, "deactivated": deactivated}
