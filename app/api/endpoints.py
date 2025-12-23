from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
from datetime import datetime

from app.db.session import get_db
from app.models.models import Video, VehicleDetection, VideoStatus
from app.schemas import schemas
from app.services.video_service import video_service
from app.core.config import settings

router = APIRouter()

@router.post("/videos/upload", response_model=schemas.Video)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Save file
    file_path = os.path.join(settings.STORAGE_PATH, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Create DB record
    db_video = Video(filename=file.filename, filepath=file_path)
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    
    # Trigger processing in background
    background_tasks.add_task(video_service.process_video, db_video.id, db)
    
    return db_video

@router.get("/videos/{video_id}", response_model=schemas.Video)
def get_video(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@router.get("/videos/{video_id}/detections", response_model=List[schemas.VehicleDetection])
def get_video_detections(video_id: int, db: Session = Depends(get_db)):
    return db.query(VehicleDetection).filter(VehicleDetection.video_id == video_id).all()

@router.get("/detections", response_model=List[schemas.VehicleDetection])
def search_detections(
    plate: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    query = db.query(VehicleDetection)
    if plate:
        query = query.filter(VehicleDetection.plate_number.like(f"%{plate}%"))
    if start_date:
        query = query.filter(VehicleDetection.created_at >= start_date)
    if end_date:
        query = query.filter(VehicleDetection.created_at <= end_date)
    
    return query.all()
