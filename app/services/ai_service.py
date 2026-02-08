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
import json
from app.utils.validators import IndianPlateValidator
try:
    from sahi import AutoDetectionModel
    from sahi.predict import get_sliced_prediction
    SAHI_AVAILABLE = True
except ImportError:
    SAHI_AVAILABLE = False

import google.generativeai as genai
from abc import ABC, abstractmethod
from typing import Optional, List, Dict
import time
import re
import json

logger = logging.getLogger(__name__)

# Complete Indian State and UT Registration Codes (36 total - 28 States + 8 UTs)
INDIAN_STATE_CODES = [
    # States (28)
    "AP",  # Andhra Pradesh
    "AR",  # Arunachal Pradesh
    "AS",  # Assam
    "BR",  # Bihar
    "CG",  # Chhattisgarh
    "GA",  # Goa
    "GJ",  # Gujarat
    "HR",  # Haryana
    "HP",  # Himachal Pradesh
    "JH",  # Jharkhand
    "KA",  # Karnataka
    "KL",  # Kerala
    "MP",  # Madhya Pradesh
    "MH",  # Maharashtra
    "MN",  # Manipur
    "ML",  # Meghalaya
    "MZ",  # Mizoram
    "NL",  # Nagaland
    "OD",  # Odisha
    "PB",  # Punjab
    "RJ",  # Rajasthan
    "SK",  # Sikkim
    "TN",  # Tamil Nadu
    "TS",  # Telangana (also TG in older systems)
    "TR",  # Tripura
    "UP",  # Uttar Pradesh
    "UK",  # Uttarakhand
    "WB",  # West Bengal
    # Union Territories (8)
    "AN",  # Andaman and Nicobar Islands
    "CH",  # Chandigarh
    "DN",  # Dadra and Nagar Haveli (legacy)
    "DD",  # Daman and Diu / Dadra and Nagar Haveli and Daman and Diu
    "DL",  # Delhi
    "JK",  # Jammu and Kashmir
    "LA",  # Ladakh
    "LD",  # Lakshadweep
    "PY"   # Puducherry
]

def correct_ocr_errors(text: str) -> str:
    """Fix common OCR mistakes for Indian plates."""
    if not text or len(text) < 4:
        return text
    
    # Extract first 2-3 characters as potential state code
    potential_state = text[:2].upper()
    
    # Common OCR substitutions that break state codes
    corrections = {
        "LL": "DL",  # Double L → Delhi
        "0D": "OD",  # Zero → O for Odisha
        "8R": "BR",  # 8 → B for Bihar
        "l": "I",    # lowercase L → I
        "O": "0",    # O → 0 in numeric sections
    }
    
    # If potential state code is invalid, try corrections
    if potential_state not in INDIAN_STATE_CODES:
        for wrong, right in corrections.items():
            if potential_state == wrong:
                text = right + text[2:]
                break
    
    return text


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
    def check_plate(self, image: np.ndarray, local_ocr: str = "UNKNOWN", vehicle_type: str = "UNKNOWN") -> tuple[str, float, str, str, Optional[dict]]:
        pass

    @abstractmethod
    def check_collage(self, collage: np.ndarray, video_id: int = -1) -> list[dict]: # Result dicts include partial_confidence
        pass

class GeminiProvider(BaseAIProvider):
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        if not api_key:
            logger.warning("Gemini API Key missing! Gemini provider will be disabled.")
            self.model = None
            return
            
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.last_call = 0
        self.rate_limit_delay = 1.0
        self.prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agents", "prompts")

    def _load_prompt(self, filename: str) -> str:
        try:
            path = os.path.join(self.prompts_dir, filename)
            with open(path, "r") as f:
                return f.read()
        except:
            return ""

    def check_plate(self, image: np.ndarray, local_ocr: str = "UNKNOWN", vehicle_type: str = "UNKNOWN") -> tuple[str, float, str, str, Optional[dict]]:
        if not self.model: return None, 0.0, None, None, None
        now = time.time()
        if now - self.last_call < 1.0:
            time.sleep(1.0 - (now - self.last_call))
        self.last_call = time.time()

        try:
            from PIL import Image
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            
            # Agent 2: Validation Agent
            system_prompt = self._load_prompt("validation.md")
            if not system_prompt: # Fallback
                logger.error("Prompts dir not found, using fallback.")
                return None, 0.0, None, None, None
                
            prompt = system_prompt.replace("{{local_ocr_result}}", local_ocr).replace("{{vehicle_type}}", vehicle_type)
            
            response = self.model.generate_content([prompt, pil_image])
            text = response.text.replace("```json", "").replace("```", "").strip()
            result = json.loads(text)
            
            if result.get("is_match") and result.get("plate"):
                # Pack metadata into a dict-like structure or just return the dict as vehicle_info if handled by caller
                # video_service.py expects res as a dict in batch mode. 
                # For recognize_plate, we'll return a dict for vehicle_info.
                v_meta = {
                    "make": result.get("vehicle", {}).get("make"),
                    "model": result.get("vehicle", {}).get("model"),
                    "color": result.get("vehicle", {}).get("color"),
                    "type": result.get("vehicle", {}).get("type"),
                    "helmet_status": result.get("occupants", {}).get("helmet_status"),
                    "passengers": result.get("occupants", {}).get("passenger_count")
                }
                return str(result["plate"]), result.get("confidence", 0.9), v_meta, result.get("insight"), result.get("partial_confidence")
            
            return None, 0.0, None, result.get("insight"), result.get("partial_confidence")

        except Exception as e:
            logger.error(f"Gemini Validation Error: {e}")
            return None, 0.0, None, None, None

    def get_metadata_only(self, image: np.ndarray) -> dict:
        """Agent 4: Metadata Agent (Low Cost/Flash)"""
        if not self.model: return {}
        try:
            from PIL import Image
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            
            prompt = """
            Identify vehicle details for the primary vehicle:
            - Make/Model (e.g. Honda City)
            - Color
            - Passengers count
            
            Return JSON: {"make": "...", "color": "...", "type": "...", "helmet_status": "...", "passengers": 0}
            """
            response = self.model.generate_content([prompt, pil_image])
            text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except:
            return {}

    def check_collage(self, collage: np.ndarray, video_id: int = -1) -> list[dict]:
        # Agent 3: Auditor Agent (Collage Forensics)
        if not self.model: return []
        now = time.time()
        if now - self.last_call < 1.0:
            time.sleep(1.0 - (now - self.last_call))
        self.last_call = time.time()

        try:
            from PIL import Image
            pil_image = Image.fromarray(cv2.cvtColor(collage, cv2.COLOR_BGR2RGB))
            
            # Using v5.5 Auditor Prompt
            # For collage check, we revert to a specialized collage prompt OR adapt the auditor prompt 
            # Current v5.5 plan implies "Auditor" is for single hard cases, but let's stick to the previous Grid logic for now 
            # and upgrade it later if strictly requested. The user plan mentions Agent 2 is Validation (Collage+Crop).
            # Wait, user plan says: "Agent 2... Input: 3x3 Collage... Logic: Triggered if Regex fails".
            # This implies Agent 2 (Flash) does the Collage.
            
            # Let's keep the legacy collage prompt for now but load it from file if we had one "collage_agent.md".
            # For now, I will inline the upgraded v5.5 Collage Prompt here to match the "Validation Agent" description for 3x3.
            
            prompt = """
            You are a High-Speed Validation Agent (Agent 2).
            Trace the vehicle crops in this 3x3 grid (ID labels are green).
            
            For each vehicle:
            1. Read the plate.
            2. Check vehicle class (CAR, TRUCK, BUS, MOTORCYCLE, AUTO).
            3. Detect Make and Model (e.g. Maruti Swift, Toyota Innova).
            4. Detect Color (e.g. White, Black).
            5. For motorcycles: Detect if driver is wearing a HELMET (YES/NO/NA).
            6. Count visible passengers (approximate).
            
            Return JSON array: [{
                "track_id": 123, 
                "plate": "...", 
                "confidence": 0.9, 
                "type": "CAR", 
                "make": "Maruti Swift", 
                "color": "White", 
                "helmet_status": "YES/NO/NA",
                "passengers": 1,
                "insight": "...", 
                "partial_confidence": {"state": 0.9, "dist": 0.9, "series": 0.9, "last4": 0.9}
            }]
            
            The 'insight' should be a technical observation.
            Use "UNCERTAIN" for unreadable plates.
            """
            
            response = self.model.generate_content([prompt, pil_image])
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].strip()
            results = json.loads(text)
            # v5.5 Defensive: Ensure all plates are strings
            if isinstance(results, list):
                for r in results:
                    if 'plate' in r: r['plate'] = str(r['plate'])
            return results
        except Exception as e:
            logger.error(f"Gemini Collage Error: {e}")
            return []

    def audit_case(self, image: np.ndarray, local_ocr: str, fcf_score: float, vehicle_desc: str) -> dict:
        # Agent 3: Forensic Auditor (Single Hard Case)
        if not self.model: return {}
        
        try:
            from PIL import Image
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            
            system_prompt = self._load_prompt("auditor.md")
            prompt = system_prompt.replace("{{local_ocr_result}}", local_ocr)\
                                  .replace("{{fcf_score}}", str(fcf_score))\
                                  .replace("{{vehicle_description}}", vehicle_desc)
                                  
            response = self.model.generate_content([prompt, pil_image])
            text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except Exception as e:
            logger.error(f"Gemini Auditor Error: {e}")
            return {}

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
    """
    v5.1 Tiered Agent Routing:
    - Tier 1: Local OCR (Handled in recognize_plate)
    - Tier 2: Gemini Flash (Fast, Cost-Effective)
    - Tier 3: Gemini Pro (Deep Reasoning, Expensive)
    """
    def __init__(self):
        self.flash_provider = None
        self.pro_provider = None
        
        # Initialize Providers if Key exists
        if settings.GEMINI_API_KEY:
            # Always load Flash as primary
            self.flash_provider = GeminiProvider(settings.GEMINI_API_KEY, model_name=settings.MODEL_FLASH)
            
            # Load Pro if Tiered Routing is enabled
            if settings.ENABLE_TIERED_ROUTING:
                self.pro_provider = GeminiProvider(settings.GEMINI_API_KEY, model_name=settings.MODEL_PRO)
        
    def recheck(self, image: np.ndarray, video_id: int = -1) -> tuple[str, float, Optional[dict], str, Optional[dict]]:
        if not settings.ENABLE_GLOBAL_RECHECK: return None, 0.0, None, None, None
        
        # Usage tracking
        if video_id != -1:
            try:
                import redis
                r = redis.from_url(settings.REDIS_URL, decode_responses=True)
                key = f"gemini_usage:{video_id}"
                count = r.incr(key)
                if count > settings.MAX_GEMINI_CALLS_PER_VIDEO: return None, 0.0, None, None, None
            except: pass

        # Tier 2: Flash
        if self.flash_provider:
            text, conf, v_info, insight, p_conf = self.flash_provider.check_plate(image)
            if text and conf > 0.8: 
                return text, conf, v_info, insight, p_conf
            
            # Tier 3: Escalation to Pro
            if settings.ENABLE_TIERED_ROUTING and self.pro_provider:
                logger.info(f"[TIERED ROUTING] Escalating to Pro for video {video_id}...")
                text_pro, conf_pro, v_info_pro, insight_pro, p_conf_pro = self.pro_provider.check_plate(image)
                if text_pro and conf_pro > 0.8:
                    return text_pro, conf_pro, v_info_pro, insight_pro, p_conf_pro
                 
        return None, 0.0, None, None, None

    def recheck_batch(self, collage: np.ndarray, video_id: int = -1) -> list[dict]:
        if not settings.ENABLE_GLOBAL_RECHECK: return []
        
        # Usage tracking
        if video_id != -1:
            try:
                import redis
                r = redis.from_url(settings.REDIS_URL, decode_responses=True)
                key = f"gemini_usage:{video_id}"
                r.incr(key)
            except: pass

        # Collages are complex, so we might want to default to Pro if budget allows, 
        # but sticking to Tiered logic: Flash first.
        
        if self.flash_provider:
            results = self.flash_provider.check_collage(collage, video_id)
            if results: return results
            
            if settings.ENABLE_TIERED_ROUTING and self.pro_provider:
                logger.info(f"[TIERED ROUTING] Escalating Batch to Pro for video {video_id}...")
                return self.pro_provider.check_collage(collage, video_id)
                
        return []

class LogicBridge:
    """
    v5.5 Agent 4: Symbolic Supervisor.
    Arbitrates between Agents and checks Database History.
    """
    def __init__(self):
        pass

    def arbitrate(self, agent2_result: dict, agent3_result: dict, history: list) -> dict:
        """
        Decides the final plate based on Agent 2 (Flash), Agent 3 (Pro), and History.
        """
        # 1. Stalker Check: If plate found in history < 5 mins ago at diff location -> CLONE
        # (This logic requires full DB access, simulated here or passed via history list)
        
        # 2. Consensus Check
        val_plate = agent2_result.get("plate", "UNKNOWN")
        audit_plate = agent3_result.get("validated_plate", "UNKNOWN")
        
        if val_plate == audit_plate and val_plate != "UNKNOWN":
            return {"plate": val_plate, "status": "CONFIRMED", "agent": "CONSENSUS"}
            
        # 3. Hierarchy: Trust Agent 3 (Pro) if confidence is high
        if agent3_result.get("confidence_adjustment", 0) > 0.8:
            return {"plate": agent3_result.get("validated_plate"), "status": "AUDITED", "agent": "AGENT_3"}
            
        # 4. Fallback to Validation if Auditor is uncertain
        if val_plate != "UNKNOWN":
            return {"plate": val_plate, "status": "VALIDATED", "agent": "AGENT_2"}
            
        return {"plate": None, "status": "FAILED", "agent": "NONE"}

class AIService:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AIService, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance

    def initialize(self):
        try:
            from app.tools.mcp_vision_v2 import vision_tool
            self.vision_tool = vision_tool
            
            # v5.1: VisionToolV2 handles the model loading
            self.vehicle_model = self.vision_tool.model
            
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
            self.search_agent = SearchAgent(self.rechecker.flash_provider.model if self.rechecker.flash_provider else None)
            self.current_threshold = settings.DETECTION_THRESHOLD
            self.sensitivity = settings.AGENTS_SENSITIVITY
            
            self.roi_mask = None
            self._load_roi_mask()
        except Exception as e:
            logger.error(f"Error initializing AI models: {e}")

    def _load_roi_mask(self):
        try:
            if os.path.exists(settings.ROI_MASK_PATH):
                self.roi_mask = cv2.imread(settings.ROI_MASK_PATH, cv2.IMREAD_GRAYSCALE)
                if self.roi_mask is not None:
                     logger.info(f"Loaded ROI Mask from {settings.ROI_MASK_PATH}")
                else:
                    logger.warning("ROI Mask empty or unreadable.")
            else:
                 # Optional: Create blank white mask or just leave None
                 self.roi_mask = None
        except Exception as e:
            logger.error(f"Failed to load ROI mask: {e}")
            self.roi_mask = None

    def detect_vehicles(self, frame):
        # v5.1: Delegated to VisionToolV2 (YOLOv11)
        # Note: We are now returning a list of dicts, not Box objects.
        # video_service.py must be updated to handle dictionary access.
        
        # SAHI Logic needs to be ported if strictly required, but for v5.1 speed 
        # we rely on YOLOv11's superior small object detection first.
        
        detections = self.vision_tool.detect_vehicles(frame, conf=self.current_threshold)
        
        # v2.3.5: Apply ROI Filter
        if self.roi_mask is not None:
            filtered_dets = []
            h, w = frame.shape[:2]
            if self.roi_mask.shape[:2] != (h, w):
                self.roi_mask = cv2.resize(self.roi_mask, (w, h))

            for det in detections:
                x1, y1, x2, y2 = map(int, det['bbox'])
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                if 0 <= cx < w and 0 <= cy < h:
                    if self.roi_mask[cy, cx] > 0:
                        filtered_dets.append(det)
            return filtered_dets
            
        return detections

    def estimate_blur(self, image):
        if image is None or image.size == 0: return 0.0
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    def _is_valid_indian_format(self, text):
        return IndianPlateValidator.is_valid(text)

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

    def detect_plates(self, vehicle_crop):
        if self.plate_model is None: return []
        results = self.plate_model(vehicle_crop, verbose=False)
        return results[0].boxes

    def recognize_plate(self, plate_crop, video_id: int = -1, allow_gemini: bool = True) -> tuple[str, float, Optional[dict], str, str, Optional[dict]]:
        from app.models.models import RecheckStatus
        if plate_crop is None or plate_crop.size == 0:
            return None, 0.0, None, RecheckStatus.SKIPPED.value, None, None
            
        # v5.1: Advanced Pre-processing Pipeline
        plate_crop = self.vision_tool.apply_homography(plate_crop)
        plate_crop = self.vision_tool.enhance_plate_crop(plate_crop)
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
                        clean = correct_ocr_errors(clean)  # Fix D→L, O→0, etc.
                        if self._is_valid_plate(clean) and prob > max_conf:
                            max_conf, best_text = prob, clean
            except: pass
        else:
            try:
                res = self.reader.readtext(plate_crop)
                if res:
                    for (bbox, text, prob) in res:
                        clean = "".join([c for c in text if c.isalnum()]).upper()
                        clean = correct_ocr_errors(clean)  # Fix D→L, O→0, etc.
                        if self._is_valid_plate(clean) and prob > max_conf:
                            max_conf, best_text = prob, clean
            except: pass

        # Validation & Yield Optimization
        is_valid_format = self._is_valid_indian_format(best_text) if best_text else False
        blur_score = self.estimate_blur(plate_crop)
        
        # v5.5: If local OCR failed entirely, WE MUST recheck if Gemini is allowed
        # Otherwise, use standard confidence threshold.
        should_recheck = (not best_text) or (max_conf < settings.RECHECK_CONFIDENCE_THRESHOLD) or (not is_valid_format)
        
        if blur_score < 30 and best_text: should_recheck = False 

        recheck_status = RecheckStatus.NONE.value
        insight = "Initial local OCR scan."
        p_conf = None
        if should_recheck and allow_gemini:
            recheck_status = RecheckStatus.PENDING.value
            ai_text, ai_conf, v_info, ai_insight, ai_p_conf = self.rechecker.recheck(plate_crop, video_id)
            if ai_text:
                recheck_status = RecheckStatus.SUCCESS.value
                insight = ai_insight or "Gemini verified reading."
                p_conf = ai_p_conf
                if ai_conf > max_conf or (not is_valid_format and self._is_valid_indian_format(ai_text)):
                    return ai_text, ai_conf, v_info, recheck_status, insight, p_conf
            else:
                recheck_status = RecheckStatus.FAILED.value
                insight = ai_insight or "Gemini failed to verify."
                p_conf = ai_p_conf
        
        return best_text, max_conf, None, recheck_status, insight, p_conf

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

    def ocr_jury_arbitrate(self, local_text: str, cloud_text: str, vehicle_type: str = "CAR", cloud_conf: float = 1.0):
        """
        OCR Jury Agent: Weighted arbitration between agents.
        v5.1 Upgrade: ENFORCED REJECTION.
        """
        if not local_text and not cloud_text: return "NO PLATE", "FAILED"
        
        # v5.5 Forensic Triage: Be more permissive of "fragments"
        if not cloud_text or "NO PLATE" in cloud_text:
            cloud_text = None
        elif cloud_conf < 0.40: # Drastically lowered from 0.85 to capture fragments
            cloud_text = cloud_text + " (Fragment)"
            
        if not local_text and not cloud_text: return "UNCERTAIN", "FORENSIC_PENDING"
        if not local_text: return cloud_text, "CLOUD"
        if not cloud_text: return local_text, "LOCAL"
        if local_text == cloud_text: return local_text, "CONSENSUS"
        
        # v5.1 Jury weighting
        return local_text, "LOCAL (Overridden)"

    def get_quick_metadata(self, vehicle_crop) -> dict:
        """Agentic Interface for Metadata extraction."""
        if not self.rechecker.flash_provider: return {}
        return self.rechecker.flash_provider.get_metadata_only(vehicle_crop)
        
        # Pattern validation (Indian Format Priority)
        local_valid = self._is_valid_indian_format(local_text)
        cloud_valid = self._is_valid_indian_format(cloud_text)
        
        # v5.1 Logic: If conflicting, and both are valid, and Cloud confidence is not 1.0, prefer Local if it was enhanced.
        if local_valid and not cloud_valid:
            return local_text, "LOCAL (Pattern Match)"
        if cloud_valid and not local_valid:
            return cloud_text, "CLOUD (Pattern Match)"
            
        # Commercial / Professional Syntax Bias
        if vehicle_type in ["TRUCK", "BUS", "AUTO", "LORRY"]:
            if local_valid: return local_text, "LOCAL (Commercial Pattern)"
            
        return cloud_text, "CLOUD (Intelligence Bias)"

    def qc_agent_verify(self, local_ocr: str, ai_ocr: str) -> bool:
        """
        QC Agent: Validates if local results match AI results.
        """
        if not local_ocr or not ai_ocr: return False
        return local_ocr.strip().upper() == ai_ocr.strip().upper()

    def semantic_validator(self, plate_text, vehicle_type):
        """
        Semantic Validator: Checks if plate syntax matches vehicle class (v4.0+).
        """
        if not settings.ENABLE_VEHICLE_MATCHING: return True
        if not plate_text or plate_text == "NO PLATE": return False
        
        # v5.0 Tightened Logic:
        # 1. Length Check: Indian plates are typically 10 chars (or 7-9 for older)
        if len(plate_text) < 5 or len(plate_text) > 12:
            return False
            
        # 2. Vehicle Class Consistency
        # Commercial vehicles (Truck/Bus/Auto) MUST have standard patterns.
        # If a Truck has a 4-digit plate sans state code, it's likely a misread.
        if vehicle_type in ["BUS", "TRUCK", "AUTO"] and not self._is_valid_indian_format(plate_text):
            logger.warning(f"[SEMANTIC AUDIT] Suspected Mismatch: {plate_text} on {vehicle_type}")
            return False
            
        return True


ai_service = AIService()
