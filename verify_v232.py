import sys
import os
import json
from sqlalchemy.orm import Session

# Add local app to path
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.models.models import Video

def verify_analytics():
    print(">>> Verifying v2.3.2 Analytics Storage...")
    db = SessionLocal()
    try:
        # Check if any video has analytics_data
        videos = db.query(Video).filter(Video.analytics_data != None).all()
        print(f"Videos with analytics: {len(videos)}")
        
        for v in videos:
            data = json.loads(v.analytics_data)
            print(f"Video {v.id} Analytics: {data.get('total_vehicles_seen')} unique, peak density {data.get('peak_vehicle_density')}")
            assert "frame_series" in data, "Missing frame_series in analytics"
            assert "total_vehicles_seen" in data, "Missing total_vehicles_seen"
            
        print(">>> Analytics Verification PASSED.")
    except Exception as e:
        print(f">>> Analytics Verification FAILED: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_analytics()
