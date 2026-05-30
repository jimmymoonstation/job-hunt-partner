from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.models import Application, Interview, Job
from src.api.schemas import StatusCounts, StatsOut

router = APIRouter(prefix="/stats", tags=["stats"])

# The start date of the job hunt — set when first application is created
_hunt_start: datetime | None = None


@router.get("", response_model=StatsOut)
def get_stats(period: str = Query("all_time", enum=["today", "week", "all_time"]), db: Session = Depends(get_db)):
    now = datetime.utcnow()

    # Period filter for applications
    if period == "today":
        since = now.replace(hour=0, minute=0, second=0)
    elif period == "week":
        since = now - timedelta(days=7)
    else:
        since = None

    # Jobs
    jobs_discovered = db.query(func.count(Job.id)).scalar()
    jobs_active = db.query(func.count(Job.id)).filter(Job.is_active == True).scalar()

    # Applications
    app_query = db.query(Application)
    if since:
        app_query = app_query.filter(Application.applied_at >= since)
    apps = app_query.all()

    status_counts = StatusCounts()
    for app in apps:
        if hasattr(status_counts, app.status):
            setattr(status_counts, app.status, getattr(status_counts, app.status) + 1)
    total_apps = len(apps)

    # Interviews
    interviews_scheduled = db.query(func.count(Interview.id)).scalar()

    # Days
    first_app = (
        db.query(Application)
        .filter(Application.applied_at.isnot(None))
        .order_by(Application.applied_at.asc())
        .first()
    )
    start_date = first_app.applied_at if first_app else now
    days_since_start = max(1, (now - start_date).days)
    days_remaining = max(0, 60 - days_since_start)  # 2-month goal

    all_apps = db.query(Application).filter(Application.status != "saved").count()
    daily_avg = round(all_apps / days_since_start, 2)

    return StatsOut(
        period=period,
        jobs_discovered=jobs_discovered,
        jobs_active=jobs_active,
        applications=status_counts,
        applications_total=total_apps,
        interviews_scheduled=interviews_scheduled,
        days_since_start=days_since_start,
        days_remaining=days_remaining,
        daily_average_applications=daily_avg,
    )


@router.get("/analysis")
def get_analysis(db: Session = Depends(get_db)):
    """Full analytics payload for the Analysis tab."""

    # ── Daily applied count ────────────────────────────────────────────────────
    daily_rows = db.execute(text("""
        SELECT date(applied_at) as day, COUNT(*) as cnt
        FROM applications
        WHERE applied_at IS NOT NULL AND status != 'saved'
        GROUP BY day ORDER BY day
    """)).fetchall()

    # ── Daily status-change events (interviews, offers, rejections) ────────────
    interview_rows = db.execute(text("""
        SELECT date(changed_at) as day, COUNT(*) as cnt
        FROM status_history
        WHERE to_status IN ('interview','phone_screen') AND changed_at IS NOT NULL
        GROUP BY day ORDER BY day
    """)).fetchall()

    offer_rows = db.execute(text("""
        SELECT date(changed_at) as day, COUNT(*) as cnt
        FROM status_history
        WHERE to_status = 'offer' AND changed_at IS NOT NULL
        GROUP BY day ORDER BY day
    """)).fetchall()

    rejection_rows = db.execute(text("""
        SELECT date(changed_at) as day, COUNT(*) as cnt
        FROM status_history
        WHERE to_status IN ('rejected','withdrawn') AND changed_at IS NOT NULL
        GROUP BY day ORDER BY day
    """)).fetchall()

    def to_dict(rows): return {r[0]: r[1] for r in rows}
    daily_applied    = to_dict(daily_rows)
    daily_interviews = to_dict(interview_rows)
    daily_offers     = to_dict(offer_rows)
    daily_rejections = to_dict(rejection_rows)

    # Build full date range
    all_dates = sorted(set(
        list(daily_applied) + list(daily_interviews) +
        list(daily_offers)  + list(daily_rejections)
    ))

    # 7-day rolling average helper
    def rolling_avg(series: list[float], window: int = 7) -> list[float]:
        result = []
        for i, v in enumerate(series):
            chunk = series[max(0, i - window + 1): i + 1]
            result.append(round(sum(chunk) / len(chunk), 2))
        return result

    applied_series    = [daily_applied.get(d, 0)    for d in all_dates]
    interview_series  = [daily_interviews.get(d, 0) for d in all_dates]
    offer_series      = [daily_offers.get(d, 0)     for d in all_dates]
    rejection_series  = [daily_rejections.get(d, 0) for d in all_dates]
    rolling_7d        = rolling_avg(applied_series)

    # Cumulative applied
    cumulative = []
    running = 0
    for v in applied_series:
        running += v
        cumulative.append(running)

    # ── Status funnel ─────────────────────────────────────────────────────────
    status_rows = db.execute(text("""
        SELECT status, COUNT(*) as cnt FROM applications
        WHERE status != 'saved'
        GROUP BY status
    """)).fetchall()
    status_map = {r[0]: r[1] for r in status_rows}
    total_applied = sum(status_map.values())

    funnel_stages = ["applied", "phone_screen", "interview", "offer"]
    funnel = []
    for stage in funnel_stages:
        cnt = status_map.get(stage, 0)
        funnel.append({
            "stage": stage,
            "count": cnt,
            "pct":   round(cnt / total_applied * 100, 1) if total_applied else 0,
        })

    # ── Source breakdown ──────────────────────────────────────────────────────
    source_rows = db.execute(text("""
        SELECT COALESCE(j.source, 'unknown') as src, COUNT(*) as cnt
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        WHERE a.status != 'saved'
        GROUP BY src ORDER BY cnt DESC
    """)).fetchall()
    # Clean up source labels: "linkedin" → "LinkedIn", "greenhouse:stripe" → "Greenhouse"
    def clean_source(s):
        if not s: return "Unknown"
        base = s.split(":")[0].lower()
        labels = {
            "linkedin": "LinkedIn", "greenhouse": "Greenhouse", "lever": "Lever",
            "ashby": "Ashby", "workday": "Workday", "indeed": "Indeed",
            "manual": "Manual", "web_search": "Web Search",
            "smartrecruiters": "SmartRecruiters", "amazon": "Amazon",
            "portal": "Portal",
        }
        return labels.get(base, base.title())
    # Aggregate after cleaning (multiple raw sources may map to the same label)
    source_agg: dict[str, int] = {}
    for r in source_rows:
        label = clean_source(r[0])
        source_agg[label] = source_agg.get(label, 0) + r[1]
    by_source = [{"source": k, "count": v}
                 for k, v in sorted(source_agg.items(), key=lambda x: -x[1])]

    # ── Top companies ─────────────────────────────────────────────────────────
    company_rows = db.execute(text("""
        SELECT j.company_name, a.status, COUNT(*) as cnt
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        WHERE a.status != 'saved'
        GROUP BY j.company_name, a.status
        ORDER BY j.company_name
    """)).fetchall()

    company_map = {}
    for company, status, cnt in company_rows:
        if company not in company_map:
            company_map[company] = {"company": company, "total": 0,
                                    "interview": 0, "offer": 0, "rejected": 0}
        company_map[company]["total"]    += cnt
        if status in ("interview", "phone_screen"):
            company_map[company]["interview"] += cnt
        elif status == "offer":
            company_map[company]["offer"]     += cnt
        elif status in ("rejected", "withdrawn"):
            company_map[company]["rejected"]  += cnt

    top_companies = sorted(company_map.values(), key=lambda x: -x["total"])[:15]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    responded = sum(v for k, v in status_map.items() if k != "applied")
    response_rate  = round(responded / total_applied * 100, 1) if total_applied else 0
    interview_rate = round(
        (status_map.get("interview", 0) + status_map.get("phone_screen", 0))
        / total_applied * 100, 1
    ) if total_applied else 0

    now = datetime.utcnow()
    first_row = db.execute(text(
        "SELECT MIN(applied_at) FROM applications WHERE status != 'saved'"
    )).scalar()
    start_date = datetime.fromisoformat(first_row) if first_row else now
    days_active = max(1, (now - start_date).days + 1)

    return {
        "dates":           all_dates,
        "applied_series":  applied_series,
        "interview_series": interview_series,
        "offer_series":    offer_series,
        "rejection_series": rejection_series,
        "rolling_7d":      rolling_7d,
        "cumulative":      cumulative,
        "funnel":          funnel,
        "by_source":       by_source,
        "top_companies":   top_companies,
        "kpi": {
            "total_applied":   total_applied,
            "response_rate":   response_rate,
            "interview_rate":  interview_rate,
            "days_active":     days_active,
            "avg_per_day":     round(total_applied / days_active, 1),
            "rejections":      status_map.get("rejected", 0) + status_map.get("withdrawn", 0),
            "interviews":      status_map.get("interview", 0) + status_map.get("phone_screen", 0),
            "offers":          status_map.get("offer", 0),
        },
    }
