# ALPR Pro v5.0: The Definitive Technical Manual 🧠🛡️🕵️

This manual provides an exhaustive technical breakdown of the **ALPR Pro v5.0 Hybrid Neuro-Symbolic Hub**. It is designed for developers, forensic auditors, and system architects to understand every single component, from the low-level CV tools to the high-level Agentic reasoning.

---

## 🛠️ 1. Technical Stack & Core Dependencies

| Library | Role | Version Detail |
| :--- | :--- | :--- |
| **FastAPI** | Core ASYNC Web Framework | Production-grade API backbone |
| **SQLAlchemy** | Database ORM | Handles SQLite/PostgreSQL logic |
| **Ultralytics** | YOLOv11 Engine | Object detection & Multi-object tracking |
| **EasyOCR / Paddle** | Local OCR Engines | High-speed plate recognition (Edge) |
| **Gemini 1.5 Pro** | Agentic Cloud Brain | Deep metadata & Forensic validation |
| **Celery** | Distributed Task Queue | Asynchronous background processing |
| **Redis** | Message Broker | State management for background workers |
| **OpenCV** | Image Manipulation | Frame processing & Collage generation |
| **FFmpeg** | Video Conditioning | CFR enforcement & Stream sharpening |

---

## 📁 2. Detailed Project Anatomy

### **`/app` - The Logic Hub**
- **`main.py`**: Entry point. Mounts routers, static files, and global middleware.
- **`worker.py`**: The heavy-lifting consumer. Runs the `process_video_task` logic.
- **`api/`**: 
    - `auth.py`: JWT issuing and user registration.
    - `videos.py`: CRUD for video assets and streaming.
    - `detections.py`: SQLAlchemy-powered forensic search.
    - `v2_api.py`: Telemetry (Agents, Costs, Analytics).
    - `v5_api.py`: Forensic Case Feed & Agent Logs.
- **`agents/`**:
    - `orchestrator.py`: Logic for deciding AI re-check paths.
    - `auditor.py`: Cross-validator for classification vs plate data.
- **`tools/`**: Specialized MCP (Model Context Protocol) tool wrappers for YOLO, OCR, and Super-Res.

### **`/frontend` - The Visual Hub**
- **`assets/` & `css/`**: Core branding and Glassmorphism styling.
- **`js/api.js`**: Global Axios-like interceptor for JWT handling.
- **`js/auth.js`**: Login/Register state machine.
- **`js/app.js`**: Real-time dashboard engine (1,000+ lines of logic).

---

## 🔐 3. System Access & Authentication

### **Default Admin Credentials**
The system is pre-seeded with a master administrator for initial configuration.
- **Email**: `admin@alpr.pro`
- **Password**: `admin123`
- **Seeding Script**: `app/db/seed.py` (Resets DB and creates admin).

### **Auth Flow**
1. User submits credentials via `auth.html`.
2. Backend validates via `app/core/security.py`.
3. A JWT token is issued and stored in `localStorage` by `api.js`.
4. The `Auth Guard` in `app.js` ensures every view-switch verifies the token.

---

## 🖥️ 4. Page Registry & UI Features

### **1. Landing Hub (`index.html`)**
- System branding and quick-start links.
- Terminal-style visual feedback.

### **2. Forensic Command Center (`dashboard.html`)**
- **System Readiness**: Real-time status of CUDA (GPU), Disk space, and ROI masks.
- **Parallel Analysis**: Drag-and-drop uploader supporting multi-gigabyte video files.
- **Master Task List**: Tracks active background analysis jobs with "Live Terminal" log viewing.

### **3. Forensic Explorer (`detections` view)**
- **High-Sensitivity Search**: Filter by plate, car color, or vehicle make.
- **Data Pagination**: Optimized for 100,000+ detection records.
- **Rich Detection Cards**: Expandable views showing forensic collages and agent thought logs.

### **4. Agent Factory (`agents` view)**
- **Telemetry Console**: FPS, buffer status, and cost estimation for Gemini API.
- **Live Tuning**: Adjust batch sizes (Collage 3x3 vs 4x4) and detection sensitivity without restart.

### **5. Forensic Audit Machine (`Analysis Modal`)**
- **Traffic Density Charts**: Visual distribution of vehicle flow.
- **Safety Violation Ledger**: Specific counts for Helmet vs No-Helmet (v3.1+ feature).

---

## 🏗️ 5. Forensic Data Models (Registry Schema)

Every record tracks forensic provenance:
- **`User`**: Root owner of assets.
- **`Video`**: Tracks filename, status, and rich analytics JSON.
- **`VehicleDetection`**: Atomic detection. Fields: `best_frame`, `blur_score`, `crop_path`, `is_validated`.
- **`DetectionBatch`**: Groups detections for AI collage processing. Fields: `collage_path`, `raw_ai_json`, `cost_estimate`.
- **`AgentLog`**: The "Case Reasoning" table. Tracks `agent_name`, `action_taken`, and `reasoning`.

---

## � 6. The Agentic Pipeline Workflow

1. **Ingest**: Standardize stream via FFmpeg (CFR + Sharpen).
2. **Detect**: YOLOv11 + ByteTrack identifies unique vehicles.
3. **Capture**: Orchestrator buffers crops until `COLLAGE_SIZE` is reached.
4. **Stitch**: OpenCV generates a high-res forensic collage.
5. **Verify**: Gemini 1.5 Pro performs multi-modal validation (Vision + Logic).
6. **Audit**: QC Agent identifies discrepancies and commits final forensic proof to `AgentLog`.

---

## 🧪 7. Utility & Forensic Scripts

- `migrate_v30.py`: Database schema evolution.
- `diag_db.py`: Low-level data integrity inspector.
- `test_roi.py`: ROI Mask visualizer.
- `verify_v239.py`: Full system sanity check.

---
*Manual Version: 5.0.3 (Definitive Master Reference)*
