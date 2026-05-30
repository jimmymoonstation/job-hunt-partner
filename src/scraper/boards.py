"""
Additional job board scrapers using DDG site-scoped search.
Wellfound and YC Work at a Startup both block server-side scraping,
so we use DuckDuckGo `site:` queries to discover their job listings.
"""
import hashlib
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


def _job_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:20]


def _ddg(query: str, max_results: int = 20) -> list[dict]:
    import time
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        time.sleep(1.5)
        return results
    except Exception as e:
        logger.debug(f"DDG search failed for '{query}': {e}")
        return []


# ── Wellfound (wellfound.com) ─────────────────────────────────────────────────

async def _scrape_wellfound(client, titles: list[str], locations: list[str], levels: list[str]) -> list[dict]:
    """
    Search Wellfound startup jobs via DDG site: queries.
    Wellfound blocks direct HTTP scraping (403), so we use DuckDuckGo
    to find individual job pages indexed on wellfound.com.
    """
    from src.scraper.career_pages import _matches_criteria, _infer_level
    from src.scraper.web_search import _clean_title, _title_from_url, _is_individual_job_url
    import asyncio

    results = []
    seen: set[str] = set()
    loc_kw = '"San Francisco" OR "Bay Area" OR "Remote"'

    for title_kw in (titles or [])[:4]:
        query = f'"{title_kw}" {loc_kw} site:wellfound.com'
        raw = await asyncio.get_event_loop().run_in_executor(None, _ddg, query, 15)
        await asyncio.sleep(1)

        for r in raw:
            url  = r.get("href", "")
            snip = r.get("body", "")

            if not url or "wellfound.com" not in url:
                continue
            if not _is_individual_job_url(url):
                continue
            if url in seen:
                continue
            seen.add(url)

            title    = _title_from_url(url) or _clean_title(r.get("title", ""))
            # Try extracting company from URL: wellfound.com/company/{slug}/jobs/{id}
            m = re.search(r"wellfound\.com/(?:company/([^/?#]+)/jobs|jobs/([^/?#]+))", url)
            company  = (m.group(1) or m.group(2) or "").replace("-", " ").title() if m else ""
            location = ""
            if "remote" in snip.lower():
                location = "Remote"
            elif "san francisco" in snip.lower() or "bay area" in snip.lower():
                location = "San Francisco Bay Area"

            if not title or not _matches_criteria(title, location or snip, titles, locations, levels):
                continue

            results.append({
                "company_job_id": _job_id(url),
                "company_name":   company or "Unknown",
                "job_title":      title,
                "location":       location or None,
                "level":          _infer_level(title),
                "url":            url,
                "source":         "wellfound",
                "description":    snip[:500] or None,
                "posted_at":      None,
            })

    logger.info(f"Wellfound (DDG): {len(results)} matching jobs")
    return results


# ── Y Combinator Work at a Startup ───────────────────────────────────────────

async def _scrape_yc(client, titles: list[str], locations: list[str], levels: list[str]) -> list[dict]:
    """
    Search Y Combinator Work at a Startup jobs via DDG site: queries.
    The site uses client-side rendering without exposed SSR data,
    so we use DuckDuckGo to find indexed job pages.
    """
    from src.scraper.career_pages import _matches_criteria, _infer_level
    from src.scraper.web_search import _clean_title, _title_from_url, _is_individual_job_url
    import asyncio

    results = []
    seen: set[str] = set()
    loc_kw = '"San Francisco" OR "Bay Area" OR "Remote"'

    for title_kw in (titles or [])[:4]:
        query = f'"{title_kw}" {loc_kw} site:workatastartup.com'
        raw = await asyncio.get_event_loop().run_in_executor(None, _ddg, query, 15)
        await asyncio.sleep(1)

        for r in raw:
            url  = r.get("href", "")
            snip = r.get("body", "")

            if not url or "workatastartup.com" not in url:
                continue
            # YC job URLs look like /jobs/{id} or /companies/{slug}/jobs/{id}
            if "/jobs/" not in url:
                continue
            if url in seen:
                continue
            seen.add(url)

            title    = _title_from_url(url) or _clean_title(r.get("title", ""))
            m = re.search(r"workatastartup\.com/companies/([^/?#]+)", url)
            company  = m.group(1).replace("-", " ").title() if m else ""
            location = ""
            if "remote" in snip.lower():
                location = "Remote"
            elif "san francisco" in snip.lower() or "bay area" in snip.lower():
                location = "San Francisco Bay Area"

            if not title or not _matches_criteria(title, location or snip, titles, locations, levels):
                continue

            results.append({
                "company_job_id": _job_id(url),
                "company_name":   company or "Unknown",
                "job_title":      title,
                "location":       location or None,
                "level":          _infer_level(title),
                "url":            url,
                "source":         "yc",
                "description":    snip[:500] or None,
                "posted_at":      None,
            })

    logger.info(f"YC Work at a Startup (DDG): {len(results)} matching jobs")
    return results
