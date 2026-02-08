import logging
import redis
import json
import datetime
from app.core.config import settings

class RedisLogHandler(logging.Handler):
    """
    Custom Logging Handler that publishes log records to a Redis Channel.
    This allows WebSockets to stream server-side logs to the frontend in real-time.
    """
    def __init__(self, redis_url: str, channel: str = "system_logs"):
        super().__init__()
        self.redis_url = redis_url
        self.channel = channel
        self.redis_client = None
        self._connect()

    def _connect(self):
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        except Exception as e:
            print(f"Failed to connect to Redis for Logging: {e}")

    def emit(self, record):
        try:
            if not self.redis_client:
                self._connect()
                if not self.redis_client: return

            # Filter out noisy logs if needed
            if record.name in ["uvicorn.access", "watchfiles.main"]:
                return

            log_entry = {
                "timestamp": datetime.datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.module,
                "funcName": record.funcName,
                "line": record.lineno,
                # Simple heuristic to categorize logs for frontend filtering
                "event_type": self._categorize(record.getMessage()) 
            }
            
            self.redis_client.publish(self.channel, json.dumps(log_entry))
        except Exception:
            self.handleError(record)

    def _categorize(self, msg: str) -> str:
        msg_upper = msg.upper()
        if "GEMINI" in msg_upper: return "GEMINI"
        if "YOLO" in msg_upper or "DETECT" in msg_upper: return "DETECTOR"
        if "FRAME" in msg_upper or "VIDEO" in msg_upper: return "CAPTURER"
        if "QC" in msg_upper or "RECHECK" in msg_upper: return "QC"
        return "SYSTEM"


class DatabaseLogHandler(logging.Handler):
    """
    Custom Logging Handler for In-Process mode (no Redis/Celery).
    Writes logs directly to ProcessingLog table so they appear in UI.
    """
    def __init__(self):
        super().__init__()
        self.current_video_id = None  # Set by worker/video service

    def set_video_id(self, video_id: int):
        """Called by video service to associate logs with a video."""
        self.current_video_id = video_id

    def emit(self, record):
        try:
            # Filter noise
            if record.name in ["uvicorn.access", "watchfiles.main"]:
                return
            
            # Only save logs if we have an active video context
            if not self.current_video_id:
                return

            from app.db.session import SessionLocal
            from app.models.models import ProcessingLog

            msg = record.getMessage()
            event_type = self._categorize(msg)

            db = SessionLocal()
            try:
                log = ProcessingLog(
                    video_id=self.current_video_id,
                    event_type=event_type,
                    message=msg,
                    is_error=(record.levelname in ["ERROR", "CRITICAL"])
                )
                db.add(log)
                db.commit()
            finally:
                db.close()
        except Exception:
            # Silently fail to avoid infinite loops
            pass

    def _categorize(self, msg: str) -> str:
        """Categorize log message for frontend filtering."""
        msg_upper = msg.upper()
        if "ORCHESTRATOR" in msg_upper or "[CASE" in msg_upper:
            return "ORCHESTRATOR"
        if "AUDITOR" in msg_upper or "AUDIT" in msg_upper:
            return "AUDITOR"
        if "GEMINI" in msg_upper or "AI_RECHECK" in msg_upper:
            return "GEMINI"
        if "CAPTURE" in msg_upper or "SNIP" in msg_upper:
            return "CAPTURER"
        if "DECISION MATRIX" in msg_upper or "FCF" in msg_upper:
            return "MATRIX"
        if "DETECTOR" in msg_upper or "YOLO" in msg_upper:
            return "DETECTOR"
        if "CONSENSUS" in msg_upper:
            return "CONSENSUS"
        return "SYSTEM"

# Global instance for In-Process mode
db_log_handler = DatabaseLogHandler()
