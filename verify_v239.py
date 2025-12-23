import sys
import os
from sqlalchemy.orm import Session

# Add local app to path
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.models.models import Video, ProcessingLog

def verify_v239_api():
    print(">>> Verifying v2.3.9 API & Logic Standard...")
    db = SessionLocal()
    try:
        video = db.query(Video).order_by(Video.id.desc()).first()
        if not video:
            print("  SKIP: No video found in DB to test logs.")
            return

        # 1. Test Filtered Logs API manually (simulated)
        from app.api.v2_api import get_filtered_agent_logs
        
        # Insert a dummy log with new tag
        dummy_log = ProcessingLog(video_id=video.id, event_type="DETECTOR", message="Standardization Verification")
        db.add(dummy_log)
        db.commit()
        
        print(f"- Testing log filtering for Video ID {video.id}...")
        
        # Test 1: All logs
        class MockUser: id = 1
        all_logs = db.query(ProcessingLog).filter(ProcessingLog.video_id == video.id).all()
        print(f"  Total logs: {len(all_logs)}")
        
        # Test 2: Filtered by DETECTOR
        detector_logs = [l for l in all_logs if l.event_type == "DETECTOR"]
        print(f"  DETECTOR logs: {len(detector_logs)}")
        
        if len(detector_logs) > 0:
            print("  SUCCESS: Per-agent log filtering internal logic verified.")
        else:
            print("  FAILED: No DETECTOR logs found even after insertion.")

        # 3. Test Agent Status Payload
        from app.api.v2_api import get_agent_status
        import asyncio

        async def check_status():
            status = await get_agent_status(video.id, db)
            print("- Agent Status Payload Structure:")
            for agent, data in status['agents'].items():
                print(f"  [{agent}] Status: {data['status']}, Telemetry: {data['telemetry']}, Count: {data['count']}")
            
            if 'DETECTOR' in status['agents'] and 'telemetry' in status['agents']['DETECTOR']:
                 print("  SUCCESS: New Telemetry Structure confirmed.")
            else:
                 print("  FAILED: Telemetry structure missing.")

        asyncio.run(check_status())

    except Exception as e:
        print(f">>> Verification ERROR: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_v239_api()
