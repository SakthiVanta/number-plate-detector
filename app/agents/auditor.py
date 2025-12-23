import logging
from sqlalchemy.orm import Session
from app.models.models import VehicleCase, AgentLog
from app.agents.prompts import AUDITOR_PROMPT
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)

class AuditorAgent:
    """
    The Forensic Auditor: Cross-verifies findings and resolves mismatches.
    """
    
    def audit_case(self, db: Session, case_id: int, plate_text: str, vehicle_type: str):
        """
        Cross-checks if the plate syntax matches the vehicle class.
        """
        from app.models.models import CaseStatus
        case = db.query(VehicleCase).filter(VehicleCase.id == case_id).first()
        if not case: return
        
        # 1. Semantic Validation
        is_logical = ai_service.semantic_validator(plate_text, vehicle_type)
        
        step = 10 # Post-processing step
        if not is_logical:
            self._log_audit(db, case_id, step, "SEMANTIC_MISMATCH", 
                           f"Warning: Forensic Auditor detected a mismatch. Plate '{plate_text}' is unlikely for vehicle type '{vehicle_type}'.")
            case.status = CaseStatus.FLAGGED_UNCERTAIN
        else:
            self._log_audit(db, case_id, step, "AUDIT_VERIFIED", 
                           f"Forensic verification successful. Plate and vehicle signatures are consistent.")
            case.status = CaseStatus.SOLVED
            
        case.final_plate = plate_text
        case.vehicle_class = vehicle_type
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
        logger.info(f"[AUDIT #{case_id}] {action}: {reasoning}")

auditor_agent = AuditorAgent()
