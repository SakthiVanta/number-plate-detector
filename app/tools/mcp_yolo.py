import json
import torch
from ultralytics import YOLO
from app.core.config import settings

def tool(func):
    """Simple decorator to mark functions as tools."""
    func.is_tool = True
    return func

class YOLOTool:
    """
    MCP-Compliant Tool for Vehicle Detection.
    Accepts: frame (np.ndarray) or image_path
    Returns: JSON structure of detections
    """
    def __init__(self):
        self.model = YOLO(settings.YOLO_MODEL_PATH)

    @tool
    def detect_vehicles(self, frame):
        """
        Detects vehicles in a frame.
        Classes: [2 (car), 3 (motorcycle), 5 (bus), 7 (truck)]
        Returns: List of detection objects.
        """
        results = self.model.track(
            frame, 
            persist=True, 
            classes=[2, 3, 5, 7], 
            conf=settings.DETECTION_THRESHOLD,
            verbose=False
        )
        
        detections = []
        if results and results[0].boxes:
            for box in results[0].boxes:
                det = {
                    "bbox": box.xyxy[0].tolist(),
                    "conf": float(box.conf[0]),
                    "class_id": int(box.cls[0]),
                    "track_id": int(box.id[0]) if box.id is not None else None
                }
                detections.append(det)
        
        return detections

yolo_tool = YOLOTool()
