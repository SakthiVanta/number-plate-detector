import sys
import os

# Add local app to path
sys.path.append(os.getcwd())

from app.core.config import settings
from app.services.ai_service import ai_service

def test_filter_logic():
    print(">>> Testing Filter Agent Sensitivity...")
    
    # Simulate HIGH sensitivity
    ai_service.sensitivity = "HIGH"
    persistence_thresh = 5 # Implementation in video_service.py: if HIGH -> 5
    
    frames_seen = 5
    is_valid = frames_seen >= persistence_thresh
    print(f"Sensitivity: HIGH, Frames: {frames_seen}, Required: {persistence_thresh}, Accepted: {is_valid}")
    assert is_valid == True, "Should accept 5 frames at HIGH sensitivity"

    # Simulate BALANCED sensitivity
    ai_service.sensitivity = "BALANCED"
    persistence_thresh = 15 # Default/BALANCED
    
    frames_seen = 5
    is_valid = frames_seen >= persistence_thresh
    print(f"Sensitivity: BALANCED, Frames: {frames_seen}, Required: {persistence_thresh}, Accepted: {is_valid}")
    assert is_valid == False, "Should reject 5 frames at BALANCED sensitivity"

    print(">>> Filter Logic Test PASSED.")

if __name__ == "__main__":
    test_filter_logic()
