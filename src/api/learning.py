"""
Hourly learning pass — reads user feedback, identifies patterns, deactivates
jobs that don't fit, and picks up new companies from manually-added links.
"""
import logging
import re
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)

# Feedback tag categories
_WRONG_LOCATION_TAGS = {"wrong location"}
_WRONG_COMPANY_TAGS  = {"wrong company", "not interested"}
_WRONG_LEVEL_TAGS    = {"wrong level", "too senior"}
_CLOSED_TAGS         = {"role no longer open", "role closed", "already applied"}

# Title words that indicate seniority — if user keeps rejecting "too senior" jobs
_SENIOR_TITLE_WORDS  = ["senior", "staff", "principal", "lead ", "director", "vp ", "vice president", "head of", "manager"]


def _parse_tags(feedback_str: str) -> set[str]:
    """Extract chip tags from a feedback string, lowercased."""
    if not feedback_str:
        return set()
    # Format: "Tag1, Tag2 — freetext note"
    tags_part = feedback_str.split(" — ")[0]
    return {t.strip().lower() for t in tags_part.split(",") if t.strip()}


def run_learning_pass() -> dict:
    """
    Analyze all accumulated feedback and:
    1. Deactivate active jobs matching rejected patterns (location, company, level)
    2. Ensure new manually-added companies are already picked up (done at add-time)
    Returns a summary dict.
    """
    from src.api.database import SessionLocal
    from src.api.models import Job, Application, TrackedCompany

    db = SessionLocal()
    try:
        applied_ids = {a.job_id for a in db.query(Application).all()}

        # ── Gather all feedback ──────────────────────────────────────────────
        feedback_jobs = db.query(Job).filter(Job.user_feedback.isnot(None)).all()

        rejected_locations: defaultdict[str, int] = defaultdict(int)  # location → count
        rejected_companies: defaultdict[str, int] = defaultdict(int)  # company_name.lower() → count
        senior_rejections = 0

        for j in feedback_jobs:
            tags = _parse_tags(j.user_feedback)
            if tags & _WRONG_LOCATION_TAGS and j.location:
                rejected_locations[j.location] += 1
            if tags & _WRONG_COMPANY_TAGS:
                rejected_companies[(j.company_name or "").lower()] += 1
            if tags & _WRONG_LEVEL_TAGS:
                senior_rejections += 1

        # ── Rules ────────────────────────────────────────────────────────────
        # Location: if a specific location string was rejected 2+ times, block it
        blocked_locs = {loc for loc, cnt in rejected_locations.items() if cnt >= 2}
        # Company: if rejected 2+ times, block that company entirely
        blocked_cos  = {co for co, cnt in rejected_companies.items() if cnt >= 2}
        # Level: if 3+ senior rejections, filter out senior titles
        filter_senior = senior_rejections >= 3

        logger.info(
            f"Learning: blocked_locs={len(blocked_locs)}, "
            f"blocked_cos={len(blocked_cos)}, filter_senior={filter_senior}"
        )

        # ── Apply to active jobs ─────────────────────────────────────────────
        deactivated = []
        active_jobs = db.query(Job).filter(Job.is_active == True).all()

        for j in active_jobs:
            if j.id in applied_ids:
                continue

            reason = None

            # Rejected company
            if (j.company_name or "").lower() in blocked_cos:
                reason = f"company rejected ≥2× ({j.company_name})"

            # Rejected location
            elif j.location and j.location in blocked_locs:
                reason = f"location rejected ≥2× ({j.location})"

            # Senior title filter
            elif filter_senior:
                title_lower = (j.job_title or "").lower()
                if any(w in title_lower for w in _SENIOR_TITLE_WORDS):
                    reason = f"senior title filtered (pattern: {j.job_title[:40]})"

            if reason:
                j.is_active = False
                deactivated.append({"id": j.id, "company": j.company_name,
                                     "title": j.job_title, "reason": reason})

        # ── Disable TrackedCompany for hard-blocked companies ─────────────────
        disabled_tracked = []
        if blocked_cos:
            tracked = db.query(TrackedCompany).filter(TrackedCompany.is_active == True).all()
            for tc in tracked:
                if (tc.company_name or "").lower() in blocked_cos:
                    tc.is_active = False
                    disabled_tracked.append(tc.company_name)

        db.commit()

        summary = {
            "ran_at": datetime.utcnow().isoformat(),
            "feedback_jobs_analyzed": len(feedback_jobs),
            "blocked_locations": sorted(blocked_locs),
            "blocked_companies": sorted(blocked_cos),
            "filter_senior_titles": filter_senior,
            "jobs_deactivated": len(deactivated),
            "tracked_companies_disabled": disabled_tracked,
            "deactivated_detail": deactivated,
        }
        logger.info(
            f"Learning pass complete: {len(deactivated)} jobs deactivated, "
            f"{len(disabled_tracked)} tracked companies disabled"
        )
        return summary

    except Exception as e:
        logger.error(f"Learning pass failed: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        db.close()
