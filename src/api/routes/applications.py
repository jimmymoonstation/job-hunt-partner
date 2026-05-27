from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.models import Application, Interview, Job, Resume, StatusHistory
from src.api.schemas import (
    ApplicationCreate, ApplicationListOut, ApplicationOut, ApplicationUpdate,
    InterviewCreate, InterviewOut, InterviewUpdate, StatusHistoryOut,
)

router = APIRouter(prefix="/applications", tags=["applications"])

VALID_STATUSES = {"saved", "applied", "phone_screen", "interview", "offer", "rejected", "withdrawn"}


@router.get("", response_model=ApplicationListOut)
def list_applications(
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(Application)
    if status:
        query = query.filter(Application.status == status)
    total = query.count()
    apps = query.order_by(Application.updated_at.desc()).offset(offset).limit(limit).all()
    return ApplicationListOut(total=total, applications=apps)


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(body: ApplicationCreate, db: Session = Depends(get_db)):
    if body.status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status. Choose from: {VALID_STATUSES}")
    job = db.query(Job).filter(Job.id == body.job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")

    app = Application(
        job_id=body.job_id,
        resume_id=body.resume_id,
        status=body.status,
        applied_at=datetime.utcnow() if body.status != "saved" else None,
        notes=body.notes,
        updated_at=datetime.utcnow(),
    )
    db.add(app)
    db.flush()

    db.add(StatusHistory(
        application_id=app.id,
        from_status=None,
        to_status=body.status,
    ))
    db.commit()
    db.refresh(app)
    return app


@router.get("/{app_id}", response_model=ApplicationOut)
def get_application(app_id: int, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
    return app


@router.patch("/{app_id}", response_model=ApplicationOut)
def update_application(app_id: int, body: ApplicationUpdate, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")

    if body.status and body.status != app.status:
        if body.status not in VALID_STATUSES:
            raise HTTPException(400, f"Invalid status")
        db.add(StatusHistory(
            application_id=app.id,
            from_status=app.status,
            to_status=body.status,
            notes=body.notes,
        ))
        app.status = body.status
        if body.status == "applied" and not app.applied_at:
            app.applied_at = datetime.utcnow()

    if body.notes is not None:
        app.notes = body.notes
    if body.resume_id is not None:
        app.resume_id = body.resume_id

    app.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(app)
    return app


@router.get("/{app_id}/history", response_model=list[StatusHistoryOut])
def get_history(app_id: int, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
    return app.status_history


@router.post("/{app_id}/interviews", response_model=InterviewOut, status_code=201)
def add_interview(app_id: int, body: InterviewCreate, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")

    interview = Interview(
        application_id=app_id,
        round=body.round,
        scheduled_at=body.scheduled_at,
        notes=body.notes,
    )
    db.add(interview)

    # Auto-advance status to interview if not already further along
    if app.status in ("applied", "phone_screen", "saved"):
        db.add(StatusHistory(
            application_id=app_id,
            from_status=app.status,
            to_status="interview",
        ))
        app.status = "interview"
        app.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(interview)
    return interview


@router.patch("/interviews/{interview_id}", response_model=InterviewOut)
def update_interview(interview_id: int, body: InterviewUpdate, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(404, "Interview not found")

    for field, val in body.model_dump(exclude_none=True).items():
        setattr(interview, field, val)
    db.commit()
    db.refresh(interview)
    return interview
