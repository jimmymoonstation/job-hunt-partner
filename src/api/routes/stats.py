from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
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
    first_app = db.query(Application).order_by(Application.applied_at.asc()).first()
    start_date = first_app.applied_at if first_app and first_app.applied_at else now
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
