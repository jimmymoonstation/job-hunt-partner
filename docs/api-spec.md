# API Specification

FastAPI backend at `http://localhost:5057`. Served externally via nginx at `/api/`.

All responses are JSON. All timestamps are ISO 8601 UTC.

---

## Jobs

### `GET /api/jobs`
List all discovered jobs, newest first.

**Query params:**
| Param | Type | Default | Description |
|---|---|---|---|
| `status` | string | `new` | Filter: `new`, `saved`, `applied`, `all` |
| `since` | datetime | — | Only jobs discovered after this time |
| `q` | string | — | Search title/company |
| `location` | string | — | Filter by location |
| `level` | string | — | Filter by level |
| `limit` | int | 50 | Max results |
| `offset` | int | 0 | Pagination |

**Response:**
```json
{
  "total": 142,
  "jobs": [
    {
      "id": 1,
      "company_job_id": "12345",
      "company_name": "Stripe",
      "job_title": "Senior Software Engineer",
      "location": "San Francisco, CA",
      "level": "Senior",
      "url": "https://stripe.com/jobs/12345",
      "source": "greenhouse",
      "posted_at": "2024-01-15T08:00:00Z",
      "discovered_at": "2024-01-15T14:22:00Z",
      "is_active": true,
      "application": null
    }
  ]
}
```

### `GET /api/jobs/{id}`
Single job with full description.

### `PATCH /api/jobs/{id}`
Update `is_active` or add to saved list.

---

## Applications

### `GET /api/applications`
All applications with current status.

**Query params:** `status`, `limit`, `offset`

**Response:**
```json
{
  "total": 12,
  "applications": [
    {
      "id": 1,
      "job": { "id": 1, "company_name": "Stripe", "job_title": "Senior SWE", "url": "..." },
      "status": "interview",
      "applied_at": "2024-01-10T10:00:00Z",
      "updated_at": "2024-01-14T09:00:00Z",
      "resume": { "id": 2, "name": "SWE Backend v3" },
      "notes": "Recruiter reached out via LinkedIn",
      "interviews": [
        { "id": 1, "round": "phone_screen", "scheduled_at": "2024-01-16T15:00:00Z", "outcome": "passed" }
      ]
    }
  ]
}
```

### `POST /api/applications`
Apply to a job.

**Body:**
```json
{
  "job_id": 1,
  "resume_id": 2,
  "notes": "Applied via company website",
  "status": "applied"
}
```

### `PATCH /api/applications/{id}`
Update status, notes, or resume.

**Body:**
```json
{
  "status": "phone_screen",
  "notes": "Recruiter called, scheduled screen for Jan 16"
}
```
Status changes are automatically written to `status_history`.

### `GET /api/applications/{id}/history`
Full status change log for an application.

---

## Interviews

### `POST /api/applications/{id}/interviews`
Add an interview round.

**Body:**
```json
{
  "round": "technical",
  "scheduled_at": "2024-01-20T14:00:00Z",
  "notes": "2-hour coding interview"
}
```

### `PATCH /api/interviews/{id}`
Update outcome, notes, or prep notes.

---

## Resumes

### `GET /api/resumes`
List all resume versions.

### `POST /api/resumes`
Create a new resume version.

**Body:**
```json
{
  "name": "SWE Backend v3",
  "version": "3.0",
  "tags": ["backend", "python", "senior"],
  "content_json": { ... },
  "file_path": null
}
```

### `GET /api/resumes/{id}`
Full resume including `content_json`.

### `PUT /api/resumes/{id}`
Replace a resume version.

---

## Search Config

### `GET /api/config`
Get active search configuration.

**Response:**
```json
{
  "id": 1,
  "titles": ["Software Engineer", "Backend Engineer"],
  "locations": ["San Francisco", "Remote"],
  "levels": ["Senior", "Staff"],
  "keywords": ["distributed systems", "Python"],
  "excluded_companies": [],
  "is_active": true,
  "updated_at": "2024-01-10T08:00:00Z"
}
```

### `PUT /api/config`
Replace active config. Triggers an immediate scraper run.

---

## Stats

### `GET /api/stats`
Aggregated progress metrics.

**Response:**
```json
{
  "period": "all_time",
  "jobs_discovered": 847,
  "jobs_saved": 23,
  "applications": {
    "total": 12,
    "by_status": {
      "applied": 7,
      "phone_screen": 2,
      "interview": 2,
      "offer": 0,
      "rejected": 1
    }
  },
  "interviews_scheduled": 3,
  "days_since_start": 14,
  "days_remaining": 46,
  "daily_average_applications": 0.86,
  "target_daily_applications": 3
}
```

**Query params:** `period` — `today`, `week`, `all_time`

---

## Scraper

### `POST /api/scraper/run`
Trigger an immediate scraper run (for testing or on-demand refresh).

### `GET /api/scraper/status`
Last run time, job counts, any errors.

---

## Discord Webhook (internal)

### `POST /api/discord/notify`
Used internally by the scraper and status tracker to push notifications to the Discord bot.

**Body:**
```json
{
  "type": "new_jobs",
  "payload": { "count": 5, "jobs": [...] }
}
```

**Notification types:** `new_jobs`, `status_change`, `interview_reminder`, `daily_summary`
