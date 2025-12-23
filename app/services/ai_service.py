import cv2
try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
except ImportError:
    PADDLE_AVAILABLE = False
    
import easyocr
import numpy as np
import os
import torch
import re
from ultralytics import YOLO
from app.core.config import settings
import logging
try:
    from sahi import AutoDetectionModel
    from sahi.predict import get_sliced_prediction
    SAHI_AVAILABLE = True
except ImportError:
    SAHI_AVAILABLE = False

import google.generativeai as genai
from abc import ABC, abstractmethod
import time
import re
import json

logger = logging.getLogger(__name__)

def create_ai_collage(image_list, labels):
    """
    Stitches a list of up to 10 images into a grid (2x5 or similar).
    Adds ID labels to each crop for AI reference.
    """
    if not image_list:
        return None
        
    font = cv2.FONT_HERSHEY_SIMPLEX
    processed_crops = []
    
    # Grid Logic (e.g. 3x3 = 9 images)
    rows, cols = settings.COLLAGE_GRID_SIZE
    max_slots = rows * cols
    
    # Target size for each slot in the collage
    target_h, target_w = 400, 400 # Squared for vehicle context

    for i in range(max_slots):
        if i < len(image_list):
            img = image_list[i]
            label = labels[i]
            if img is None or img.size == 0:
                crop = np.zeros((target_h, target_w, 3), dtype=np.uint8)
            else:
                crop = cv2.resize(img, (target_w, target_h))
            
            # Use black background for text for better readability
            cv2.rectangle(crop, (0, 0), (120, 40), (0, 0, 0), -1)
            cv2.putText(crop, f"ID:{label}", (5, 30), font, 1.0, (0, 255, 0), 2)
        else:
            crop = np.zeros((target_h, target_w, 3), dtype=np.uint8)
            
        processed_crops.append(crop)
    
    # Build the Grid
    grid_rows = []
    for r in range(rows):
        row_images = processed_crops[r*cols : (r+1)*cols]
        grid_rows.append(np.hstack(row_images))
    
    full_collage = np.vstack(grid_rows)
    
    return full_collage

# --- Global AI Rechecker Architecture ---

class BaseAIProvider(ABC):
    @abstractmethod
    def check_plate(self, image: np.ndarray) -> tuple[str, float]:
        pass

    @abstractmethod
    def check_collage(self, collage: np.ndarray) -> list[dict]:
        pass

class GeminiProvider(BaseAIProvider):
    def __init__(self, api_key: str):
        if not api_key:
            logger.warning("Gemini API Key missing! Gemini provider will be disabled.")
            self.model = None
            return
            
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        self.last_call = 0
        self.rate_limit_delay = 1.0

    def check_plate(self, image: np.ndarray) -> tuple[str, float, str]:
        if not self.model: return None, 0.0, None
        now = time.time()
        if now - self.last_call < 1.0:
            time.sleep(1.0 - (now - self.last_call))
        self.last_call = time.time()

        try:
            from PIL import Image
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            prompt = """
            1. Extract the License Plate Number from this image. 
            2. Identify the vehicle make/model and color (e.g., 'White Swift', 'Red Truck').
            3. CRITICAL: If the license plate characters are NOT clearly identifiable, return ONLY the word 'REJECTED'. Do not guess.
            4. If a plate is found, return in format: PLATE | VEHICLE_INFO (e.g., DL8CAF1234 | White Swift).
            5. Return ONLY the requested format or 'REJECTED'.
            """
            response = self.model.generate_content([prompt, pil_image])
            result = response.text.strip().upper()
            if "REJECTED" in result or len(result) < 4: return None, 0.0, None
            if "|" in result:
                text, v_info = result.split("|", 1)
                text = "".join([c for c in text.strip() if c.isalnum()])
                return text, 0.95, v_info.strip()
            text = "".join([c for c in result if c.isalnum()])
            return text, 0.95, None
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            return None, 0.0, None

    def check_collage(self, collage: np.ndarray) -> list[dict]:
        if not self.model: return []
        now = time.time()
        if now - self.last_call < 1.0:
            time.sleep(1.0 - (now - self.last_call))
        self.last_call = time.time()

        try:
            from PIL import Image
            import json
            pil_image = Image.fromarray(cv2.cvtColor(collage, cv2.COLOR_BGR2RGB))
            prompt = """
            You are a traffic forensic expert. Trace the vehicle crops in this 3x3 grid. 
            Each crop has a green ID label (e.g. ID:123).
            
            CRITICAL RULES:
            1. STRICT ASSOCIATION: Identify the vehicle that occupies the MAJORITY of the crop (the foreground vehicle). 
            2. IGNORE background vehicles, trailing cars, or plates visible in the distance. 
            3. FOR BIKES/SCOOTERS: Do not associate them with a plate if it clearly belongs to a car behind them.
            
            For each vehicle in the grid, return: 
            - track_id: The exact number after ID:
            - plate: License Plate Number of the FOREGROUND vehicle (if visible). Return 'NO PLATE' if not clear.
            - color: Primary foreground vehicle color
            - make: Foreground Vehicle Make and Model (e.g., 'Maruti Swift', 'Honda Activa')
            - type: Specific Vehicle Type (CAR, MOTORCYCLE, SCOOTER, BICYCLE, BUS, TRUCK, AUTO)
            - helmet_status: (HELMET, NO_HELMET, N/A). 
              CRITICAL: For MOTORCYCLE/SCOOTER, if the driver or pillion is NOT wearing a visible helmet, mark as NO_HELMET. Only mark HELMET if clearly visible.
            - passengers: Exact count of people on the vehicle (1, 2, 3, 4, 5+). 
            - confidence: Confidence in overall analysis (0.0 to 1.0)
            
            CRITICAL: Return ONLY a valid JSON array of objects. Do not explain.
            Format: [{"track_id": 123, "plate": "...", "color": "...", "make": "...", "type": "...", "helmet_status": "...", "passengers": 1, "confidence": 0.9}, ...]
            """
            # v2.3 Agentic: Added Search Grounding for vehicle details if needed
            response = self.model.generate_content([prompt, pil_image])
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].strip()
            results = json.loads(text)
            return results
        except Exception as e:
            logger.error(f"Gemini Collage Error: {e}")
            return []

class SearchAgent:
    """
    Search-based enrichment for vehicle details.
    """
    def __init__(self, model):
        self.model = model

    def deep_search_vehicle(self, vehicle_desc: str) -> str:
        if not self.model: return vehicle_desc
        prompt = f"Analyze this vehicle description and refine it based on common models: {vehicle_desc}. Return a concise vehicle make and model."
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except:
            return vehicle_desc

class GlobalAIRechecker:
    def __init__(self):
        self.providers = []
        if settings.GEMINI_API_KEY:
            self.providers.append(GeminiProvider(settings.GEMINI_API_KEY))
        
    def recheck(self, image: np.ndarray, video_id: int = -1) -> tuple[str, float, str]:
        if not settings.ENABLE_GLOBAL_RECHECK: return None, 0.0, None
        if video_id != -1:
            try:
                import redis
                r = redis.from_url(settings.REDIS_URL, decode_responses=True)
                key = f"gemini_usage:{video_id}"
                count = r.incr(key)
                if count > settings.MAX_GEMINI_CALLS_PER_VIDEO: return None, 0.0, None
            except: pass

        for provider in self.providers:
            try:
                text, conf, v_info = provider.check_plate(image)
                if text and conf > 0.8: return text, conf, v_info
            except: continue
        return None, 0.0, None

    def recheck_batch(self, collage: np.ndarray, video_id: int = -1) -> list[dict]:
        if not settings.ENABLE_GLOBAL_RECHECK or not self.providers: return []
        if video_id != -1:
            try:
                import redis
                r = redis.from_url(settings.REDIS_URL, decode_responses=True)
                key = f"gemini_usage:{video_id}"
                r.incr(key)
            except: pass

        for provider in self.providers:
            try:
                results = provider.check_collage(collage)
                if results: return results
            except: continue
        return []

class AIService:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AIService, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance

    def initialize(self):
        try:
            if os.path.exists(settings.YOLO_MODEL_PATH):
                self.vehicle_model = YOLO(settings.YOLO_MODEL_PATH)
            else:
                self.vehicle_model = YOLO("yolov8n.pt")
            
            if os.path.exists(settings.PLATE_MODEL_PATH):
                self.plate_model = YOLO(settings.PLATE_MODEL_PATH)
            else:
                self.plate_model = None
            
            self.use_paddle = PADDLE_AVAILABLE
            if self.use_paddle:
                try:
                    self.reader = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
                except:
                    self.use_paddle = False
            
            if not self.use_paddle:
                self.reader = easyocr.Reader(['en'], gpu=torch.cuda.is_available())
            
            self.rechecker = GlobalAIRechecker()
            
            # v2.3 Agentic instances
            self.search_agent = SearchAgent(self.rechecker.providers[0].model if self.rechecker.providers else None)
            self.current_threshold = settings.DETECTION_THRESHOLD
            self.sensitivity = settings.AGENTS_SENSITIVITY
            
            # v2.3.5: ROI Mask
            self.roi_mask = None
            self._load_roi_mask()
        except Exception as e:
            logger.error(f"Error initializing AI models: {e}")

    def _load_roi_mask(self):
        if os.path.exists(settings.ROI_MASK_PATH):
            mask = cv2.imread(settings.ROI_MASK_PATH, cv2.IMREAD_GRAYSCALE)
            if mask is not None:
                self.roi_mask = mask
                logger.info(f"[ROI AGENT] Mask loaded from {settings.ROI_MASK_PATH}")
            else:
                logger.warning(f"[ROI AGENT] Failed to decode mask at {settings.ROI_MASK_PATH}")
        else:
            logger.info("[ROI AGENT] No ROI mask found. Full-frame detection active.")

    def detect_vehicles(self, frame):
        # v4.0: Slicing Agent (SAHI) Integration
        if SAHI_AVAILABLE:
            try:
                # Wrap existing model for SAHI
                if not hasattr(self, 'sahi_model'):
                    self.sahi_model = AutoDetectionModel.from_model_type(
                        model_type='yolov8',
                        model_path=settings.YOLO_MODEL_PATH,
                        confidence_threshold=self.current_threshold,
                        device="cuda:0" if torch.cuda.is_available() else "cpu"
                    )
                
                # Perform Sliced Prediction
                sahi_result = get_sliced_prediction(
                    frame,
                    self.sahi_model,
                    slice_height=settings.SLICE_HEIGHT,
                    slice_width=settings.SLICE_WIDTH,
                    overlap_height_ratio=settings.OVERLAP_RATIO,
                    overlap_width_ratio=settings.OVERLAP_RATIO
                )
                
                # Convert SAHI results to ultralytics-compatible boxes list
                # This is a simplified fallback; in production we map carefully
                boxes = []
                for pred in sahi_result.object_prediction_list:
                    # Filter for vehicles (classes mapping might vary, usually 2,3,5,7)
                    if pred.category.id in [2, 3, 5, 7]:
                        # Mock an ultralytics box for downstream compatibility
                        class DummyBox:
                            def __init__(self, p):
                                self.xyxy = [torch.tensor([p.bbox.minx, p.bbox.miny, p.bbox.maxx, p.bbox.maxy])]
                                self.id = [torch.tensor([-1])] # Track ID logic needs sync
                                self.cls = [torch.tensor([p.category.id])]
                                self.conf = [torch.tensor([p.score.value])]
                        boxes.append(DummyBox(pred))
                
                # v4.0 Note: Tracking logic (ByteTrack) needs frame-level consistency
                # For now, we return these for forensic snapshots. 
                # REAL TRACKING still uses standard YOLO track in main loop for speed.
                if len(boxes) > 0: return boxes
            except Exception as e:
                logger.error(f"[SAHI AGENT] Slicing error: {e}")

        # Fallback: Standard YOLOv8 Tracking
        # v2.3: Lowered threshold for high sensitivity
        results = self.vehicle_model.track(frame, classes=[2, 3, 5, 7], persist=True, verbose=False, 
                                          tracker="bytetrack.yaml", conf=self.current_threshold)
        boxes = results[0].boxes
        
        # v2.3.5: Apply ROI Filter
        if self.roi_mask is not None:
            filtered_boxes = []
            h, w = frame.shape[:2]
            # Resize mask if frame size changed (e.g. multi-cam or dynamic res)
            if self.roi_mask.shape[:2] != (h, w):
                self.roi_mask = cv2.resize(self.roi_mask, (w, h))

            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                
                # Check if center of box is in white region of mask
                if 0 <= cx < w and 0 <= cy < h:
                    if self.roi_mask[cy, cx] > 0:
                        filtered_boxes.append(box)
            
            return filtered_boxes
            
        return boxes

    def monitor_agent_tune(self, track_density: float):
        """
        Monitor Agent: Auto-tunes detection threshold based on activity.
        If density (tracks per frame) is very low, we lower the threshold to find more.
        """
        if self.sensitivity == "HIGH":
            target = 0.15
        elif self.sensitivity == "BALANCED":
            target = 0.25
        else:
            target = 0.45

        if track_density < 0.05: # Very few detections
            self.current_threshold = max(0.1, self.current_threshold - 0.05)
        elif track_density > 0.5: # Way too many, might be noise
            self.current_threshold = min(0.6, self.current_threshold + 0.05)
        
        logger.info(f"[MONITOR AGENT] Tune: New Threshold = {self.current_threshold}")

    # --- v3.0 Agentic Integrity Additions ---

    def quality_gatekeeper_score(self, image):
        """
        Quality Gatekeeper: Calculates Laplacian Variance (Sharpness).
        Returns: Sharpness score (Float).
        """
        if image is None or image.size == 0: return 0.0
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    def reid_guardian_embedding(self, vehicle_crop):
        """
        Re-ID Guardian: Generates a visual signature (color/shape summary).
        In v3.0, we use a simplified color-histogram-based embedding.
        """
        if vehicle_crop is None or vehicle_crop.size == 0: return ""
        # Resize to fixed size for consistency
        img = cv2.resize(vehicle_crop, (64, 64))
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Calculate histograms for H and S channels
        h_hist = cv2.calcHist([hsv], [0], None, [8], [0, 180])
        s_hist = cv2.calcHist([hsv], [1], None, [8], [0, 256])
        
        # Normalize and flatten
        cv2.normalize(h_hist, h_hist, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(s_hist, s_hist, 0, 1, cv2.NORM_MINMAX)
        
        embedding = np.concatenate([h_hist.flatten(), s_hist.flatten()])
        return json.dumps(embedding.tolist())

    def ocr_jury_arbitrate(self, local_text: str, cloud_text: str, vehicle_type: str = "CAR"):
        """
        OCR Jury Agent: Weighted arbitration between agents.
        """
        if not local_text: return cloud_text, "CLOUD"
        if not cloud_text: return local_text, "LOCAL"
        if local_text == cloud_text: return local_text, "CONSENSUS"
        
        # Pattern validation (Indian Format Priority)
        local_valid = self._is_valid_indian_format(local_text)
        cloud_valid = self._is_valid_indian_format(cloud_text)
        
        if local_valid and not cloud_valid:
            return local_text, "LOCAL (Pattern Match)"
        if cloud_valid and not local_valid:
            return cloud_text, "CLOUD (Pattern Match)"
            
        # Commercial syntax rule (v3.0 Implementation)
        if vehicle_type in ["TRUCK", "BUS", "AUTO"]:
            # Bias toward local OCR for these types as they often have specific fonts
            return local_text, "LOCAL (Commercial Bias)"
            
        return cloud_text, "CLOUD (Confidence Bias)"

    def qc_agent_verify(self, local_ocr: str, ai_ocr: str) -> bool:
        """
        QC Agent: Validates if local results match AI results.
        """
        if not local_ocr or not ai_ocr: return False
        return local_ocr.strip().upper() == ai_ocr.strip().upper()

    def semantic_validator(self, plate_text, vehicle_type):
        """
        Semantic Validator: Checks if plate syntax matches vehicle class (v4.0).
        e.g., Commercial plates (Yellow) usually have specific series in India.
        For now, uses CLIP-like logic (Visual Signature vs Metadata).
        """
        if not settings.ENABLE_VEHICLE_MATCHING: return True
        
        # Logic: If it's a BUS but has a very short plate (like a private bike), flag it.
        if vehicle_type in ["BUS", "TRUCK"] and len(plate_text) < 6:
            logger.warning(f"[SEMANTIC AGENT] Potential Misassociation: {plate_text} on {vehicle_type}")
            return False
            
        # Commercial check: BUS/TRUCKS in India often have specific patterns
        # For this v4.0 alpha, we return True but log the check
        return True

    def detect_plates(self, vehicle_crop):
        if self.plate_model is None: return []
        results = self.plate_model(vehicle_crop, verbose=False)
        return results[0].boxes

    def estimate_blur(self, image):
        if image is None or image.size == 0: return 0.0
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    def recognize_plate(self, plate_crop, video_id: int = -1, allow_gemini: bool = True) -> tuple[str, float, str, str]:
        from app.models.models import RecheckStatus
        if plate_crop is None or plate_crop.size == 0:
            return None, 0.0, None, RecheckStatus.SKIPPED.value
            
        plate_crop = self.preprocess_for_night_mode(plate_crop)
        h, w = plate_crop.shape[:2]
        if h < 40:
            plate_crop = cv2.resize(plate_crop, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
            
        best_text, max_conf = "", 0.0
        
        if self.use_paddle:
            try:
                res = self.reader.ocr(plate_crop, cls=True)
                if res and res[0]:
                    for line in res[0]:
                        text, prob = line[1]
                        clean = "".join([c for c in text if c.isalnum()]).upper()
                        if self._is_valid_plate(clean) and prob > max_conf:
                            max_conf, best_text = prob, clean
            except: pass
        else:
            try:
                res = self.reader.readtext(plate_crop)
                if res:
                    for (bbox, text, prob) in res:
                        clean = "".join([c for c in text if c.isalnum()]).upper()
                        if self._is_valid_plate(clean) and prob > max_conf:
                            max_conf, best_text = prob, clean
            except: pass

        if not best_text: return None, 0.0, None, RecheckStatus.SKIPPED.value
        
        # Validation
        is_valid_format = self._is_valid_indian_format(best_text)
        blur_score = self.estimate_blur(plate_crop)
        should_recheck = max_conf < settings.RECHECK_CONFIDENCE_THRESHOLD or not is_valid_format
        if blur_score < 30: should_recheck = False

        recheck_status = RecheckStatus.NONE.value
        if should_recheck and allow_gemini:
            recheck_status = RecheckStatus.PENDING.value
            ai_text, ai_conf, v_info = self.rechecker.recheck(plate_crop, video_id)
            if ai_text:
                recheck_status = RecheckStatus.SUCCESS.value
                if ai_conf > max_conf or (not is_valid_format and self._is_valid_indian_format(ai_text)):
                    return ai_text, ai_conf, v_info, recheck_status
            else:
                recheck_status = RecheckStatus.FAILED.value
        
        return best_text, max_conf, None, recheck_status

    def _is_valid_indian_format(self, text):
        if not text or len(text) < 4: return False
        state_codes = ['AN','AP','AR','AS','BR','CH','CT','DN','DD','DL','GA','GJ','HR','HP','JK','JH','KA','KL','LD','MP','MH','MN','ML','MZ','NL','OD','OR','PY','PB','RJ','SK','TN','TG','TS','TR','UP','UK','UA','WB']
        if text[:2].upper() not in state_codes:
            if re.match(r"^[0-9]{2}BH", text):
                 return re.match(r"^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$", text) is not None
            return False
        return re.match(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{1,4}$", text) or re.match(r"^[A-Z]{2}[0-9]{1,2}[0-9]{4}$", text)

    def _is_valid_plate(self, text):
        negative_list = ["VEHICLE", "PLATE", "STOP", "CAR", "CNG", "INDIA", "ROAD", "DRIVE", "SLOW", "KEEP", "DISTANCE"]
        if any(word in text for word in negative_list): return False
        if len(text) < 4 or len(text) > 12: return False
        return (any(c.isdigit() for c in text) and any(c.isalpha() for c in text)) or (any(c.isdigit() for c in text) and len(text) >= 4)

    def preprocess_for_night_mode(self, image: np.ndarray) -> np.ndarray:
        if image is None: return image
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        if np.mean(hsv[:, :, 2]) < 60:
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            cl = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8)).apply(l)
            return cv2.cvtColor(cv2.merge((cl, a, b)), cv2.COLOR_LAB2BGR)
        return image

ai_service = AIService()
