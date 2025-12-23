import numpy as np
from app.services.ai_service import ai_service

def tool(func):
    """Simple decorator for tool methods."""
    func.is_tool = True
    return func

class OCRTool:
    """
    MCP-Compliant Tool for Hybrid OCR.
    Wraps local PaddleOCR and cloud Gemini Vision.
    """
    
    @tool
    def read_plate(self, plate_crop: np.ndarray, video_id: int = -1):
        """
        Performs hybrid recognition (Local + Cloud).
        Returns: (text, confidence, vehicle_info, status)
        """
        # We reuse the existing recognize_plate which already has rechecker logic
        return ai_service.recognize_plate(plate_crop, video_id=video_id)

    @tool
    def arbitrate_results(self, local_text: str, cloud_text: str, v_type: str):
        """
        Arbitrates between multiple OCR candidates using Jury logic.
        """
        return ai_service.ocr_jury_arbitrate(local_text, cloud_text, v_type)

ocr_tool = OCRTool()
