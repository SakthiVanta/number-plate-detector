from app.db.session import SessionLocal
from app.models.models import Video, VehicleDetection, User
from sqlalchemy.orm import joinedload

db = SessionLocal()
try:
    current_user_id = 1
    # Mocking list_detections logic
    skip = 0
    limit = 10
    
    owned_video_ids = [v[0] for v in db.query(Video.id).filter(Video.owner_id == current_user_id).all()]
    print(f"OWNED VIDEO IDs: {owned_video_ids}")
    
    query = db.query(VehicleDetection).filter(VehicleDetection.video_id.in_(owned_video_ids))
    
    print(f"TOTAL BEFORE FILTERS: {query.count()}")
    
    # Filter by nothing (generic call)
    total = query.count()
    items = query.options(joinedload(VehicleDetection.batch)).order_by(VehicleDetection.created_at.desc()).offset(skip).limit(limit).all()
    
    print(f"API RESULT: total={total}, items_count={len(items)}")
    for item in items:
        print(f"  ID:{item.id} Plate:{item.plate_number}")

finally:
    db.close()
