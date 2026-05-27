# Job Hunt Partner

An AI-powered job hunting system built for full-time job seekers on a deadline. It continuously scrapes the web for fresh job openings, tracks your application pipeline, and coaches you through the process via Discord.

## Goal

Land a job within 2 months by staying organized, never missing a fresh opening, and having an active coaching partner that checks in on your progress.

## Components

| Component | Purpose | Location |
|---|---|---|
| **Scraper** | Searches web every 10 min for new openings | `src/scraper/` |
| **API** | FastAPI backend, all data access | `src/api/` |
| **Dashboard** | Web UI — job board + application tracker | `src/dashboard/` |
| **Discord Bot** | Conversational coaching partner | `src/discord/` |
| **Database** | SQLite with JSON columns | `jobs.db` |

## Docs

- [Architecture & Data Flow](docs/architecture.md)
- [Database Schema](docs/schema.md)
- [API Specification](docs/api-spec.md)
- [Scraper Design](docs/scraper.md)
- [Discord Bot Design](docs/discord-bot.md)
- [Deployment Guide](docs/deployment.md)

## Quick Start

```bash
# 1. Clone and set up
git clone https://github.com/jimmymoonstation/job-hunt-partner
cd job-hunt-partner
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Fill in BRAVE_API_KEY and DISCORD_BOT_TOKEN

# 3. Initialize database
python scripts/init_db.py

# 4. Run locally
uvicorn src.api.main:app --reload

# 5. Deploy to server
bash scripts/deploy.sh
```

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy, APScheduler
- **Database:** SQLite (JSON columns for flexible resume storage)
- **Scraper:** httpx + BeautifulSoup + Brave Search API
- **Dashboard:** Vanilla HTML/CSS/JS (no framework, fast and simple)
- **Bot:** discord.py
- **Server:** nginx reverse proxy, systemd services
