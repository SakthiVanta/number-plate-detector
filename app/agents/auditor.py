import logging
from sqlalchemy.orm import Session
from app.models.models import VehicleCase, AgentLog, VehicleDetection, CaseStatus
from app.agents.prompts import AUDITOR_PROMPT
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)

class AuditorAgent:
    """
    The Forensic Auditor: Cross-verifies findings and resolves mismatches.
    """
    
    def audit_case(self, db: Session, case_id: int, plate_text: str, vehicle_type: str, forensic_insight: str = None):
        """
        Cross-checks if the plate syntax matches the vehicle class.
        """
        plate_text = str(plate_text) if plate_text else plate_text
        from app.models.models import CaseStatus
        case = db.query(VehicleCase).filter(VehicleCase.id == case_id).first()
        if not case: return
        
        # 1. Semantic Validation
        is_logical = ai_service.semantic_validator(plate_text, vehicle_type)
        
        # 2. Sync with Primary Detection Record
        detection = db.query(VehicleDetection).filter(
            VehicleDetection.video_id == case.video_id,
            VehicleDetection.track_id == case.track_id
        ).first()

        step = 10 # Post-processing step
        
        # v5.1 Explicit Doubt: If plate is UNCERTAIN/NO PLATE, don't allow it to pass as solved
        if not plate_text or plate_text in ["UNCERTAIN", "NO PLATE", "FAILED"]:
            self._log_audit(db, case_id, step, "AUDIT_REJECTED", 
                           f"Forensic Audit: AI was not confident in its reading. No data returned to avoid false positive.")
            case.status = CaseStatus.FLAGGED_UNCERTAIN
            if detection:
                detection.is_validated = False
                detection.plate_number = "PENDING"
                detection.ocr_source = "AUDIT_REJECTED"
        elif not is_logical:
            self._log_audit(db, case_id, step, "SEMANTIC_MISMATCH", 
                           f"Warning: Forensic Auditor detected a mismatch. Plate '{plate_text}' is unlikely for vehicle type '{vehicle_type}'.")
            case.status = CaseStatus.FLAGGED_UNCERTAIN
            if detection:
                detection.is_validated = False
                detection.ocr_source += " (Flagged)"
        else:
            self._log_audit(db, case_id, step, "AUDIT_VERIFIED", 
                           f"Forensic verification successful. {forensic_insight if forensic_insight else 'Plate and vehicle signatures are consistent.'}")
            case.status = CaseStatus.SOLVED
            if detection:
                detection.is_validated = True
                detection.plate_number = plate_text
                detection.vehicle_type = vehicle_type
            
        case.final_plate = plate_text
        case.vehicle_class = vehicle_type
        if forensic_insight:
            case.forensic_insight = forensic_insight
            if detection:
                detection.forensic_insight = forensic_insight
        db.commit()

    def _log_audit(self, db: Session, case_id: int, step: int, action: str, reasoning: str):
        log = AgentLog(
            case_id=case_id,
            step_number=step,
            agent_name="Auditor",
            action_taken=action,
            reasoning=reasoning
        )
        db.add(log)
        db.flush()
        print(f"    └─ [FORENSIC AUDITOR] {action}: {reasoning}")
        logger.info(f"[AUDIT #{case_id}] {action}: {reasoning}")

auditor_agent = AuditorAgent()
