from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql import text
from app.db.session import get_db
from app.core.config import settings
import redis

router = APIRouter()

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    System Health Check
    - Database Connectivity
    - Redis Connectivity
    """
    status = {"status": "ok", "components": {}}
    
    # Check DB
    try:
        db.execute(text("SELECT 1"))
        status["components"]["db"] = "connected"
    except Exception as e:
        status["components"]["db"] = f"error: {str(e)}"
        status["status"] = "degraded"

    # Check Redis
    try:
        r = redis.from_url(settings.REDIS_URL, socket_timeout=1)
        r.ping()
        status["components"]["redis"] = "connected"
    except Exception as e:
        status["components"]["redis"] = f"error: {str(e)}"
        status["status"] = "degraded"
        
    return status
