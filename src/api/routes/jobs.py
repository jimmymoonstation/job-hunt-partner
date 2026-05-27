import hashlib
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.models import Job
from src.api.schemas import JobListOut, JobOut


class JobCreate(BaseModel):
    job_title: str
    company_name: str
    url: str
    location: Optional[str] = None
    level: Optional[str] = None
    description: Optional[str] = None
    posted_at: Optional[datetime] = None

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


@router.post("", response_model=JobOut, status_code=201)
def create_job(body: JobCreate, db: Session = Depends(get_db)):
    job_id = hashlib.sha256(f"{body.company_name}{body.job_title}{body.url}".encode()).hexdigest()[:16]
    existing = db.query(Job).filter_by(company_job_id=job_id, source="manual").first()
    if existing:
        raise HTTPException(status_code=409, detail="Job already exists")
    job = Job(
        company_job_id=job_id,
        company_name=body.company_name,
        job_title=body.job_title,
        location=body.location,
        level=body.level,
        url=body.url,
        source="manual",
        description=body.description,
        posted_at=body.posted_at,
        discovered_at=datetime.utcnow(),
        is_active=True,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
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
