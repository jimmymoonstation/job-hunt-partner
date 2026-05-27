# Scraper Design

The scraper is the heartbeat of the system. It runs every 10 minutes and feeds new job openings into the database without duplicates.

## Strategy: Two-Layer Discovery

```
Layer 1: Broad Discovery (Brave Search API)
    → Search queries built from user's search_config
    → Catches jobs posted anywhere on the web
    → Fast, no per-site maintenance

Layer 2: Targeted Career Page Scrapers
    → Direct HTML parsing of major company /careers pages
    → More reliable for top-priority companies
    → Extracts structured data (job ID, exact post date)
```

## Layer 1: Brave Search API

**Endpoint:** `https://api.search.brave.com/res/web/v1/search`  
**Free tier:** 2,000 requests/month  
**Queries per run:** 1 query per (title × location) combination, max 5  
**At 10-min interval:** 6 queries/hour × 24h = 144/day = ~4,320/month (over free tier)

**Optimization:** Only run Brave Search every 30 minutes (not 10). Run targeted scrapers every 10 minutes. This brings usage to ~1,440/month — within free tier.

### Query Template
```
"{job_title}" "{location}" (job OR opening OR hiring) 
-site:linkedin.com -site:indeed.com
after:2024-01-01
```

### Response Parsing
Brave returns web results. We:
1. Filter URLs that look like job postings (contain `/jobs/`, `/careers/`, `/position/`, etc.)
2. Fetch each URL with httpx
3. Parse with BeautifulSoup looking for JSON-LD structured data (`application/ld+json` with `@type: JobPosting`)
4. Fall back to heuristic HTML parsing if no structured data

### JSON-LD JobPosting (ideal case)
Most modern job boards emit this. Example:
```json
{
  "@type": "JobPosting",
  "title": "Senior Software Engineer",
  "hiringOrganization": { "name": "Acme Corp" },
  "jobLocation": { "address": { "addressLocality": "San Francisco" } },
  "datePosted": "2024-01-15",
  "identifier": { "value": "job-12345" },
  "url": "https://careers.acme.com/jobs/12345"
}
```

## Layer 2: Targeted Company Scrapers

Built-in scrapers for companies that use common ATS platforms:

| Platform | Companies Using It | Scrape Method |
|---|---|---|
| Greenhouse | Stripe, Notion, Figma, 100s more | `boards.greenhouse.io/{company}/jobs.json` — clean JSON API, no scraping needed |
| Lever | many startups | `jobs.lever.co/{company}` — JSON API available |
| Workday | Google, Meta (some), large enterprises | HTML scraping, paginated |
| Direct (custom) | Apple, Amazon, Microsoft | Custom per-company parser |

### Greenhouse (Example — easiest)
```
GET https://boards.greenhouse.io/acme/jobs
→ Returns full JSON with all open positions
→ Each job has: id, title, location, updated_at, absolute_url
→ Zero HTML parsing needed
```

### Company Career Page Registry
Stored in `src/scraper/targets.py` — a list of known company career page URLs and their platform type. Users can add more via the dashboard.

## Deduplication Logic

```python
# Dedup key = (company_job_id, source)
# company_job_id is extracted from:
#   1. JSON-LD identifier.value
#   2. URL path (regex extracts numeric/alphanumeric ID)
#   3. SHA256 hash of (company_name + job_title + url) as fallback

def extract_job_id(url: str, structured_data: dict) -> str:
    if structured_data.get("identifier", {}).get("value"):
        return str(structured_data["identifier"]["value"])
    # try URL: /jobs/12345 or /positions/swe-senior-12345
    match = re.search(r'/(?:jobs|positions|careers|openings)/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    # fallback: content hash
    return hashlib.sha256(f"{company}{title}{url}".encode()).hexdigest()[:16]
```

## Scheduler

Uses **APScheduler** running inside the FastAPI process (no separate worker needed).

```
Every 10 min:  run targeted career page scrapers
Every 30 min:  run Brave Search queries
Every 60 min:  mark inactive jobs (check if posting URLs still return 200)
Daily 09:00:   send morning summary to Discord
Daily 18:00:   send evening check-in to Discord (if < 3 applications today)
```

## Rate Limiting & Politeness

- Min 2s delay between requests to the same domain
- Rotate User-Agent headers
- Respect `robots.txt` for direct scrapers
- Brave API: stay within 2000/month by batching queries

## Error Handling

- Network errors: log and skip, retry next cycle
- Parsing errors: log raw HTML for debugging, skip job
- DB constraint errors: silently ignore (dedup working correctly)
- Brave API quota exceeded: fall back to targeted scrapers only, alert via Discord

## Scraper Run Log

Each scraper run writes a summary to `scraper_runs` (in-memory, not persisted):
```
Run #1042 | 2024-01-15 14:30:00
  Sources checked: 12
  New jobs found: 7
  Duplicates skipped: 43
  Errors: 0
  Duration: 8.2s
```
