"""
Direct scrapers for companies using common ATS platforms.
Greenhouse and Lever expose clean JSON APIs — no HTML parsing needed.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Registry of companies and their ATS platform + board slug
# Add more companies here — users can also add via dashboard in future
GREENHOUSE_COMPANIES = [
    "stripe", "notion", "figma", "airtable", "brex", "ramp",
    "scale", "cohere", "anthropic", "openai", "mistral",
    "robinhood", "plaid", "chime", "affirm", "carta",
    "databricks", "confluent", "hashicorp", "datadog",
    "asana", "dropbox", "twilio", "sendgrid",
]

LEVER_COMPANIES = [
    "netlify", "vercel", "supabase", "planetscale",
    "linear", "loom", "pitch", "descript",
    "retool", "segment", "mixpanel", "amplitude",
]


async def scrape_all(titles: list[str], locations: list[str]) -> list[dict]:
    results = []
    async with httpx.AsyncClient(timeout=15) as client:
        for company in GREENHOUSE_COMPANIES:
            try:
                jobs = await _scrape_greenhouse(client, company, titles, locations)
                results.extend(jobs)
            except Exception as e:
                logger.debug(f"Greenhouse {company}: {e}")

        for company in LEVER_COMPANIES:
            try:
                jobs = await _scrape_lever(client, company, titles, locations)
                results.extend(jobs)
            except Exception as e:
                logger.debug(f"Lever {company}: {e}")

    logger.info(f"Career pages: found {len(results)} matching jobs")
    return results


async def _scrape_greenhouse(client: httpx.AsyncClient, company: str, titles: list[str], locations: list[str]) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"
    resp = await client.get(url)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    data = resp.json()

    results = []
    for job in data.get("jobs", []):
        if not _matches_criteria(job.get("title", ""), job.get("location", {}).get("name", ""), titles, locations):
            continue
        posted_at = None
        if updated := job.get("updated_at"):
            try:
                posted_at = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            except ValueError:
                pass
        results.append({
            "company_job_id": str(job["id"]),
            "company_name": data.get("name", company.title()),
            "job_title": job["title"],
            "location": job.get("location", {}).get("name"),
            "level": _infer_level(job["title"]),
            "url": job["absolute_url"],
            "source": f"greenhouse:{company}",
            "description": _strip_html(job.get("content", ""))[:2000],
            "posted_at": posted_at,
        })
    return results


async def _scrape_lever(client: httpx.AsyncClient, company: str, titles: list[str], locations: list[str]) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    resp = await client.get(url)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    jobs = resp.json()

    results = []
    for job in jobs:
        loc = job.get("categories", {}).get("location", "")
        if not _matches_criteria(job.get("text", ""), loc, titles, locations):
            continue
        posted_at = None
        if ts := job.get("createdAt"):
            try:
                posted_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            except (ValueError, TypeError):
                pass
        results.append({
            "company_job_id": job["id"],
            "company_name": company.title(),
            "job_title": job["text"],
            "location": loc or None,
            "level": _infer_level(job["text"]),
            "url": job["hostedUrl"],
            "source": f"lever:{company}",
            "description": _strip_html(job.get("descriptionBody", ""))[:2000],
            "posted_at": posted_at,
        })
    return results


def _matches_criteria(title: str, location: str, titles: list[str], locations: list[str]) -> bool:
    if not titles and not locations:
        return True

    title_match = not titles or any(
        t.lower() in title.lower() for t in titles
    )
    location_match = not locations or any(
        loc.lower() in location.lower() or "remote" in location.lower()
        for loc in locations
    )
    return title_match and location_match


def _strip_html(html: str) -> str:
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)


def _infer_level(title: str) -> Optional[str]:
    title_lower = title.lower()
    if any(w in title_lower for w in ["staff", "principal", "distinguished"]):
        return "Staff/Principal"
    if any(w in title_lower for w in ["senior", "sr.", "sr "]):
        return "Senior"
    if any(w in title_lower for w in ["junior", "jr.", "associate"]):
        return "Junior"
    if any(w in title_lower for w in ["lead", "tech lead"]):
        return "Lead"
    if re.search(r"\bL[3-7]\b|\bIC[3-7]\b", title):
        m = re.search(r"\bL([3-7])\b|\bIC([3-7])\b", title)
        return f"L{m.group(1) or m.group(2)}"
    return None
