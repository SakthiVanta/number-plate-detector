import sqlite3
import os

DB_PATH = "alpr.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found. Skipping migration.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # vehicle_detections v5.5 columns
    columns = [
        ("fcf_score", "FLOAT"),
        ("visual_rank", "FLOAT"),
        ("stability_score", "FLOAT")
    ]

    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE vehicle_detections ADD COLUMN {col_name} {col_type}")
            print(f"Added column {col_name} to vehicle_detections")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col_name} already exists in vehicle_detections")
            else:
                print(f"Error adding {col_name}: {e}")

    conn.commit()
    conn.close()
    print("v5.5 Migration (Formula Layer columns) complete.")

if __name__ == "__main__":
    migrate()
