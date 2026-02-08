import sqlite3
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "vehicle_detect.db"

def run_migration():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    detections_cols = [
        ("fcf_score", "REAL"),
        ("visual_rank", "REAL"),
        ("stability_score", "REAL"),
        ("audit_required", "BOOLEAN"),
        ("raw_inference_log", "TEXT"),
        ("forensic_insight", "TEXT"),
        ("partial_confidence", "TEXT")
    ]
    
    cases_cols = [
        ("forensic_insight", "TEXT")
    ]
    
    logger.info(f"Checking schema for {DB_PATH}...")
    
    # Update vehicle_detections
    for col_name, col_type in detections_cols:
        try:
            cursor.execute(f"SELECT {col_name} FROM vehicle_detections LIMIT 1")
        except sqlite3.OperationalError:
            logger.info(f"Adding missing column to vehicle_detections: {col_name}")
            try:
                cursor.execute(f"ALTER TABLE vehicle_detections ADD COLUMN {col_name} {col_type}")
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to add {col_name} to vehicle_detections: {e}")
                
    # Update vehicle_cases
    for col_name, col_type in cases_cols:
        try:
            cursor.execute(f"SELECT {col_name} FROM vehicle_cases LIMIT 1")
        except sqlite3.OperationalError:
            logger.info(f"Adding missing column to vehicle_cases: {col_name}")
            try:
                cursor.execute(f"ALTER TABLE vehicle_cases ADD COLUMN {col_name} {col_type}")
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to add {col_name} to vehicle_cases: {e}")

    conn.close()
    logger.info("Migration check complete.")

if __name__ == "__main__":
    run_migration()
