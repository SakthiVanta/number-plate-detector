from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.models import VehicleCase, AgentLog
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/cases/{video_id}/{track_id}/logs")
async def get_case_logs(video_id: int, track_id: int, db: Session = Depends(get_db)):
    """
    Returns the forensic thought trail for a specific vehicle track.
    Used by the v5.0 "Agent Thinking" console.
    """
    case = db.query(VehicleCase).filter(
        VehicleCase.video_id == video_id,
        VehicleCase.track_id == track_id
    ).first()
    
    if not case:
        return []
    
    logs = db.query(AgentLog).filter(AgentLog.case_id == case.id).order_by(AgentLog.step_number).all()
    return logs

@router.get("/cases/{video_id}")
async def list_cases(video_id: int, db: Session = Depends(get_db)):
    """Lists all forensic cases for a specific video."""
    return db.query(VehicleCase).filter(VehicleCase.video_id == video_id).all()
