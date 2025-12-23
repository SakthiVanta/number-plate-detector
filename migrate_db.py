import sqlite3
import os

DB_PATH = "vehicle_detect.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found. Nothing to migrate.")
        return

    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Add columns to vehicle_detections
    cols_to_add = [
        ("raw_ocr_text", "TEXT"),
        ("recheck_status", "VARCHAR(20)")
    ]

    for col_name, col_type in cols_to_add:
        try:
            print(f"Adding column '{col_name}' to 'vehicle_detections'...")
            cursor.execute(f"ALTER TABLE vehicle_detections ADD COLUMN {col_name} {col_type}")
            print(f"Successfully added '{col_name}'.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"Column '{col_name}' already exists.")
            else:
                print(f"Error adding column '{col_name}': {e}")

    # 2. Create processing_logs table
    try:
        print("Creating table 'processing_logs'...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processing_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                frame_index INTEGER,
                timestamp FLOAT,
                event_type VARCHAR(50) NOT NULL,
                message TEXT,
                is_error BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos(id)
            )
        ''')
        print("Successfully created 'processing_logs' table.")
    except Exception as e:
        print(f"Error creating 'processing_logs' table: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
