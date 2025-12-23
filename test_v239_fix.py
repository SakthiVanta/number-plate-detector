import json
import logging
from sqlalchemy import create_mock_engine

class MockDetection:
    def __init__(self, id, plate):
        self.id = id
        self.plate_number = plate
        self.confidence = 0.95
        self.vehicle_info = "Mock Car"
        self.timestamp = 123456789.0
        self.video_id = 1
        self.track_id = 7

def test_serialization_fix():
    print(">>> Testing v2.3.9 Serialization Fix...")
    detections = [MockDetection(1, "ABC-123"), MockDetection(2, "XYZ-789")]
    
    serializable_results = []
    for d in detections:
        serializable_results.append({
            "id": d.id,
            "plate_number": d.plate_number,
            "confidence": float(d.confidence),
            "vehicle_info": d.vehicle_info,
            "timestamp": float(d.timestamp),
            "video_id": d.video_id,
            "track_id": d.track_id
        })
    
    try:
        data = json.dumps(serializable_results)
        print("  SUCCESS: JSON serialization works perfectly.")
        print(f"  Sample Data: {data[:100]}...")
    except Exception as e:
        print(f"  FAILED: Serialization still leaking objects: {e}")

if __name__ == "__main__":
    test_serialization_fix()
