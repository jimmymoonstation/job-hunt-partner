# Architecture & Data Flow

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INTERNET                                    │
│   Google Jobs · LinkedIn · Greenhouse · Lever · Workday · FAANG     │
│                    company career pages                             │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  HTTP (every 10 min)
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        SCRAPER SERVICE                               │
│                                                                      │
│   BraveSearchClient ──► query("{title} {location} job -site:linkedin)│
│   CareerPageScraper ──► direct HTML parsing of company /careers pages│
│   Deduplicator      ──► company_job_id + url hash check against DB   │
│   Normalizer        ──► extract: title, company, level, location,    │
│                         posted_at, job_id, url                       │
└──────────────────────────────┬───────────────────────────────────────┘
                               │  INSERT new jobs only
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         SQLite DATABASE                              │
│                                                                      │
│   jobs ◄──────────────── applications ◄────── status_history        │
│                               │                                      │
│                          interviews                                  │
│                                                                      │
│   resumes (JSON blobs)    search_config    discord_sessions          │
└──────────┬────────────────────┬────────────────────────────────────-─┘
           │                    │
           ▼                    ▼
┌──────────────────┐   ┌────────────────────────────────────────────┐
│   FastAPI        │   │   DISCORD BOT                              │
│                  │   │                                            │
│  /jobs           │   │   #job-hunt channel                        │
│  /applications   │   │   • new job alerts (on discovery)          │
│  /interviews     │   │   • conversational partner                 │
│  /resumes        │   │   • interview prep on demand               │
│  /config         │   │   • calls Claude API for responses         │
│  /stats          │   │   • reads/writes DB via internal API       │
└────────┬─────────┘   └────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       WEB DASHBOARD                                  │
│                                                                      │
│  ┌─────────────┐  ┌──────────────────┐  ┌─────────────────────┐    │
│  │  Job Board  │  │  Pipeline Tracker│  │  Stats & Progress   │    │
│  │             │  │                  │  │                     │    │
│  │ All openings│  │  Kanban: new →   │  │  Applied: 12        │    │
│  │ matching    │  │  applied →       │  │  Interviews: 3      │    │
│  │ your config │  │  screen →        │  │  Offers: 0          │    │
│  │             │  │  interview →     │  │  Goal: 5/day        │    │
│  │ [Save] [X]  │  │  offer/rejected  │  │  Days left: 58      │    │
│  └─────────────┘  └──────────────────┘  └─────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

## Data Flow: New Job Discovery

```mermaid
sequenceDiagram
    participant S as Scheduler (10 min)
    participant B as Brave Search API
    participant C as Career Page Scrapers
    participant D as Deduplicator
    participant DB as SQLite DB
    participant Bot as Discord Bot
    participant UI as Web Dashboard

    S->>B: search("{title} {location} job opening")
    B-->>S: list of URLs + snippets
    S->>C: fetch & parse each career page URL
    C-->>S: structured job data
    S->>D: check company_job_id against DB
    D->>DB: SELECT WHERE company_job_id IN (...)
    DB-->>D: existing IDs
    D-->>S: new jobs only (deduped)
    S->>DB: INSERT new jobs (status=new)
    S->>Bot: notify: "3 new openings found"
    Bot-->>Bot: post to #job-hunt channel
    UI->>DB: GET /jobs?status=new (auto-refresh every 60s)
    DB-->>UI: latest openings
```

## Data Flow: Applying to a Job

```mermaid
sequenceDiagram
    participant U as User
    participant UI as Dashboard
    participant API as FastAPI
    participant DB as SQLite DB
    participant Bot as Discord Bot

    U->>UI: clicks "Apply" on a job
    UI->>UI: show modal: select resume version
    U->>UI: selects resume, adds notes
    UI->>API: POST /applications {job_id, resume_id, notes}
    API->>DB: INSERT application (status=applied)
    API->>DB: INSERT status_history (new→applied)
    API-->>UI: 201 Created
    UI-->>U: job moves to "Applied" column
    API->>Bot: webhook: "You applied to {title} at {company}"
    Bot-->>Bot: post to #job-hunt + start tracking
```

## Data Flow: Discord Coaching Interaction

```mermaid
sequenceDiagram
    participant U as User
    participant Discord as Discord #job-hunt
    participant Bot as discord.py Bot
    participant API as FastAPI
    participant Claude as Claude API

    U->>Discord: "how am I doing this week?"
    Discord->>Bot: on_message event
    Bot->>API: GET /stats?period=week
    API->>DB: aggregate query
    DB-->>API: {applied:5, interviews:1, new_jobs:47}
    API-->>Bot: stats payload
    Bot->>Claude: prompt with stats + conversation history
    Claude-->>Bot: coaching response
    Bot->>Discord: "This week: 5 applications, 1 interview scheduled..."
```

## Scheduler Timeline

```
:00  ─── scraper runs ──► check Brave Search + career pages
:10  ─── scraper runs
:20  ─── scraper runs
...
09:00 ── daily morning summary pushed to Discord
18:00 ── evening check-in if < N applications today
```

## Deployment Topology (DigitalOcean Droplet)

```
Internet
   │
   ▼
nginx (port 80/443)
   ├── /jobs-dashboard  ──► static files (src/dashboard/)
   └── /api             ──► FastAPI (uvicorn, port 5057)
                               ├── APScheduler (runs in-process)
                               └── SQLite (jobs.db)

systemd services:
   job-hunter-api.service    ← FastAPI + scheduler
   claude-discord-bot.service ← existing, extended with job-hunt module
```
