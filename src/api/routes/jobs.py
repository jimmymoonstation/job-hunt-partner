from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.models import Job
from src.api.schemas import JobListOut, JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListOut)
def list_jobs(
    status: Optional[str] = Query(None, description="new|saved|applied|all"),
    since: Optional[datetime] = None,
    q: Optional[str] = None,
    location: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    from src.api.models import Application

    query = db.query(Job).filter(Job.is_active == True)

    if since:
        query = query.filter(Job.discovered_at >= since)
    if q:
        query = query.filter(
            Job.job_title.ilike(f"%{q}%") | Job.company_name.ilike(f"%{q}%")
        )
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    if level:
        query = query.filter(Job.level.ilike(f"%{level}%"))

    # Filter by application status
    if status == "new":
        applied_job_ids = db.query(Application.job_id)
        query = query.filter(Job.id.notin_(applied_job_ids))
    elif status == "applied":
        applied_job_ids = db.query(Application.job_id)
        query = query.filter(Job.id.in_(applied_job_ids))

    total = query.count()
    jobs = query.order_by(Job.discovered_at.desc()).offset(offset).limit(limit).all()

    return JobListOut(total=total, jobs=jobs)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/{job_id}")
def update_job(job_id: int, is_active: Optional[bool] = None, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if is_active is not None:
        job.is_active = is_active
    db.commit()
    return {"ok": True}
