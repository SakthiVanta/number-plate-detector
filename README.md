# ALPR Pro v5.5 - Multi-Tiered Agentic Forensic Framework 👁️🛡️

> **The "Triage & Truth" Edition**  
> *Next-Gen Forensic Traffic Analytics powered by Neuro-Symbolic Agents.*

**ALPR Pro v5.5** is not just an ALPR (License Plate Recognition) system—it is a forensic truth engine. It combines ultra-fast edge vision (YOLOv11) with a council of AI Agents (Gemini Pro/Flash) to "argue" the validity of every detection. The result is pure forensic data with explainable confidence.

---

## ⚡ v5.5 Key Innovations

### 1. The Forensic Confidence Formula (FCF) ⚗️
We don't just "detect" plates; we mathematically prove them. Every vehicle track is scored before costing a cent in API calls.
$$ FCF = (Stability \times 0.4) + (OCR_{Conf} \times 0.4) + (VisualRank \times 0.2) $$
-   **Visual Rank ($V_r$)**: A new computer vision metric that scores image "forensic value" (Sharpness + Contrast) to prevent garbage-in-garbage-out.
-   **Stability Score ($S$)**: Measures how consistent the OCR result is across multiple frames in a track.

### 2. The Decision Matrix (Cost-Optimized Triage) 🚦
Smart routing saves 90% of cloud costs while maximizing accuracy.
-   **🟢 Instant Commit (FCF > 0.90)**: "Obvious" plates (high stability & clarity) are committed locally. **Cost: $0.00**.
-   **🟡 Validation Agent (FCF 0.65 - 0.90)**: Sends crop to **Gemini Flash** (Fast/Cheap) to check general legibility and make/model match.
-   **🔴 Forensic Auditor (FCF < 0.65)**: The "Hard Cases". Sends to **Gemini Pro** (Deep Reasoning) for a pixel-by-pixel forensic audit.

### 3. The 4-Agent Architecture 🤖
1.  **Ingestion Agent (Edge)**: Local YOLOv11 + Regex + FCF Filter. Discards noise instantly.
2.  **Validation Agent**: "Is this a readable plate?" (Fast check).
3.  **Auditor Agent**: "What is the truth here?" (Deep check for occlusion, glare, ghosts).
4.  **Logic Bridge**: The "Judge". A symbolic arbitrator that cross-references AI opinions with historical data (e.g., "This car was seen 5 mins ago") to prevent hallucinations and enforce consistency.

---

## 🚀 Features

*   **Real-Time "Matrix" Dashboard**: Live WebSocket log streaming directly from the brain of the agents to your UI.
*   **Zero-Latency Mode**: Run completely standalone without Redis/Celery for simpler deployments.
*   **Historic Stalker Detection**: Automatically flags vehicles seen repeatedly >5 times in 24 hours.
*   **Forensic Search**: Search by Plate, Color, Make, or even "Partial Plate" queries.
*   **Setup Wizard**: Auto-secure your instance on first launch.

---

## 🛠️ System Architecture

*   **Vision Core**: `YOLOv11` (Detection) + `OpenCV` (Processing)
*   **Intelligence**: `Google Gemini 1.5 Pro` (Auditor) + `Gemini 1.5 Flash` (Validator)
*   **Backend**: `FastAPI` (Async Python)
*   **Database**: `SQLite` (Default) / PostgreSQL (Supported)
*   **Frontend**: Vanilla JS (Glassmorphism Design)

---

## 📖 Getting Started

### 1. Prerequisites
*   Python 3.10+
*   (Optional) Redis (for async background workers). *Not required for default LITE mode.*

### 2. Installation
```powershell
# Clone the repository
git clone https://github.com/YourRepo/alpr-pro.git
cd alpr-pro

# Install dependencies
pip install -r requirements.txt
```

> **Note on Upgrades**: 
> *   `basicsr` / `realesrgan` are currently disabled by default due to Python 3.13 compatibility. The system automatically falls back to OpenCV enhancers.
> *   We use **YOLOv11** (`yolo11n.pt`) for superior small-object detection. It will auto-download on first run.

### 3. Usage

#### Option A: Standalone Mode (Recommended for testing)
Runs everything in a single process. No Redis required.
```powershell
python main.py
```
*Access the dashboard at: `http://localhost:8000`*

#### Option B: Scalable Mode (Production)
Requires Redis installed and running.
1.  Set `USE_CELERY = True` in `app/core/config.py`.
2.  Start the API:
    ```powershell
    python main.py
    ```
3.  Start the Worker:
    ```powershell
    python -m celery -A app.worker worker --loglevel=info --pool=solo
    ```

---

## 🔐 Credentials
*   **Default Admin**:
    *   **Email**: `admin@alpr.pro`
    *   **Password**: `admin123`
*   **Forensic Access**: All detections are hashed and virtually signed for chain-of-custody.

---

## 📚 Documentation
For a deep dive into the code structure, database schema, and agent prompts, see the **[Master Technical Manual (documentation.md)](./documentation.md)**.
