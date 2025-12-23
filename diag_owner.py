from app.db.session import SessionLocal
from app.models.models import Video, VehicleDetection, User

db = SessionLocal()
try:
    v1 = db.query(Video).filter(Video.id == 1).first()
    if v1:
        print(f"VIDEO 1: owner_id={v1.owner_id}, status={v1.status}")
    else:
        print("VIDEO 1 NOT FOUND")

    u1 = db.query(User).filter(User.id == 1).first()
    if u1:
        print(f"USER 1: id={u1.id}, email={u1.email}")
    else:
        print("USER 1 NOT FOUND")

    det_count = db.query(VehicleDetection).filter(VehicleDetection.video_id == 1).count()
    print(f"DETECTIONS FOR VIDEO 1: {det_count}")

    # Check for any deletions or odd states
    all_videos = db.query(Video).all()
    print(f"TOTAL VIDEOS: {len(all_videos)}")
    for v in all_videos:
        print(f"  ID:{v.id} Owner:{v.owner_id} Status:{v.status} Filename:{v.filename}")

finally:
    db.close()
