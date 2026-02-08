from pydantic_settings import BaseSettings
from pydantic import AliasChoices, Field

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./vehicle_detect.db"
    YOLO_MODEL_PATH: str = "weights/yolo11n.pt"
    PLATE_MODEL_PATH: str = "weights/license_plate_detector.pt"
    STORAGE_PATH: str = "storage"
    FRAME_SAMPLING_RATE: float = 0.5
    REDIS_URL: str = "redis://localhost:6379/0"
    USE_CELERY: bool = False # Set to False to run processing in-process (No Redis needed)
    
    SECRET_KEY: str = "your-super-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # v5.1 Security Hardening
    ENABLE_SETUP_WIZARD: bool = True # Forces setup on first load if no admin exists    
    # Global AI Rechecker Settings
    GEMINI_API_KEY: str = Field("", validation_alias=AliasChoices('GEMINI_API_KEY', 'GOOGLE_API_KEY'))
    RECHECK_CONFIDENCE_THRESHOLD: float = 0.85
    ENABLE_GLOBAL_RECHECK: bool = True
    
    # v2.3 Agentic & Collage Settings
    COLLAGE_SIZE: int = 20 # Increased from 9 for better batch coverage
    COLLAGE_GRID_SIZE: tuple = (4, 5) # 4 rows x 5 columns = 20 slots 
    DETECTION_THRESHOLD: float = 0.25 # Lowered for high sensitivity
    TRACK_PERSISTENCE_FRAMES: int = 6 # Was 15, reduced for high-speed traffic
    AGENTS_SENSITIVITY: str = "HIGH" # HIGH, BALANCED, LOW

    # v5.1 Cost Optimization
    ENABLE_TIERED_ROUTING: bool = True # If True, use Flash first, then Pro if uncertain
    MODEL_FLASH: str = "gemini-2.5-flash"
    MODEL_PRO: str = "gemini-3-flash"
    
    # Optimization & Chunking
    CHUNK_DURATION_MINUTES: int = 15
    CHUNK_OVERLAP_SECONDS: int = 5
    MAX_GEMINI_CALLS_PER_VIDEO: int = 50
    # For long videos, we might disable generating the full output video to save space/time
    # and rely on the JSON metadata + frontend overlays.
    ENABLE_FULL_VIDEO_OUTPUT: bool = True 
    
    # v2.1 Advanced Optimizations
    FRAME_SKIP_AI: int = 3 # Run YOLO/OCR every 3rd frame (effectively 20fps for 60fps video)
    ROI_MASK_PATH: str = "storage/roi_mask.png" # Optional mask for motion detection

    # v4.0 Hyper-Resolution Settings
    SLICE_HEIGHT: int = 640
    SLICE_WIDTH: int = 640
    OVERLAP_RATIO: float = 0.2
    ENABLE_SUPER_RES: bool = True
    SUPER_RES_MODEL: str = "RealESRGAN_x4plus"
    ENABLE_VEHICLE_MATCHING: bool = True # Semantic Validator
    STABILIZE_VIDEO: bool = True # Video Conditioner
    
    class Config:
        env_file = ".env"

settings = Settings()
