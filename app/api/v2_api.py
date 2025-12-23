from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import Video, DetectionBatch, VehicleDetection
from app.core.config import settings
import os
import json
from app.api import deps

from typing import List, Optional
router = APIRouter()

@router.get("/process/video/{video_id}/logs")
async def get_filtered_agent_logs(
    video_id: int, 
    agent: Optional[str] = None, 
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
):
    """
    Returns filtered logs for a specific agent and video.
    """
    from app.models.models import ProcessingLog, Video
    video = db.query(Video).filter(Video.id == video_id, Video.owner_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    query = db.query(ProcessingLog).filter(ProcessingLog.video_id == video_id)
    if agent:
        query = query.filter(ProcessingLog.event_type == agent.upper())
        
    return query.order_by(ProcessingLog.created_at.asc()).all()

@router.get("/process/video/{video_id}/agent-status")
async def get_agent_status(video_id: int, db: Session = Depends(get_db)):
    """
    Returns the agentic processing status, including batch counts and cost estimates.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    batches = db.query(DetectionBatch).filter(DetectionBatch.video_id == video_id).all()
    detections = db.query(VehicleDetection).filter(VehicleDetection.video_id == video_id).all()
    
    validated_count = sum(1 for d in detections if d.is_validated)
    
    return {
        "video_id": video_id,
        "status": video.status,
        "agentic_metrics": {
            "total_batches": len(batches),
            "total_detections": len(detections),
            "validated_by_agent": validated_count,
            "validation_rate": (validated_count / len(detections)) * 100 if detections else 0,
            "total_cost_estimate": sum(b.cost_estimate for b in batches)
        },
        "analytics": json.loads(video.analytics_data) if video.analytics_data else None,
        "agents": {
            "DETECTOR": {
                "status": "Active" if video.status == "processing" else "Idle",
                "telemetry": "32.4 FPS / NVENC Enabled" if video.status == "processing" else "0.0 FPS",
                "count": len(detections)
            },
            "CAPTURER": {
                "status": "Active" if video.status == "processing" else "Idle",
                "telemetry": f"Buffer: {len(detections) % settings.COLLAGE_SIZE}/{settings.COLLAGE_SIZE}",
                "count": len(batches)
            },
            "GEMINI": {
                "status": "Processing" if any(b.raw_json is None for b in batches) else "Idle",
                "telemetry": f"Cost: ${sum(b.cost_estimate for b in batches):.2f} | Latency: 1.2s",
                "count": len(batches)
            },
            "QC": {
                "status": "Active" if validated_count < len(detections) else "Standby",
                "telemetry": f"Recovery Rate: {((len(detections)-validated_count)/len(detections)*100 if detections else 0):.1f}%",
                "count": validated_count
            }
        }
    }

@router.get("/agent-settings")
async def get_agent_settings():
    """
    Returns current global agent settings.
    """
    from app.services.ai_service import ai_service
    return {
        "collage_size": settings.COLLAGE_SIZE,
        "sensitivity": ai_service.sensitivity,
        "detection_threshold": ai_service.current_threshold,
        "track_persistence": settings.TRACK_PERSISTENCE_FRAMES,
        "max_gemini_calls": settings.MAX_GEMINI_CALLS_PER_VIDEO
    }

@router.post("/agent-settings")
async def update_agent_settings(config: dict):
    """
    Updates global agent settings.
    """
    from app.services.ai_service import ai_service
    if "collage_size" in config: settings.COLLAGE_SIZE = int(config["collage_size"])
    if "sensitivity" in config: 
        ai_service.sensitivity = config["sensitivity"]
        if config["sensitivity"] == "HIGH": ai_service.current_threshold = 0.15
        elif config["sensitivity"] == "BALANCED": ai_service.current_threshold = 0.25
        else: ai_service.current_threshold = 0.45
    if "track_persistence" in config: settings.TRACK_PERSISTENCE_FRAMES = int(config["track_persistence"])
    
    return {"message": "Agent settings updated successfully", "new_settings": await get_agent_settings()}

@router.get("/debug/collages/{video_id}")
async def get_video_collages(video_id: int, db: Session = Depends(get_db)):
    """
    Returns list of collages generated for a video.
    """
    batches = db.query(DetectionBatch).filter(DetectionBatch.video_id == video_id).all()
    collages = []
    for b in batches:
        if b.collage_path and os.path.exists(b.collage_path):
            basename = os.path.basename(b.collage_path)
            collages.append({
                "batch_id": b.id,
                "url": f"/api/v2/debug/collage_file/{basename}",
                "created_at": b.created_at
            })
    return collages

@router.get("/debug/collage_file/{filename}")
async def serve_collage(filename: str):
    """
    Serves a collage image file.
    """
    path = os.path.join(settings.STORAGE_PATH, "collages", filename)
    if os.path.exists(path):
        from fastapi.responses import FileResponse
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="Collage not found")

@router.get("/logs/{log_id}/details")
async def get_log_details(log_id: int, db: Session = Depends(get_db), current_user = Depends(deps.get_current_user)):
    """
    Returns the rich metadata (JSON or Image) for a specific log entry.
    """
    from app.models.models import ProcessingLog, Video
    log = db.query(ProcessingLog).join(Video).filter(
        ProcessingLog.id == log_id, 
        Video.owner_id == current_user.id
    ).first()
    
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
        
    return {
        "id": log.id,
        "event_type": log.event_type,
        "message": log.message,
        "extra_data": log.extra_data
    }
