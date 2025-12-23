import cv2
import logging
import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import VehicleCase, AgentLog, CaseStatus
from app.agents.prompts import ORCHESTRATOR_PROMPT
from app.services.ai_service import ai_service
from app.services.enhancer_service import enhancer_manager

logger = logging.getLogger(__name__)

class OrchestratorAgent:
    """
    The Case Manager: Decides how to process a vehicle detection.
    """
    
    def process_track(self, db: Session, video_id: int, track_id: int, vehicle_crop, metadata: dict):
        """
        1. Look for existing case
        2. Analyze quality
        3. Decide on tools (Enhance? Cloud OCR?)
        4. Log reasoning
        """
        # 1. Fetch or Create Case
        case = db.query(VehicleCase).filter(
            VehicleCase.video_id == video_id,
            VehicleCase.track_id == track_id
        ).first()
        
        if not case:
            case = VehicleCase(
                video_id=video_id,
                track_id=track_id,
                status=CaseStatus.OPEN
            )
            db.add(case)
            db.flush()
            self._log_thought(db, case.id, 1, "INITIAL_SCAN", "New vehicle detected. Opening forensic case file.")

        # 2. Quality Audit
        blur_score = ai_service.quality_gatekeeper_score(vehicle_crop)
        case.confidence_score = blur_score # Use as initial metric
        
        step = 2
        needs_enhancement = blur_score < 100 # v5.0 Threshold
        
        if needs_enhancement:
            self._log_thought(db, case.id, step, "ENHANCEMENT_TRIGGER", f"Image blurry ({blur_score:.1f}). Invoking Neural Enhancer Agent.")
            # Tool Call: Enhancer (Simulator for alpha)
            enhanced = enhancer_manager.enhance_crop(vehicle_crop)
            # In a real v5.0, we would save the enhanced frame path here
            # case.enhanced_frame_path = ...
            step += 1
        
        # 3. OCR Selection
        # If blurry and enhanced, we might prefer Cloud OCR
        use_cloud = needs_enhancement or (metadata.get('recheck_required') == True)
        
        if use_cloud:
            self._log_thought(db, case.id, step, "HYBRID_OCR_SELECT", "Low confidence/High difficulty. Routing payload to Gemini Cloud Agent.")
            # This would integrate with existing rechecker logic
        else:
            self._log_thought(db, case.id, step, "HYBRID_OCR_SELECT", "High-fidelity crop. Proceeding with Local OCR (Speed optimized).")
            
        db.commit()
        return case

    def _log_thought(self, db: Session, case_id: int, step: int, action: str, reasoning: str, tool_output: dict = None):
        log = AgentLog(
            case_id=case_id,
            step_number=step,
            agent_name="Orchestrator",
            action_taken=action,
            reasoning=reasoning,
            tool_output=json.dumps(tool_output) if tool_output else None
        )
        db.add(log)
        db.flush()
        print(f"    └─ [CASE #{case_id}] {action}: {reasoning}")
        logger.info(f"[CASE #{case_id}] Step {step}: {action} - {reasoning}")

orchestrator = OrchestratorAgent()
