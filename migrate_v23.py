import sqlite3
import os
import sys

# Add current directory to path to reach app
sys.path.append(os.getcwd())

def migrate():
    db_path = "vehicle_detect.db"
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(">>> Starting Migration to v2.3 (Agentic)...")

    # 1. Create detection_batches table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detection_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER,
                collage_path TEXT NOT NULL,
                raw_json TEXT,
                cost_estimate REAL DEFAULT 0.0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos (id)
            )
        """)
        print("Created detection_batches table.")
    except Exception as e:
        print(f"Error creating detection_batches table: {e}")

    # 2. Update vehicle_detections table
    columns_to_add = [
        ("batch_id", "INTEGER REFERENCES detection_batches(id)"),
        ("is_validated", "BOOLEAN DEFAULT 0"),
        ("make_model", "TEXT"),
        ("color_conf", "REAL")
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE vehicle_detections ADD COLUMN {col_name} {col_type}")
            print(f"Added column {col_name} to vehicle_detections.")
        except sqlite3.OperationalError:
            print(f"Column {col_name} already exists in vehicle_detections.")
        except Exception as e:
            print(f"Error adding column {col_name}: {e}")

    conn.commit()
    conn.close()
    print(">>> Migration to v2.3 COMPLETE.")

if __name__ == "__main__":
    migrate()
