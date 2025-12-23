import os
import subprocess
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class VideoConditionerAgent:
    """
    Standardizes raw footage:
    1. Converts VFR to CFR (30 FPS)
    2. De-interlaces (if needed)
    3. Sharpens (Unsharp Mask)
    4. Stabilizes (if enabled)
    """
    
    def process(self, input_path: str) -> str:
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Source video not found: {input_path}")
            
        filename = os.path.basename(input_path)
        output_name = f"conditioned_{filename}.mp4"
        output_dir = os.path.join(settings.STORAGE_PATH, "conditioned")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_name)
        
        logger.info(f"Conditioning video: {input_path} -> {output_path}")
        
        # Build FFmpeg command for maximum performance/quality
        # -vf: fps=30 (CFR), unsharp (sharpening), vidstabdetect/vidstabtransform (stabilization)
        # For simplicity and speed in this v4.0 alpha, we start with CFR + Sharpening
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-filter:v', 'fps=fps=30,unsharp=5:5:1.5:5:5:0.0',
            '-c:v', 'libx264',
            '-crf', '18',
            '-preset', 'veryfast',
            output_path
        ]
        
        try:
            # Run command and capture output
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                return input_path # Fallback to original on failure
                
            logger.info("Conditioning complete")
            return output_path
        except Exception as e:
            logger.error(f"Failed to condition video: {e}")
            return input_path # Fallback

ingest_manager = VideoConditionerAgent()
