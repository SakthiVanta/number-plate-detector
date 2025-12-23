import sqlite3
import os

def migrate():
    db_path = "vehicle_detect.db"
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(">>> Starting Migration to v2.3.2 (Analytics & De-duplication)...")

    # 1. Update videos table
    try:
        cursor.execute("ALTER TABLE videos ADD COLUMN analytics_data TEXT")
        print("Added column analytics_data to videos.")
    except sqlite3.OperationalError:
        print("Column analytics_data already exists in videos.")
    except Exception as e:
        print(f"Error adding column analytics_data: {e}")

    # 2. Update vehicle_detections table
    try:
        cursor.execute("ALTER TABLE vehicle_detections ADD COLUMN best_local_plate TEXT")
        print("Added column best_local_plate to vehicle_detections.")
    except sqlite3.OperationalError:
        print("Column best_local_plate already exists in vehicle_detections.")
    except Exception as e:
        print(f"Error adding column best_local_plate: {e}")

    conn.commit()
    conn.close()
    print(">>> Migration to v2.3.2 COMPLETE.")

if __name__ == "__main__":
    migrate()
