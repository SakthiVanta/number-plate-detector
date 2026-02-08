import sqlite3
from app.core.config import settings

def migrate_v51():
    """
    Directly adds v5.1 columns to SQLite database.
    - vehicle_detections: chain_of_custody_hash
    - detection_batches: collage_hash
    - vehicle_cases: is_stalker
    - agent_logs: xai_reasoning
    """
    
    # Extract path from sqlite:///./sql_app.db
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    if not db_path:
        print("Using default db path")
        db_path = "sql_app.db"
        
    print(f"Migrating database at: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. VehicleDetection
    try:
        cursor.execute("ALTER TABLE vehicle_detections ADD COLUMN chain_of_custody_hash VARCHAR")
        print("Added chain_of_custody_hash to vehicle_detections")
    except sqlite3.OperationalError:
        print("chain_of_custody_hash already exists")

    # 2. DetectionBatch
    try:
        cursor.execute("ALTER TABLE detection_batches ADD COLUMN collage_hash VARCHAR")
        print("Added collage_hash to detection_batches")
    except sqlite3.OperationalError:
        print("collage_hash already exists")

    # 3. VehicleCase
    try:
        cursor.execute("ALTER TABLE vehicle_cases ADD COLUMN is_stalker BOOLEAN DEFAULT 0")
        print("Added is_stalker to vehicle_cases")
    except sqlite3.OperationalError:
        print("is_stalker already exists")

    # 4. AgentLog
    try:
        cursor.execute("ALTER TABLE agent_logs ADD COLUMN xai_reasoning VARCHAR")
        print("Added xai_reasoning to agent_logs")
    except sqlite3.OperationalError:
        print("xai_reasoning already exists")

    conn.commit()
    conn.close()
    print("v5.1 Migration Complete.")

if __name__ == "__main__":
    migrate_v51()
