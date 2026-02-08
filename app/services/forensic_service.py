import hashlib
import os
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.models.models import VehicleCase, VehicleDetection, AgentLog
import logging

logger = logging.getLogger(__name__)

class ForensicService:
    """
    v5.1 Forensic Integrity Service.
    Handles:
    - Chain of Custody (SHA-256 Hashing)
    - XAI (Explainable API) Logging
    - Stalker Alert (Frequency Analysis)
    """

    def generate_hash(self, file_path: str) -> str:
        """
        Generates SHA-256 hash of a file for Chain of Custody.
        """
        if not file_path or not os.path.exists(file_path):
            return None
        
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                # Read and update hash string value in blocks of 4K
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Hashing failed for {file_path}: {e}")
            return None

    def log_xai(self, db: Session, case_id: int, agent_name: str, action: str, reasoning: str, xai_explanation: str = None):
        """
        Logs an action with a human-readable 'Why' (XAI).
        """
        step = db.query(func.max(AgentLog.step_number)).filter(AgentLog.case_id == case_id).scalar() or 0
        
        log = AgentLog(
            case_id=case_id,
            step_number=step + 1,
            agent_name=agent_name,
            action_taken=action,
            reasoning=reasoning,
            xai_reasoning=xai_explanation
        )
        db.add(log)
        db.commit()

    def check_for_stalker(self, db: Session, plate_number: str, hours: int = 24, threshold: int = 5) -> bool:
        """
        Stalker Alert: Checks if a plate has been seen > 'threshold' times in the last 'hours'.
        """
        if not plate_number or "UNKNOWN" in plate_number or len(plate_number) < 4:
            return False

        time_window = datetime.utcnow() - timedelta(hours=hours)
        
        # Count distinct video appearances (to avoid counting 100 frames in 1 video as stalking)
        count = db.query(func.count(VehicleCase.id)).join(VehicleCase.video).filter(
            VehicleCase.final_plate == plate_number,
            VehicleCase.created_at >= time_window
        ).scalar()
        
        if count and count >= threshold:
            logger.warning(f"[STALKER ALERT] Vehicle {plate_number} seen {count} times in last {hours} hours!")
            return True
        return False

    def mark_stalker(self, db: Session, case_id: int):
        case = db.query(VehicleCase).filter(VehicleCase.id == case_id).first()
        if case:
            case.is_stalker = True
            db.commit()

forensic_service = ForensicService()
