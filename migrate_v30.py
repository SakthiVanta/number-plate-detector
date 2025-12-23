from sqlalchemy import create_engine, text
import os

# Database connection URL
if os.path.exists("vehicle_detect.db"):
    DB_URL = "sqlite:///vehicle_detect.db"
    engine = create_engine(DB_URL)

    with engine.connect() as conn:
        print(">>> Adding v3.0 Agentic Integrity columns...")
        
        # 1. visual_embedding
        try:
            conn.execute(text("ALTER TABLE vehicle_detections ADD COLUMN visual_embedding TEXT"))
            print("  - Added visual_embedding")
        except Exception as e: print(f"  - visual_embedding exists or error: {e}")

        # 2. blur_score
        try:
            conn.execute(text("ALTER TABLE vehicle_detections ADD COLUMN blur_score FLOAT"))
            print("  - Added blur_score")
        except Exception as e: print(f"  - blur_score exists or error: {e}")

        # 3. ocr_source
        try:
            conn.execute(text("ALTER TABLE vehicle_detections ADD COLUMN ocr_source VARCHAR DEFAULT 'LOCAL'"))
            print("  - Added ocr_source")
        except Exception as e: print(f"  - ocr_source exists or error: {e}")

        # 4. best_frame_timestamp
        try:
            conn.execute(text("ALTER TABLE vehicle_detections ADD COLUMN best_frame_timestamp FLOAT"))
            print("  - Added best_frame_timestamp")
        except Exception as e: print(f"  - best_frame_timestamp exists or error: {e}")

        # 5. raw_inference_log
        try:
            conn.execute(text("ALTER TABLE vehicle_detections ADD COLUMN raw_inference_log TEXT"))
            print("  - Added raw_inference_log")
        except Exception as e: print(f"  - raw_inference_log exists or error: {e}")

        conn.commit()
    print(">>> v3.0 Migration Complete.")
else:
    print("Database not found.")
