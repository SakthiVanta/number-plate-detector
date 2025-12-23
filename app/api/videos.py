from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
import logging

logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.models.models import Video, VideoStatus, User
from app.schemas import schemas
from app.services.video_service import video_service
from app.core.config import settings
from app.api import deps

router = APIRouter()

from app.worker import process_video_task

@router.post("/upload", response_model=schemas.Video)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
):
    os.makedirs(settings.STORAGE_PATH, exist_ok=True)
    file_path = os.path.join(settings.STORAGE_PATH, f"{current_user.id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    db_video = Video(filename=file.filename, filepath=file_path, owner_id=current_user.id)
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    
    # Trigger processing
    if settings.USE_CELERY:
        try:
            process_video_task.delay(db_video.id)
        except Exception:
            # Automatic fallback if Redis is down
            background_tasks.add_task(process_video_task, db_video.id)
    else:
        background_tasks.add_task(process_video_task, db_video.id)
    
    return db_video

@router.get("/", response_model=List[schemas.Video])
def list_videos(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
):
    return db.query(Video).filter(Video.owner_id == current_user.id).offset(skip).limit(limit).all()

@router.get("/stream/{video_id}")
def stream_video(
    video_id: int,
    original: bool = Query(True),
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    from jose import jwt
    user = None
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
            user = db.query(User).filter(User.id == user_id).first()
        except Exception:
             pass
    
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    video = db.query(Video).filter(Video.id == video_id, Video.owner_id == user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    path = video.filepath if original else video.output_path
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(path)

@router.get("/{video_id}", response_model=schemas.Video)
def get_video(
    video_id: int, 
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
):
    video = db.query(Video).filter(Video.id == video_id, Video.owner_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@router.delete("/{video_id}")
def delete_video(
    video_id: int, 
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
):
    video = db.query(Video).filter(Video.id == video_id, Video.owner_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Delete files
    if os.path.exists(video.filepath):
        os.remove(video.filepath)
    if video.output_path and os.path.exists(video.output_path):
        os.remove(video.output_path)
        
    db.delete(video)
    db.commit()
    return {"message": "Video deleted successfully"}


@router.get("/{video_id}/report")
def get_video_report(
    video_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
):
    video = db.query(Video).filter(Video.id == video_id, Video.owner_id == current_user.id).first()
    if not video or not video.output_path:
        raise HTTPException(status_code=404, detail="Report not generated")
        
    json_path = os.path.join(settings.STORAGE_PATH, "results", f"results_{video.id}_{video.filename}.json")
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="JSON report file not found")
        
    return FileResponse(json_path, media_type="application/json", filename=f"ALPR_Report_{video.filename}.json")

@router.get("/{video_id}/logs", response_model=List[schemas.ProcessingLog])
def get_video_logs(
    video_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
):
    video = db.query(Video).filter(Video.id == video_id, Video.owner_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    from app.models.models import ProcessingLog
    return db.query(ProcessingLog).filter(ProcessingLog.video_id == video_id).order_by(ProcessingLog.created_at.asc()).all()
