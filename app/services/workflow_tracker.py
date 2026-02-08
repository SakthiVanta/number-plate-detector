"""
Workflow Step Tracker for n8n-style visualization.
Manages ProcessingStep lifecycle and broadcasts updates via WebSocket.
"""
import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import ProcessingStep, StepStatus
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Define all processing steps in order
WORKFLOW_STEPS = [
    {"name": "VIDEO_UPLOAD", "order": 1, "label": "Video Upload", "icon": "upload"},
    {"name": "CONDITIONING", "order": 2, "label": "Video Conditioning", "icon": "adjust"},
    {"name": "DETECTION", "order": 3, "label": "Vehicle Detection", "icon": "car"},
    {"name": "TRACKING", "order": 4, "label": "ByteTrack Tracking", "icon": "route"},
    {"name": "CAPTURE", "order": 5, "label": "Golden Frame Capture", "icon": "camera"},
    {"name": "BATCHING", "order": 6, "label": "Collage Generation", "icon": "th"},
    {"name": "ORCHESTRATOR", "order": 7, "label": "Case Review", "icon": "gavel"},
    {"name": "VALIDATION", "order": 8, "label": "AI Validation", "icon": "check-circle"},
    {"name": "AUDITOR", "order": 9, "label": "Quality Audit", "icon": "shield-alt"},
    {"name": "COMMIT", "order": 10, "label": "Database Commit", "icon": "database"},
]

class WorkflowTracker:
    """Manages workflow step tracking and WebSocket broadcasting."""
    
    def __init__(self, video_id: int, db: Session):
        self.video_id = video_id
        self.db = db
        self._initialize_steps()
    
    def _initialize_steps(self):
        """Create all pending steps for this video."""
        for step_def in WORKFLOW_STEPS:
            existing = self.db.query(ProcessingStep).filter(
                ProcessingStep.video_id == self.video_id,
                ProcessingStep.step_name == step_def["name"]
            ).first()
            
            if not existing:
                step = ProcessingStep(
                    video_id=self.video_id,
                    step_name=step_def["name"],
                    step_order=step_def["order"],
                    status=StepStatus.PENDING
                )
                self.db.add(step)
        
        self.db.commit()
    
    def start_step(self, step_name: str, details: Optional[Dict[str, Any]] = None):
        """Mark a step as active."""
        step = self._get_step(step_name)
        if step:
            step.status = StepStatus.ACTIVE
            step.started_at = datetime.utcnow()
            if details:
                step.details = json.dumps(details)
            self.db.commit()
            self._broadcast_update(step)
            logger.info(f"[WORKFLOW] Step '{step_name}' started for video {self.video_id}")
    
    def complete_step(self, step_name: str, details: Optional[Dict[str, Any]] = None):
        """Mark a step as completed."""
        step = self._get_step(step_name)
        if step:
            step.status = StepStatus.COMPLETED
            step.completed_at = datetime.utcnow()
            if details:
                step.details = json.dumps(details)
            self.db.commit()
            self._broadcast_update(step)
            logger.info(f"[WORKFLOW] Step '{step_name}' completed for video {self.video_id}")
    
    def fail_step(self, step_name: str, error: str):
        """Mark a step as failed."""
        step = self._get_step(step_name)
        if step:
            step.status = StepStatus.FAILED
            step.completed_at = datetime.utcnow()
            step.error_message = error
            self.db.commit()
            self._broadcast_update(step)
            logger.error(f"[WORKFLOW] Step '{step_name}' failed for video {self.video_id}: {error}")
    
    def skip_step(self, step_name: str, reason: str):
        """Mark a step as skipped."""
        step = self._get_step(step_name)
        if step:
            step.status = StepStatus.SKIPPED
            step.completed_at = datetime.utcnow()
            step.details = json.dumps({"skip_reason": reason})
            self.db.commit()
            self._broadcast_update(step)
    
    def _get_step(self, step_name: str) -> Optional[ProcessingStep]:
        """Get step by name."""
        return self.db.query(ProcessingStep).filter(
            ProcessingStep.video_id == self.video_id,
            ProcessingStep.step_name == step_name
        ).first()
    
    def _broadcast_update(self, step: ProcessingStep):
        """Broadcast step update via WebSocket (stub for now)."""
        # This will be implemented in the WebSocket handler
        pass
    
    @staticmethod
    def get_workflow_definition():
        """Get the workflow steps definition for frontend."""
        return WORKFLOW_STEPS
    
    @staticmethod
    def get_video_steps(db: Session, video_id: int):
        """Get all processing steps for a video."""
        steps = db.query(ProcessingStep).filter(
            ProcessingStep.video_id == video_id
        ).order_by(ProcessingStep.step_order).all()
        
        return [{
            "id": s.id,
            "name": s.step_name,
            "order": s.step_order,
            "status": s.status.value,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "error": s.error_message,
            "details": json.loads(s.details) if s.details else {}
        } for s in steps]
