# ALPR Pro v5.0: Master Technical Manual 🧠🛡️🕵️

This document provides a comprehensive guide to the **Hybrid Neuro-Symbolic Hub** architecture. It covers file purposes, API specifications, and the end-to-end processing flow.

---

## 📁 1. Detailed Project Anatomy

### **Core Hub (`/app`)**
- `main.py`: The application entry point. Bootstraps FastAPI, mounts routers, and serves the frontend.
- `worker.py`: Background task consumer. Listens for new video uploads and triggers the processing loop.
- `models/models.py`: The source of truth for structured forensic data. Includes `VehicleCase` (investigation record) and `AgentLog` (thought trail).
- `db/session.py`: Database connection pool and session factories.

### **The Brains (`/app/agents`)**
- `orchestrator.py`: **Master Case Manager**. Decides which models to use based on crop difficulty.
- `auditor.py`: **Verification Agent**. Cross-references visual signatures with plate data to flag mismatches.
- `prompts.py`: Strategic system instructions that define how agents "think" and "reason."

### **The Capabilities (`/app/tools`)**
- `mcp_yolo.py`: Standardized detection and tracking (SAHI-enabled).
- `mcp_enhance.py`: Image restoration tool for upscaling blurry/distant vehicles.
- `mcp_ocr.py`: Recognition tool bridging local PaddleOCR with Google Gemini 1.5 Pro.
- `mcp_video.py`: FFmpeg-based video conditioning (standardization).

### **The Interfaces (`/app/api`)**
- `auth.py`: JWT-based user session management.
- `videos.py`: Pipeline management (Upload -> Process -> Report).
- `detections.py`: Advanced forensic search (Plate, Date, Confidence).
- `v5_api.py`: Forensic Case Feed streaming.

---

## � 2. API & Payload Specification

### **Authentication**
- **Endpoint**: `POST /api/auth/login`
- **Body (Form-Data)**: `username`, `password`
- **Response**: `{ "access_token": "...", "token_type": "bearer" }`

### **Forensic Video Submission**
- **Endpoint**: `POST /api/videos/upload`
- **Body (Multipart)**: `file` (Video binary)
- **Flow**: Returns immediate ID; processing starts in background.

### **Vehicle Detection Search**
- **Endpoint**: `GET /api/detections/`
- **Params**: `plate`, `min_confidence`, `start_date`
- **Response**: `{ "items": [...], "total": X }`
- **Detection Payload**:
```json
{
  "id": 101,
  "plate_number": "UP14BT1234",
  "vehicle_type": "CAR",
  "confidence": 0.98,
  "ocr_source": "CONSENSUS",
  "recheck_status": "success",
  "track_id": 14
}
```

### **Forensic Case Logs (v5.0)**
- **Endpoint**: `GET /api/v5/cases/{video_id}/{track_id}/logs`
- **Description**: Fetches the reasoning steps for a specific vehicle.
- **Example Log**:
```json
{
  "step_number": 2,
  "agent_name": "Orchestrator",
  "action_taken": "INVOKE_ENHANCER",
  "reasoning": "Local crop pixels < 2000. Super-res required for verification."
}
```

---

## 📈 3. End-to-End Application Flow

### **Phase 1: Ingestion & Inception**
1. **User Auth**: User logs in via `login.html`. JWT is stored in local storage.
2. **Video Upload**: User drops a video into `dashboard.html`. File is saved to `storage/` and a `Video` record is created in PENDING state.
3. **Queueing**: A Celery task (`process_video_task`) is dispatched to Redis.

### **Phase 2: Agentic Processing (The Brain at Work)**
1. **Conditioning**: `mcp_video` standardizes the footage (CFR, Sharpening).
2. **Detection**: `mcp_yolo` scans frames, identifying vehicle boxes and tracking them via unique `track_id`.
3. **Orchestration**: For every unique track:
   - **Quality Check**: Orchestrator measures blur.
   - **Restoration**: If blurry, `mcp_enhance` generates a high-fidelity crop.
   - **Recognition**: `mcp_ocr` performs local OCR -> then Gemini Vision provides the "Consultant" opinion for consensus.
   - **Audit**: `Auditor` agent checks if the plate format matches the vehicle class (e.g., Bike plate on a Truck?).

### **Phase 3: Forensic Delivery**
1. **Registry Update**: Final verified data is saved to `VehicleDetection` and `VehicleCase` tables.
2. **Visual Verification**: 3x3 Forensic Collages are generated for every batch.
3. **User Audit**: User opens the dashboard, expands a detection, and the **Agent Thought Console** streams the logs via `v5_api.py`.

---

## ✅ 4. Summary of Master Components

| Component | Responsibility | Primary Tech |
| :--- | :--- | :--- |
| **API** | Communication & Data Access | FastAPI |
| **Agents** | Logic, Decisions & Auditing | Python / LangGraph |
| **Tools/MCP** | Atomic Computational Tasks | YOLOv8 / FFmpeg / Gemini |
| **UI** | Visualization & Case Review | Vanilla JS / Glassmorphism |
| **Database** | Permanent Forensic Storage | SQLAlchemy (SQLite/PG) |

---
*Document Version: 5.0 (Forensic Master Reference)*
