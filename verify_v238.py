import sys
import os
import cv2
import numpy as np
import json
from sqlalchemy.orm import Session

# Add local app to path
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.models.models import Video, ProcessingLog, DetectionBatch
from app.services.video_service import video_service
from app.services.ai_service import create_ai_collage

def test_v238_flow():
    print(">>> Testing v2.3.8 Flow & Rich Logs...")
    db = SessionLocal()
    try:
        # Create a dummy video if none exists
        video = db.query(Video).first()
        if not video:
            video = Video(filename="test.mp4", filepath="test.mp4", status="pending", owner_id=1)
            db.add(video)
            db.commit()
            db.refresh(video)

        # 1. Test Grid Collage
        print("- Testing 3x3 Grid Generation...")
        dummy_crops = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(5)]
        dummy_ids = [101, 102, 103, 104, 105]
        collage = create_ai_collage(dummy_crops, dummy_ids)
        
        # Grid is 3x3, so total width should be 3 * 400 = 1200
        # Height should be 3 * 400 = 1200
        print(f"Collage Shape: {collage.shape}")
        if collage.shape == (1200, 1200, 3):
            print("  SUCCESS: 3x3 Grid Correct.")
        else:
            print(f"  FAILED: Expected (1200, 1200, 3), got {collage.shape}")

        # 2. Test Log metadata for BATCH
        print("- Simulating Batch Processing...")
        track_ids = [101, 102, 103]
        track_data = {
            101: {'vehicle_crop': dummy_crops[0], 'first_seen': 0.0},
            102: {'vehicle_crop': dummy_crops[1], 'first_seen': 1.0},
            103: {'vehicle_crop': dummy_crops[2], 'first_seen': 2.0}
        }
        all_detections = []
        
        # We need to mock ai_service.rechecker.recheck_batch if we don't want to call API
        # but let's just check the log part.
        video_service._process_batch(db, video, track_ids, track_data, all_detections)
        
        # Check high-level log
        log = db.query(ProcessingLog).filter(
            ProcessingLog.video_id == video.id,
            ProcessingLog.event_type == "BATCH"
        ).order_by(ProcessingLog.created_at.desc()).first()
        
        if log and log.extra_data:
            print(f"  SUCCESS: BATCH log has extra_data: {log.extra_data}")
        else:
            print("  FAILED: BATCH log missing extra_data")

        # Check AI_RECHECK log
        log_ai = db.query(ProcessingLog).filter(
            ProcessingLog.video_id == video.id,
            ProcessingLog.event_type == "AI_RECHECK"
        ).order_by(ProcessingLog.created_at.desc()).first()
        
        if log_ai and log_ai.extra_data:
            print(f"  SUCCESS: AI_RECHECK log has extra_data (JSON)")
        else:
            print("  FAILED: AI_RECHECK log missing extra_data")

        print(">>> v2.3.8 Verification COMPLETE.")
    except Exception as e:
        print(f">>> Verification FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_v238_flow()
