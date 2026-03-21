#!/usr/bin/env python3
"""
SurgeonAI Frontend Backend — Real Webcam Feed + Socket.IO Events
Cross-platform: macOS + Windows. Plug in USB webcam and go.
"""
from flask import Flask, Response, jsonify
from flask_socketio import SocketIO, emit
import cv2
import time
import threading
import random
import platform
from datetime import datetime

# ---------------------------------------------------------------------------
# Camera — tries indices 0-4 until it finds one that opens
# ---------------------------------------------------------------------------
def open_camera():
    """Auto-detect first available USB webcam. Works on Mac and Windows."""
    for idx in range(5):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)
            print(f"[CAMERA] Opened camera index {idx}")
            return cap
        cap.release()
    print("[CAMERA] ERROR: No camera found on indices 0-4. Plug in your webcam.")
    return None

camera_lock = threading.Lock()
camera = None

def get_camera():
    global camera
    with camera_lock:
        if camera is None or not camera.isOpened():
            camera = open_camera()
    return camera

# ---------------------------------------------------------------------------
# Flask + Socket.IO
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'surgeai-dev'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Shared state
current_step = {"stepNumber": 1, "stepName": "Incision Preparation"}
metrics = {"fps": 30, "latency": 12}

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def generate_frames():
    """Stream live webcam as MJPEG. Retries camera if disconnected."""
    while True:
        cam = get_camera()
        if cam is None:
            # No camera — wait and retry
            time.sleep(1)
            continue
        ok, frame = cam.read()
        if not ok:
            # Camera read failed — reset and retry
            with camera_lock:
                global camera
                if camera is not None:
                    camera.release()
                    camera = None
            time.sleep(0.5)
            continue
        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')

@app.route('/video')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/health')
def health():
    cam = get_camera()
    return jsonify({"ok": True, "camera": cam is not None and cam.isOpened(), "platform": platform.system()})

# ---------------------------------------------------------------------------
# Socket.IO — /realtime namespace
# ---------------------------------------------------------------------------
@socketio.on('connect', namespace='/realtime')
def handle_connect():
    print(f"[SOCKET] Client connected")
    emit('step_update', {
        "eventVersion": 1,
        "timestamp": datetime.now().isoformat(),
        "type": "step_update",
        "payload": current_step
    })
    emit('system_health', {
        "eventVersion": 1,
        "timestamp": datetime.now().isoformat(),
        "type": "system_health",
        "payload": metrics
    })

@socketio.on('disconnect', namespace='/realtime')
def handle_disconnect():
    print(f"[SOCKET] Client disconnected")

def emit_loop():
    """Emit simulated surgical events every 5 seconds."""
    while True:
        time.sleep(5)
        current_step["stepNumber"] = (current_step["stepNumber"] % 4) + 1
        steps = ["Incision Preparation", "Tool Selection", "Tissue Manipulation", "Closure"]
        current_step["stepName"] = steps[current_step["stepNumber"] - 1]

        socketio.emit('step_update', {
            "eventVersion": 1, "timestamp": datetime.now().isoformat(),
            "type": "step_update", "payload": current_step.copy()
        }, namespace='/realtime')

        if current_step["stepNumber"] == 2:
            socketio.emit('warning', {
                "eventVersion": 1, "timestamp": datetime.now().isoformat(),
                "type": "warning", "payload": {"message": "Incorrect tool detected! Use scalpel #3"}
            }, namespace='/realtime')
            time.sleep(3)
            socketio.emit('clear', {
                "eventVersion": 1, "timestamp": datetime.now().isoformat(),
                "type": "clear", "payload": {}
            }, namespace='/realtime')

        metrics["fps"] = 28 + random.randint(-2, 4)
        metrics["latency"] = 10 + random.randint(-2, 5)
        socketio.emit('system_health', {
            "eventVersion": 1, "timestamp": datetime.now().isoformat(),
            "type": "system_health", "payload": metrics.copy()
        }, namespace='/realtime')

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    PORT = 5001
    print(f"{'='*50}")
    print(f"  SurgeonAI Backend — {platform.system()}")
    print(f"  Video:     http://localhost:{PORT}/video")
    print(f"  Health:    http://localhost:{PORT}/health")
    print(f"  Socket.IO: http://localhost:{PORT}/realtime")
    print(f"{'='*50}")

    # Pre-open camera so macOS triggers the permission dialog NOW
    cam = open_camera()
    if cam:
        print(f"[CAMERA] Live webcam ready — {int(cam.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
        camera = cam
    else:
        print("[CAMERA] WARNING: No webcam detected. Plug in your Logi Brio and restart.")

    threading.Thread(target=emit_loop, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=PORT, debug=False)
