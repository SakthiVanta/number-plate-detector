from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.db.session import get_db
from app.models.models import VehicleDetection, Video
from app.schemas import schemas
from app.api import deps

router = APIRouter()

@router.get("/", response_model=schemas.PaginatedVehicleDetection)
def list_detections(
    plate: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    video_id: Optional[int] = None,
    min_confidence: Optional[float] = None,
    recheck_status: Optional[str] = None,
    vehicle_query: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
):
    from sqlalchemy.orm import joinedload
    # v2.7: Explicit ownership check for better reliability
    owned_video_ids = [v[0] for v in db.query(Video.id).filter(Video.owner_id == current_user.id).all()]
    query = db.query(VehicleDetection).filter(VehicleDetection.video_id.in_(owned_video_ids))
    
    if video_id:
        # v2.7: Support parent/chunk video filtering - find chunk IDs if searching by parent
        v = db.query(Video).filter(Video.id == video_id).first()
        if v and not v.is_chunk:
            chunk_ids = [c.id for c in v.chunks] + [v.id]
            query = query.filter(VehicleDetection.video_id.in_(chunk_ids))
        else:
            query = query.filter(VehicleDetection.video_id == video_id)
            
    if plate:
        query = query.filter(VehicleDetection.plate_number.icontains(plate))
    if min_confidence:
        query = query.filter(VehicleDetection.confidence >= min_confidence)
    if recheck_status:
        query = query.filter(VehicleDetection.recheck_status == recheck_status)
    if vehicle_query:
        query = query.filter(
            (VehicleDetection.vehicle_info.icontains(vehicle_query)) | 
            (VehicleDetection.make_model.icontains(vehicle_query))
        )
    if start_date:
        query = query.filter(VehicleDetection.created_at >= start_date)
    if end_date:
        query = query.filter(VehicleDetection.created_at <= end_date)
        
    total = query.count()
    items = query.options(joinedload(VehicleDetection.batch)).order_by(VehicleDetection.created_at.desc()).offset(skip).limit(limit).all()
    
    return {"items": items, "total": total}

@router.get("/{detection_id}", response_model=schemas.VehicleDetection)
def get_detection(
    detection_id: int, 
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
):
    detection = db.query(VehicleDetection).join(Video).filter(
        VehicleDetection.id == detection_id, 
        Video.owner_id == current_user.id
    ).first()
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    return detection

@router.patch("/{detection_id}", response_model=schemas.VehicleDetection)
def update_detection(
    detection_id: int,
    plate_number: str,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
):
    detection = db.query(VehicleDetection).join(Video).filter(
        VehicleDetection.id == detection_id, 
        Video.owner_id == current_user.id
    ).first()
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    
    detection.plate_number = plate_number.upper()
    db.commit()
    db.refresh(detection)
    return detection

@router.delete("/{detection_id}")
def delete_detection(
    detection_id: int, 
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
):
    detection = db.query(VehicleDetection).join(Video).filter(
        VehicleDetection.id == detection_id, 
        Video.owner_id == current_user.id
    ).first()
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
        
    db.delete(detection)
    db.commit()
    return {"message": "Detection deleted successfully"}
