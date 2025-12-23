from fastapi import APIRouter, Depends
import os
from sqlalchemy.orm import Session
import subprocess
import torch
import psutil
import platform
import socket
from app.core.config import settings
from app.api import deps

router = APIRouter()

def get_cpu_name():
    try:
        if platform.system() == "Windows":
            cmd = "wmic cpu get name"
            name = subprocess.check_output(cmd, shell=True).decode().strip().split('\n')
            if len(name) > 1:
                return name[1].strip()
        else:
            # Fallback for linux/mac if needed
            return platform.processor()
    except:
        return platform.processor()

def get_disk_name():
    try:
        if platform.system() == "Windows":
            cmd = 'Get-CimInstance Win32_DiskDrive | Select-Object Model | ConvertTo-Json'
            ps_proc = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True)
            if ps_proc.returncode == 0:
                import json
                data = json.loads(ps_proc.stdout)
                if isinstance(data, dict):
                    return data.get("Model", "Unknown Disk")
                elif isinstance(data, list) and len(data) > 0:
                    return data[0].get("Model", "Unknown Disk")
    except:
        pass
    return "Standard Disk"

def check_redis():
    try:
        # Simple socket check for Redis URL
        from redis import Redis
        r = Redis.from_url(settings.REDIS_URL, socket_timeout=1)
        r.ping()
        return "RUNNING"
    except:
        return "OFFLINE"

@router.get("/health")
def get_system_health(current_user=Depends(deps.get_current_user)):
    # 1. GPU Detection (Precise)
    gpu_info = "NOT DETECTED"
    gpu_capabilities = "CPU-ONLY"
    
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_info = f"NVIDIA {gpu_name}"
        gpu_capabilities = "AI-ACCELERATED"
    else:
        # Check for Integrated Graphics on Windows
        try:
            cmd = 'Get-CimInstance Win32_VideoController | Select-Object Name | ConvertTo-Json'
            ps_proc = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True)
            if ps_proc.returncode == 0:
                import json
                data = json.loads(ps_proc.stdout)
                if isinstance(data, dict):
                    gpu_info = data.get("Name", "Integrated Graphics")
                elif isinstance(data, list) and len(data) > 0:
                    gpu_info = data[0].get("Name", "Integrated Graphics")
        except:
            gpu_info = "Intel/AMD Integrated"

    # 2. CPU Intelligence
    cpu_name = get_cpu_name()
    
    # 3. Disk Intelligence
    disk_name = get_disk_name()
    
    # 4. Memory Intelligence
    mem = psutil.virtual_memory()
    memory_total = f"{mem.total / (1024**3):.1f} GB"
    
    # 5. Service Status
    redis_status = check_redis()
    gemini_status = "CONFIGURED" if settings.GEMINI_API_KEY else "MISSING KEY"

    # 6. ROI Status
    roi_status = "ACTIVE" if os.path.exists(settings.ROI_MASK_PATH) else "MISSING"

    return {
        "cpu_name": cpu_name,
        "gpu_name": gpu_info,
        "gpu_caps": gpu_capabilities,
        "disk_name": disk_name,
        "memory_total": memory_total,
        "redis_status": redis_status,
        "gemini_status": gemini_status,
        "roi_status": roi_status,
        "cpu_usage": psutil.cpu_percent(),
        "disk_usage": psutil.disk_usage(os.path.abspath(".")).percent,
        "mem_usage": mem.percent,
        "os": f"{platform.system()} {platform.release()}"
    }

@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(deps.get_db), current_user=Depends(deps.get_current_user)):
    from app.models.models import Video, VehicleDetection, VideoStatus, RecheckStatus
    
    total_videos = db.query(Video).filter(Video.owner_id == current_user.id).count()
    total_detections = db.query(VehicleDetection).join(Video).filter(Video.owner_id == current_user.id).count()
    
    # Failed detections (UNKNOWN or Gemini Failed)
    total_failed = db.query(VehicleDetection).join(Video).filter(
        Video.owner_id == current_user.id,
        (VehicleDetection.plate_number == "UNKNOWN") | (VehicleDetection.recheck_status == RecheckStatus.FAILED)
    ).count()
    
    return {
        "total_videos": total_videos,
        "total_detections": total_detections,
        "total_failed": total_failed
    }
