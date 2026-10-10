# SurgeAI

Real-time surgical training assistant with AR overlays, powered by YOLOv8 object detection, OpenCV spatial analysis, and persistent object tracking.

## Quick Start

### Backend

```
run_backend.bat
```

Or manually:

```
.venv\Scripts\activate
pip install -r backend\requirements.txt
python backend\server.py
```

### Frontend

```
cd surgeon-hud
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

## Physical Setup

Place these objects in front of your Logitech BRIO 100 webcam:

- **Banana** with a red marker line drawn on it (patient tissue + incision zone)
- **Knife** on the RIGHT side (scalpel)
- **Scissors or fork** on the LEFT side (forceps/clamps)

## Configuration

Backend: `backend/.env`

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 5000 | Backend server port |
| `YOLO_MODEL` | yolov8n.pt | YOLO weights file |
| `YOLO_CONFIDENCE` | 0.3 | Detection confidence threshold |
| `CAMERA_INDEX` | 1 | External webcam device index |
| `SOCKET_NAMESPACE` | /realtime | Socket.IO namespace |
| `FRONTEND_ORIGIN` | http://localhost:5173 | CORS origin |

Frontend: `surgeon-hud/.env`

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE` | http://localhost:5000 | Backend URL |
| `VITE_SOCKET_NAMESPACE` | /realtime | Socket.IO namespace |

## Endpoints

Voice completion requires an explicit statement such as "I'm done" or "session complete".
The wake phrase and short acknowledgments such as "Okay, I am done now, thanks" are accepted.
Questions, negations, and partial-task statements such as "I am done with setup" do not end
the session. Run the offline parser tests from the repository root with
`PYTHONPATH=backend python -m unittest discover -s backend/tests -v`.

| URL | Description |
|-----|-------------|
| `http://localhost:5000/video` | MJPEG live video stream |
| `http://localhost:5000/health` | Health check (camera + YOLO status) |

## Tech Stack

- **Backend:** Python 3.11, Flask, Flask-SocketIO, OpenCV, YOLOv8 (ultralytics), NumPy
- **Frontend:** React, Vite, Zustand, Framer Motion, Socket.IO client, Tailwind CSS
