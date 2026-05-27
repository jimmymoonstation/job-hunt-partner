import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.models import Resume
from src.api.schemas import ResumeCreate, ResumeListOut, ResumeOut

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.get("", response_model=ResumeListOut)
def list_resumes(db: Session = Depends(get_db)):
    resumes = db.query(Resume).order_by(Resume.created_at.desc()).all()
    return ResumeListOut(resumes=resumes)


@router.post("", response_model=ResumeOut, status_code=201)
def create_resume(body: ResumeCreate, db: Session = Depends(get_db)):
    resume = Resume(
        name=body.name,
        version=body.version,
        tags=json.dumps(body.tags),
        content_json=json.dumps(body.content_json),
        file_path=body.file_path,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(resume_id: int, db: Session = Depends(get_db)):
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(404, "Resume not found")
    return resume


@router.put("/{resume_id}", response_model=ResumeOut)
def update_resume(resume_id: int, body: ResumeCreate, db: Session = Depends(get_db)):
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(404, "Resume not found")
    resume.name = body.name
    resume.version = body.version
    resume.tags = json.dumps(body.tags)
    resume.content_json = json.dumps(body.content_json)
    resume.file_path = body.file_path
    db.commit()
    db.refresh(resume)
    return resume


@router.delete("/{resume_id}", status_code=204)
def delete_resume(resume_id: int, db: Session = Depends(get_db)):
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(404, "Resume not found")
    db.delete(resume)
    db.commit()
