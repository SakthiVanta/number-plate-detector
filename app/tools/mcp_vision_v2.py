import cv2
import numpy as np
import torch
from ultralytics import YOLO
from collections import Counter
from app.core.config import settings

# Attempt to import RealESRGAN, provide fallback if missing
try:
    from realesrgan import RealESRGANer
    from basicsr.archs.rrdbnet_arch import RRDBNet
    HAS_ESRGAN = True
except ImportError:
    HAS_ESRGAN = False
    print("Warning: RealESRGAN/BasicSR not installed. Super-Resolution will be skipped.")

def tool(func):
    """Simple decorator to mark functions as tools."""
    func.is_tool = True
    return func

class VisionToolV2:
    """
    v5.1 Forensic Hardened Vision Tool.
    Includes:
    - YOLOv11 Support (Detection & Segmentation)
    - Homography (Perspective Correction)
    - Real-ESRGAN (Super-Resolution)
    - Temporal Consensus Logic
    """
    def __init__(self):
        # Load the newly requested YOLOv11 model (auto-downloads if not found)
        self.model_path = settings.YOLO_MODEL_PATH

        print(f"Loading YOLOv11 Model: {self.model_path}")
        self.model = YOLO(self.model_path)
        
        # Initialize Real-ESRGAN if available
        self.upsampler = None
        if HAS_ESRGAN:
            # Standard RealESRGAN_x4plus model
            model_url = 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth'
            model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
            self.upsampler = RealESRGANer(
                scale=4,
                model_path=None, # Will auto-download if handled by library or manual path
                model=model,
                tile=0,
                tile_pad=10,
                pre_pad=0,
                half=True, # Interface with GPU if avail
                gpu_id=0 if torch.cuda.is_available() else None
            )

    @tool
    def detect_vehicles(self, frame, conf=None):
        """
        Uses YOLOv11 to detect vehicles.
        """
        threshold = conf if conf else settings.DETECTION_THRESHOLD
        results = self.model.track(
            frame, 
            persist=True, 
            classes=[2, 3, 5, 7], # Car, Motorcycle, Bus, Truck
            conf=threshold,
            verbose=False
        )
        
        detections = []
        if results and results[0].boxes:
            for box in results[0].boxes:
                det = {
                    "bbox": box.xyxy[0].tolist(),
                    "conf": float(box.conf[0]),
                    "class_id": int(box.cls[0]),
                    "track_id": int(box.id[0]) if box.id is not None else -1
                }
                detections.append(det)
        return detections

    @tool
    def enhance_plate_crop(self, crop_img):
        """
        Applies Real-ESRGAN Super-Resolution to a license plate crop.
        Returns: Upscaled image (numpy array)
        """
        if not HAS_ESRGAN or self.upsampler is None:
            return crop_img # Pass-through if not enabled

        try:
            output, _ = self.upsampler.enhance(crop_img, outscale=4)
            return output
        except Exception as e:
            print(f"SR Error: {e}")
            return crop_img

    @tool
    def apply_homography(self, plate_crop):
        """
        Detects plate corners and warps perspective to a flat rectangle.
        Simplified implementation assuming contours can be found.
        """
        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5,5), 0)
        edges = cv2.Canny(blur, 50, 150)
        
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
        
        screen_cnt = None
        for c in contours:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4:
                screen_cnt = approx
                break
        
        if screen_cnt is None:
            return plate_crop # No 4-point contour found
            
        # Warp Perspective
        pts = screen_cnt.reshape(4, 2)
        rect = self._order_points(pts)
        (tl, tr, br, bl) = rect
        
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]], dtype = "float32")
            
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(plate_crop, M, (maxWidth, maxHeight))
        return warped

    def _order_points(self, pts):
        rect = np.zeros((4, 2), dtype = "float32")
        s = pts.sum(axis = 1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis = 1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect
        
    @tool
    def calculate_visual_rank(self, image):
        """
        v5.5: Calculates Visual Rank (Vr) based on Sharpness and Contrast.
        Returns float 0.0 - 1.0
        """
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            # Sharpness: Laplacian Variance (Higher is sharper)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            # Normalize Sharpness (Heuristic: >500 is very sharp)
            norm_sharpness = min(sharpness / 500.0, 1.0)
            
            # Contrast: RMS Contrast (Standard Deviation of pixel intensity)
            contrast = gray.std()
            # Normalize Contrast (Heuristic: >50 is good contrast)
            norm_contrast = min(contrast / 50.0, 1.0)
            
            # Weighted Vr Score
            vr = (norm_sharpness * 0.5) + (norm_contrast * 0.5)
            return round(vr, 2)
        except Exception as e:
            return 0.5 # Default medium confidence

    @tool
    def calculate_fcf(self, stability_score: float, ocr_conf: float, visual_rank: float) -> float:
        """
        v5.5: Forensic Confidence Formula
        FCF = (S * 0.4) + (Oc * 0.4) + (Vr * 0.2)
        """
        fcf = (stability_score * 0.4) + (ocr_conf * 0.4) + (visual_rank * 0.2)
        return round(fcf, 2)

    @tool
    def get_consensus_text(self, text_list):
        """
        v5.5: Returns (Consensus Text, Stability Score).
        Stability Score = Count of Majority / Total Votes
        """
        if not text_list:
            return None, 0.0
        
        counts = Counter(text_list)
        most_common_tuple = counts.most_common(1)[0]
        text = most_common_tuple[0]
        count = most_common_tuple[1]
        
        stability_score = count / len(text_list)
        return text, stability_score

vision_tool = VisionToolV2()
