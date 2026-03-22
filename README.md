# SurgeAI

Real-time surgical training assistant with AR overlays, powered by YOLOv8 object detection and OpenCV spatial analysis.

## Architecture

| Component | Path | Port |
|-----------|------|------|
| **Backend** | `backend/server.py` | 5000 |
| **Frontend HUD** | `surgeon-hud/` | 5173 |

The backend runs a live vision pipeline: **YOLOv8n** detects objects (banana = patient tissue, knife = scalpel, scissors/fork = forceps), **OpenCV** extracts surgical features (incision zone, tool angles), and a **6-phase state machine** orchestrates the demo flow. Results stream to the React HUD via Socket.IO and MJPEG.

## Quick start

### 1. Backend

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r backend\requirements.txt
python backend\server.py
```

### 2. Frontend HUD

```powershell
cd surgeon-hud
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

## Physical setup

Place these objects in front of your webcam:

- **Banana** with a red marker line drawn on it (patient tissue + incision zone)
- **Knife** (scalpel)
- **Scissors or fork** (forceps/clamps)

## 6-Phase demo flow

| Phase | Name | Trigger |
|-------|------|---------|
| 0 | Idle | Scanning for objects |
| 1 | Target Acquired | Banana detected |
| 2 | Tool Tracking | Banana + knife both visible |
| 3 | Incision Mode | Scalpel near tissue + red zone visible |
| 4 | Clamping | 6 seconds of sustained incision |
| 5 | Complete | Clamps brought near tissue |

## Configuration

Edit `backend/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 5000 | Backend server port |
| `YOLO_MODEL` | yolov8n.pt | Path to YOLO weights |
| `YOLO_CONFIDENCE` | 0.35 | Detection confidence threshold |
| `BRIO_CAMERA_INDEX` | 0 | Camera device index |
| `SOCKET_NAMESPACE` | /realtime | Socket.IO namespace |
| `FRONTEND_ORIGIN` | http://localhost:5173 | CORS origin for the HUD |

## Endpoints

| URL | Description |
|-----|-------------|
| `http://localhost:5000/video` | MJPEG live video stream |
| `http://localhost:5000/health` | Health check (camera + YOLO status) |

## Tech stack

- **Backend:** Python 3.11, Flask, Flask-SocketIO, OpenCV, YOLOv8 (ultralytics), NumPy
- **Frontend:** React, Vite, Zustand, Framer Motion, Socket.IO client, Tailwind CSS
