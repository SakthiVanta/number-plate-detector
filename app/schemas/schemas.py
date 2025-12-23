from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from app.models.models import VideoStatus

class UserBase(BaseModel):
    email: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: int
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[int] = None

class VehicleDetectionBase(BaseModel):
    plate_number: str
    confidence: float
    timestamp: float
    frame_index: int

class DetectionBatch(BaseModel):
    id: int
    video_id: int
    collage_path: str
    raw_json: Optional[str]
    cost_estimate: float
    created_at: datetime

    class Config:
        from_attributes = True

class VehicleDetection(VehicleDetectionBase):
    id: int
    video_id: int
    batch_id: Optional[int]
    batch: Optional[DetectionBatch] = None # Nested Forensic Data
    raw_ocr_text: Optional[str]
    recheck_status: Optional[str]
    is_validated: bool
    vehicle_info: Optional[str]
    make_model: Optional[str]
    color_conf: Optional[float]
    
    # v2.5 Safety & Forensic Fields
    vehicle_type: Optional[str] = "UNKNOWN"
    helmet_status: Optional[str] = "N/A"
    passenger_count: Optional[int] = 0
    
    # v3.0 Agentic Integrity Fields
    visual_embedding: Optional[str] = None
    blur_score: Optional[float] = 0.0
    ocr_source: Optional[str] = None
    best_frame_timestamp: Optional[float] = 0.0
    raw_inference_log: Optional[str] = None
    
    track_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True

class PaginatedVehicleDetection(BaseModel):
    items: List[VehicleDetection]
    total: int

class ProcessingLog(BaseModel):
    id: int
    video_id: int
    frame_index: Optional[int]
    timestamp: Optional[float]
    event_type: str
    message: str
    is_error: bool
    created_at: datetime

    class Config:
        from_attributes = True

class VideoBase(BaseModel):
    filename: str

class VideoCreate(VideoBase):
    filepath: str

class Video(VideoBase):
    id: int
    filepath: str
    output_path: Optional[str]
    status: VideoStatus
    created_at: datetime
    analytics_data: Optional[str] = None # JSON blob for charts & unique counts

    class Config:
        from_attributes = True
