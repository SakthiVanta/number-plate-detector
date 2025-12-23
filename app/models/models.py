from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Boolean, Index
from sqlalchemy.orm import relationship, backref
from datetime import datetime
import enum
from app.db.session import Base

class VideoStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class RecheckStatus(enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    NONE = "none"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True) # Added full_name support
    hashed_password = Column(String, nullable=False)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    videos = relationship("Video", back_populates="owner")

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    filepath = Column(String)
    output_path = Column(String, nullable=True)
    status = Column(Enum(VideoStatus), default=VideoStatus.PENDING)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    is_chunk = Column(Boolean, default=False)
    parent_video_id = Column(Integer, ForeignKey("videos.id"), nullable=True)
    analytics_data = Column(String, nullable=True) # JSON blob for charts & unique counts
    
    owner = relationship("User", back_populates="videos")
    detections = relationship("VehicleDetection", back_populates="video", cascade="all, delete-orphan")
    batches = relationship("DetectionBatch", back_populates="video", cascade="all, delete-orphan")
    chunks = relationship("Video", back_populates="parent_video", cascade="all, delete-orphan")
    parent_video = relationship("Video", back_populates="chunks", remote_side=[id])

Index("idx_video_status", Video.status)
Index("idx_video_owner", Video.owner_id)

class VehicleDetection(Base):
    __tablename__ = "vehicle_detections"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"))
    batch_id = Column(Integer, ForeignKey("detection_batches.id"), nullable=True) # Link to Gemini Batch
    plate_number = Column(String) 
    confidence = Column(Float)
    raw_ocr_text = Column(String, nullable=True) 
    recheck_status = Column(Enum(RecheckStatus), default=RecheckStatus.NONE)
    is_validated = Column(Boolean, default=False) # Agent QC Flag
    vehicle_info = Column(String, nullable=True) 
    make_model = Column(String, nullable=True) # More specific than info
    color_conf = Column(Float, nullable=True) # Confidence in color
    best_local_plate = Column(String, nullable=True) # v2.3.2 Fallback Local OCR
    
    # v2.5 Safety & Forensic Fields
    vehicle_type = Column(String, default="UNKNOWN") # CAR, BIKE, SCOOTER, etc.
    helmet_status = Column(String, default="N/A") # HELMET, NO_HELMET, N/A
    passenger_count = Column(Integer, default=0)
    
    # v3.0 Agentic Integrity Fields
    visual_embedding = Column(String, nullable=True) # Vector representation for Re-ID logic
    blur_score = Column(Float, nullable=True) # Laplacian Variance
    ocr_source = Column(String, default="LOCAL") # LOCAL, CLOUD, or CONSENSUS
    best_frame_timestamp = Column(Float, nullable=True) # Millisecond of the "Golden Frame"
    raw_inference_log = Column(String, nullable=True) # JSON blob for audit review
    
    timestamp = Column(Float)  
    frame_index = Column(Integer)
    track_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    video = relationship("Video", back_populates="detections")
    batch = relationship("DetectionBatch", back_populates="detections")

class DetectionBatch(Base):
    __tablename__ = "detection_batches"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"))
    collage_path = Column(String) # Path to the 10-image stitched grid
    raw_json = Column(String, nullable=True) # Gemini response JSON
    cost_estimate = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    video = relationship("Video", back_populates="batches")
    detections = relationship("VehicleDetection", back_populates="batch")

class ProcessingLog(Base):
    __tablename__ = "processing_logs"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"))
    frame_index = Column(Integer, nullable=True)
    timestamp = Column(Float, nullable=True)
    event_type = Column(String) # MOTION, DETECTION, AI_RECHECK, ERROR
    message = Column(String)
    extra_data = Column(String, nullable=True) # JSON or Image path for rich details
    is_error = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    video = relationship("Video", backref=backref("logs", cascade="all, delete-orphan"))

# Composite Index for faster searching
Index("idx_detections_plate_ts", VehicleDetection.plate_number, VehicleDetection.timestamp)
Index("idx_detections_video_ts", VehicleDetection.video_id, VehicleDetection.timestamp)
