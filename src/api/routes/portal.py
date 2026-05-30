import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from src.api.database import SessionLocal
from src.api.models import Job, SearchConfig, TrackedCompany

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portal", tags=["portal"])


class SubmitBody(BaseModel):
    text: str
    context: Optional[str] = None  # "why interesting" follow-up note


class LearnBody(BaseModel):
    job_id: int
    note: str


# ── URL parsing ────────────────────────────────────────────────────────────────

def _parse_job_url(url: str) -> Optional[dict]:
    """Return job-level parse dict, or None if this is a company/board-level URL."""
    from urllib.parse import urlparse
    p = urlparse(url)
    host = p.netloc.lower()
    path = p.path

    if "greenhouse.io" in host:
        m = re.search(r"/([^/]+)/jobs/(\d+)", path)
        if m:
            return {"ats_type": "greenhouse", "company_slug": m.group(1), "job_id": m.group(2)}

    if "lever.co" in host:
        m = re.match(r"/([^/]+)/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", path)
        if m:
            return {"ats_type": "lever", "company_slug": m.group(1), "job_id": m.group(2)}

    if "ashbyhq.com" in host:
        m = re.match(r"/([^/]+)/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", path)
        if m:
            return {"ats_type": "ashby", "company_slug": m.group(1), "job_id": m.group(2)}

    if "myworkdayjobs.com" in host:
        if "/job/" in path:
            tenant = host.split(".")[0]
            wd_ver = host.split(".")[1] if len(host.split(".")) > 1 else "wd5"
            parts  = [s for s in path.split("/") if s]
            board  = parts[0] if parts else tenant
            last   = parts[-1] if parts else ""
            m      = re.search(r"_([A-Za-z0-9]+)$", last)
            job_id = m.group(1) if m else last
            return {"ats_type": "workday", "company_slug": tenant, "job_id": job_id,
                    "workday_board": board, "workday_wd_ver": wd_ver, "original_path": path}

    return None


# ── Fetch single job from ATS ─────────────────────────────────────────────────

async def _fetch_greenhouse_job(slug: str, job_id: str) -> Optional[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}")
            if r.status_code == 200:
                d = r.json()
                return {
                    "title":    d.get("title", ""),
                    "location": d.get("location", {}).get("name", ""),
                    "url":      d.get("absolute_url") or f"https://job-boards.greenhouse.io/{slug}/jobs/{job_id}",
                }
        except Exception:
            pass
    return None


async def _fetch_lever_job(slug: str, job_id: str) -> Optional[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"https://api.lever.co/v0/postings/{slug}/{job_id}")
            if r.status_code == 200:
                d    = r.json()
                cats = d.get("categories", {})
                locs = cats.get("allLocations", [])
                loc  = locs[0] if locs else cats.get("location", "")
                return {
                    "title":    d.get("text", ""),
                    "location": loc,
                    "url":      d.get("hostedUrl") or f"https://jobs.lever.co/{slug}/{job_id}",
                }
        except Exception:
            pass
    return None


async def _fetch_ashby_job(slug: str, job_id: str) -> Optional[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
            if r.status_code == 200:
                for posting in r.json().get("jobPostings", []):
                    if posting.get("id") == job_id:
                        return {
                            "title":    posting.get("title", ""),
                            "location": posting.get("location", ""),
                            "url":      posting.get("externalLink") or f"https://jobs.ashbyhq.com/{slug}/{job_id}",
                        }
        except Exception:
            pass
    return None


async def _fetch_workday_job(slug: str, job_id: str, board: str, wd_ver: str, original_path: str) -> Optional[dict]:
    # Use the original URL as the job URL; try to get title via the jobs API
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(
                f"https://{slug}.{wd_ver}.myworkdayjobs.com/wday/cxs/{slug}/{board}/jobs",
                json={"limit": 20, "offset": 0, "searchText": ""},
                timeout=8,
            )
            if r.status_code == 200:
                for posting in r.json().get("jobPostings", []):
                    if job_id in posting.get("externalPath", ""):
                        return {
                            "title":    posting.get("title", ""),
                            "location": posting.get("locationsText", ""),
                            "url":      f"https://{slug}.{wd_ver}.myworkdayjobs.com/{board}{posting['externalPath']}",
                        }
        except Exception:
            pass
    return None


# ── Why was this job missed? ──────────────────────────────────────────────────

def _why_missed(title: str, location: str, db) -> list[str]:
    from src.scraper.career_pages import _matches_criteria
    try:
        cfg = db.query(SearchConfig).filter_by(is_active=True).first()
        if not cfg:
            return []
        titles    = json.loads(cfg.titles_json    or "[]")
        locations = json.loads(cfg.locations_json or "[]")
        levels    = json.loads(cfg.levels_json    or "[]")

        if _matches_criteria(title, location, titles, locations, levels):
            return []  # would have been included — maybe just hasn't been scraped yet

        reasons = []
        if titles and not any(t.lower() in title.lower() for t in titles):
            reasons.append(f'title didn\'t match tracked keywords ({", ".join(titles[:4])}{"…" if len(titles) > 4 else ""})')
        if locations and location and not any(l.lower() in location.lower() for l in locations):
            reasons.append(f'location "{location}" didn\'t match tracked locations')
        if not reasons:
            reasons.append("filtered by level or compound criteria")
        return reasons
    except Exception as e:
        logger.debug(f"_why_missed error: {e}")
        return []


# ── Main submit endpoint ───────────────────────────────────────────────────────

@router.post("/submit")
async def portal_submit(body: SubmitBody):
    text    = body.text.strip()
    context = (body.context or "").strip()

    if not text:
        return {"type": "error", "status": "error", "message": "Empty input."}

    db = SessionLocal()
    try:
        # ── Specific job URL ───────────────────────────────────────────────
        if text.startswith(("http://", "https://")):
            parsed = _parse_job_url(text)

            if parsed:
                slug     = parsed["company_slug"]
                job_id   = parsed["job_id"]
                ats_type = parsed["ats_type"]

                # Already in DB?
                existing = db.query(Job).filter(Job.company_job_id == job_id).first()
                if existing:
                    msg = f'"{existing.job_title}" at {existing.company_name} is already in the dashboard.'
                    if context:
                        existing.user_feedback = f"portal: {context}"
                        db.commit()
                        msg += " Your note was saved."
                    return {"type": "job", "status": "exists", "message": msg,
                            "job_id": existing.id, "ask_context": not bool(context)}

                # Fetch job details from ATS API
                job_data = None
                if ats_type == "greenhouse":
                    job_data = await _fetch_greenhouse_job(slug, job_id)
                elif ats_type == "lever":
                    job_data = await _fetch_lever_job(slug, job_id)
                elif ats_type == "ashby":
                    job_data = await _fetch_ashby_job(slug, job_id)
                elif ats_type == "workday":
                    job_data = await _fetch_workday_job(
                        slug, job_id,
                        parsed.get("workday_board", "Careers"),
                        parsed.get("workday_wd_ver", "wd5"),
                        parsed.get("original_path", ""),
                    )

                if not job_data:
                    job_data = {"title": "Unknown Role", "location": "", "url": text}

                # Look up company name
                company_rec  = db.query(TrackedCompany).filter_by(ats_slug=slug).first()
                company_name = company_rec.company_name if company_rec else slug.replace("-", " ").title()

                # Why was it filtered?
                missed = _why_missed(job_data["title"], job_data["location"], db)

                # Import the job
                uid = hashlib.sha256(f"{company_name}{job_data['title']}{text}".encode()).hexdigest()[:16]
                new_job = Job(
                    company_job_id=job_id,
                    company_name=company_name,
                    job_title=job_data["title"],
                    location=job_data["location"],
                    url=job_data["url"],
                    source=f"portal:{ats_type}",
                    is_active=True,
                    discovered_at=datetime.utcnow(),
                    user_feedback=f"portal: {context}" if context else None,
                )
                db.add(new_job)
                db.commit()
                db.refresh(new_job)

                msg = f'Imported "{job_data["title"]}" at {company_name}.'
                if missed:
                    msg += f' Was filtered because: {"; ".join(missed)}.'
                if context:
                    msg += " Your note was saved — I'll use this to learn."

                return {
                    "type":         "job",
                    "status":       "imported",
                    "message":      msg,
                    "job_id":       new_job.id,
                    "job_title":    job_data["title"],
                    "company":      company_name,
                    "missed":       missed,
                    "ask_context":  not bool(context),
                }

            # Company-level URL → company ingest
            from src.api.routes.companies import IngestBody, ingest_company
            result = await ingest_company(IngestBody(text=text), db)
            return {"type": "company", **result}

        # ── Company name or type:slug ──────────────────────────────────────
        from src.api.routes.companies import IngestBody, ingest_company
        result = await ingest_company(IngestBody(text=text), db)
        return {"type": "company", **result}

    finally:
        db.close()


@router.post("/learn")
async def portal_learn(body: LearnBody):
    """Attach a learning note to a job imported via the portal."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=body.job_id).first()
        if not job:
            return {"ok": False, "message": "Job not found."}
        existing = job.user_feedback or ""
        job.user_feedback = (existing + f" | portal: {body.note}").strip(" |")
        db.commit()
        return {"ok": True}
    finally:
        db.close()
