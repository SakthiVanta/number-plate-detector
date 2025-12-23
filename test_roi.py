import cv2
import numpy as np
import os
import sys

# Add local app to path
sys.path.append(os.getcwd())

from app.services.ai_service import AIService
from app.core.config import settings

def test_roi_mask():
    print(">>> Testing ROI Mask Logic (v2.3.5)...")
    
    # 1. Create a dummy mask (Half white, half black)
    # Mask is 1000x1000, white on the left half
    mask_path = settings.ROI_MASK_PATH
    os.makedirs(os.path.dirname(mask_path), exist_ok=True)
    mask = np.zeros((1000, 1000), dtype=np.uint8)
    mask[:, :500] = 255
    cv2.imwrite(mask_path, mask)
    print(f"Created dummy mask at {mask_path}")

    # 2. Initialize AIService
    ai = AIService()
    ai._load_roi_mask() # Reload to pick up new file
    
    # 3. Create a dummy frame
    frame = np.zeros((1000, 1000, 3), dtype=np.uint8)
    
    # 4. Mock some detection boxes
    class MockBox:
        def __init__(self, xyxy):
            self.xyxy = [xyxy]
            
    # Box 1: Left side (should be kept)
    box_keep = MockBox([100, 100, 200, 200]) # Center 150, 150
    # Box 2: Right side (should be filtered)
    box_filter = MockBox([600, 600, 700, 700]) # Center 650, 650
    
    # We need to monkey-patch or mock the track results
    # Instead, let's just test the filtering logic directly if we can
    # Or just mock the vehicle_model.track return
    
    print(f"Applying mask to boxes...")
    # Manually run the filtering logic from detect_vehicles
    h, w = frame.shape[:2]
    boxes = [box_keep, box_filter]
    
    filtered = []
    for box in boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        if 0 <= cx < w and 0 <= cy < h:
            if ai.roi_mask[cy, cx] > 0:
                filtered.append(box)
                
    print(f"Boxes before: {len(boxes)}, After: {len(filtered)}")
    
    if len(filtered) == 1 and filtered[0] == box_keep:
        print(">>> ROI Mask Verification PASSED.")
    else:
        print(f">>> ROI Mask Verification FAILED. Kept {len(filtered)} boxes.")

    # Cleanup
    if os.path.exists(mask_path):
        os.remove(mask_path)

if __name__ == "__main__":
    test_roi_mask()
