from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import logging
from app.api import auth, videos, detections, system, v2_api
from app.db.session import engine, Base, SessionLocal
from app.models.models import Video, User
from jose import jwt
import os
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print(">>> Starting ALPR Pro v2 API...")
# Create database tables
print(">>> Connecting to Database...")
Base.metadata.create_all(bind=engine)
print(">>> Database Tables Verified.")

# Ensure storage directory exists
os.makedirs(settings.STORAGE_PATH, exist_ok=True)

app = FastAPI(
    title="CCTV Vehicle Detection & ALPR API",
    description="Production-ready ALPR Backend with Auth and full CRUD",
    version="1.0.1"
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "detail": str(exc)},
    )

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(videos.router, prefix="/api/videos", tags=["Videos"])
app.include_router(detections.router, prefix="/api/detections", tags=["Detections"])
app.include_router(system.router, prefix="/api", tags=["System"])
app.include_router(v2_api.router, prefix="/api/v2", tags=["Agentic v2.3"])

# Serve Frontend
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

@app.get("/")
def root():
    return FileResponse("frontend/index.html")

@app.get("/{page}.html")
def serve_html(page: str):
    path = f"frontend/{page}.html"
    if os.path.exists(path):
        return FileResponse(path)
    return JSONResponse(status_code=404, content={"message": "Not Found"})

@app.get("/api/raw_vids/{video_id}")
async def raw_stream_bypass(video_id: int, token: str = None):
    from app.db.session import SessionLocal
    from app.models.models import User, Video
    from jose import jwt
    
    if not token:
        raise HTTPException(status_code=401, detail="Token missing")
    
    db = SessionLocal()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid user")
            
        video = db.query(Video).filter(Video.id == video_id, Video.owner_id == user.id).first()
        if not video or not os.path.exists(video.filepath):
            raise HTTPException(status_code=404, detail="Video not found")
            
        return FileResponse(video.filepath)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
    finally:
        db.close()

@app.get("/api/raw_files/{file_path:path}")
async def get_raw_file(file_path: str):
    # Forensic assets (collages/crops)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    # v2.4 Note: Security can be tightened here by checking token if needed
    return FileResponse(file_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
