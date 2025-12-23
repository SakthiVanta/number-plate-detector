from sqlalchemy import create_engine, text
import os

# Database connection URL
if os.path.exists("vehicle_detect.db"):
    DB_URL = "sqlite:///vehicle_detect.db"
    engine = create_engine(DB_URL)

    with engine.connect() as conn:
        print(">>> Adding v2.5 Safety & Forensic columns...")
        try:
            conn.execute(text("ALTER TABLE vehicle_detections ADD COLUMN vehicle_type VARCHAR DEFAULT 'UNKNOWN'"))
            print("  - Added vehicle_type")
        except Exception as e: print(f"  - vehicle_type exists or error: {e}")

        try:
            conn.execute(text("ALTER TABLE vehicle_detections ADD COLUMN helmet_status VARCHAR DEFAULT 'N/A'"))
            print("  - Added helmet_status")
        except Exception as e: print(f"  - helmet_status exists or error: {e}")

        try:
            conn.execute(text("ALTER TABLE vehicle_detections ADD COLUMN passenger_count INTEGER DEFAULT 0"))
            print("  - Added passenger_count")
        except Exception as e: print(f"  - passenger_count exists or error: {e}")

        conn.commit()
    print(">>> Migration Complete.")
else:
    print("Database not found.")
