import sys
import os
import json
from sqlalchemy.orm import Session

# Add local app to path
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.models.models import Video, ProcessingLog, VehicleDetection, RecheckStatus

def verify_robustness():
    print(">>> Verifying v2.3.7 Robustness & Specs...")
    db = SessionLocal()
    try:
        # 1. Check Stats Logic
        from app.api.system import get_dashboard_stats
        # We can't easily call FastAPI endpoint directly here without a test client, 
        # but we can check the DB contents.
        
        # 2. Verify Log extra_data
        logs = db.query(ProcessingLog).filter(ProcessingLog.extra_data != None).all()
        print(f"Logs with rich data: {len(logs)}")
        for l in logs:
            print(f"Log ID {l.id} [{l.event_type}]: {l.message}")
            if l.event_type == 'AI_RECHECK':
                data = json.loads(l.extra_data)
                print(f"  Sample Analysis Data: {len(data)} items")
        
        # 3. Verify Fallback Detections
        recovered = db.query(VehicleDetection).filter(VehicleDetection.vehicle_info == "RECOVERED FROM LOCAL").all()
        print(f"Recovered detections: {len(recovered)}")
        for r in recovered:
            print(f"  Recovered Track {r.track_id}: {r.plate_number}")

        print(">>> Robustness Verification COMPLETE.")
    except Exception as e:
        print(f">>> Robustness Verification FAILED: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_robustness()
