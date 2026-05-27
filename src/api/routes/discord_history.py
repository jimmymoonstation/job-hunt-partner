import json
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.models import DiscordSession

router = APIRouter(prefix="/discord", tags=["discord"])


@router.get("/history/{channel_id}")
def get_history(channel_id: str, db: Session = Depends(get_db)):
    session = db.query(DiscordSession).filter_by(channel_id=channel_id).first()
    if not session:
        return {"history": []}
    return {"history": json.loads(session.message_history_json)}


@router.post("/history/{channel_id}")
def save_history(channel_id: str, body: dict, db: Session = Depends(get_db)):
    session = db.query(DiscordSession).filter_by(channel_id=channel_id).first()
    if not session:
        session = DiscordSession(channel_id=channel_id, message_history_json="[]")
        db.add(session)

    history = json.loads(session.message_history_json)
    history.append({"role": "user", "content": body["user"]})
    history.append({"role": "assistant", "content": body["assistant"]})

    # Keep last MAX_HISTORY messages
    if len(history) > 40:
        history = history[-40:]

    session.message_history_json = json.dumps(history)
    session.last_active = datetime.utcnow()
    db.commit()
    return {"ok": True}
