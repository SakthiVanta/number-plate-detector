# ALPR Pro v2.3 - Agentic Edition 🚀

**ALPR Pro v2.3** is an enterprise-grade AI traffic analytics suite featuring **Agentic Workflows** and **Collage-Batching Intelligence**. It is designed to maximize detection rates while minimizing operational costs.

---

## 🌟 What's New in v2.3?

### 🧩 Collage-Batching (API Cost Fix)
By stitching 10 detection crops into a single high-resolution grid, we reduce Gemini API calls by **90%**. This provides the AI with comparative context, leading to superior accuracy in vehicle color and model identification.

### 🤖 Agentic AI Pattern
The system evolves from a linear pipeline to an **Agentic Workflow**:
- **Capture Manager**: Ensures no vehicle is missed, even in high-traffic scenarios.
- **Metadata Agent**: Automates extraction of deep vehicle metrics (Color/Make/Model).
- **QC Agent**: Acts as the "Supreme Court," validating local OCR results against Cloud AI.

### 🎯 High-Sensitivity Tuning
- **0.25 Threshold**: Optimized for capturing distant or partially occluded vehicles.
- **15-Frame Persistence**: Intelligent "Filter Agent" ensures plates are captured at the sharpest possible moment.

---

## 🛠️ Getting Started

1. **Configure Environment**: Set `COLLAGE_SIZE=10` and `SENSITIVITY=HIGH` in `.env`.
2. **Start Infrastructure**: Ensure Redis and Celery are active.
3. **Analyze**: Use the `/api/v2/process` endpoint or the updated dashboard.

---

## 📖 Technical Specs
For in-depth architecture, database schemas, and the "Manager-Worker" AI pattern details, see **[documentation.md](./documentation.md)**.
