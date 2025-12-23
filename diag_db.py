from app.db.session import SessionLocal
from app.models.models import Video, VehicleDetection, User, DetectionBatch

db = SessionLocal()
try:
    print("--- USERS ---")
    for u in db.query(User).all():
        print(f"ID: {u.id}, Email: {u.email}")

    print("\n--- VIDEOS ---")
    for v in db.query(Video).all():
        print(f"ID: {v.id}, Filename: {v.filename}, OwnerID: {v.owner_id}, Status: {v.status}")
        # check parent/child
        if v.is_chunk:
            print(f"  > CHUNK of Parent ID: {v.parent_video_id}")

    print("\n--- DETECTIONS (Detailed for Video 1) ---")
    dets = db.query(VehicleDetection).filter(VehicleDetection.video_id == 1).all()
    print(f"Found {len(dets)} detections for Video 1")
    for d in dets[:5]:
        print(f"  ID: {d.id}, Plate: {d.plate_number}, Batch: {d.batch_id}")

    print("\n--- BATCHES ---")
    for b in db.query(DetectionBatch).all():
        print(f"ID: {b.id}, VideoID: {b.video_id}, Path: {b.collage_path}")

    total_det = db.query(VehicleDetection).count()
    print(f"\nTOTAL DETECTIONS IN DB: {total_det}")

finally:
    db.close()
