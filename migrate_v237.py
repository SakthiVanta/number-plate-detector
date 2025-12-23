import sqlite3
import os

db_path = "vehicle_detect.db"

def migrate():
    print(f"Checking database at {db_path}...")
    if not os.path.exists(db_path):
        print("Database not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Add extra_data to processing_logs
        print("Adding extra_data to processing_logs...")
        cursor.execute("ALTER TABLE processing_logs ADD COLUMN extra_data TEXT")
        print("Successfully added extra_data column.")
    except sqlite3.OperationalError:
        print("Column extra_data already exists or table doesn't exist.")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
