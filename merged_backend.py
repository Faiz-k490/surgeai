#!/usr/bin/env python3
"""
merged_backend.py — Unified SurgeonAI backend (demo / hackathon).

Prefer production stack: `python -m backend.app.main` (real VLM + Loop A + Loop B).

Combines:
  Loop A: Webcam MJPEG stream + simulated step/warning events
  Loop B: Voice Q&A pipeline (wake word → RAG → LLM → TTS → MongoDB)

All events emitted over a single Flask-SocketIO server on /realtime namespace.
Cross-platform: macOS + Windows.
"""

from flask import Flask, Response, jsonify
from flask_socketio import SocketIO, emit
import cv2
import time
import threading
import random
import platform
import logging
import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("surgeai.merged")

# ─── Import Loop B modules ───────────────────────────────────────────────────
from audio_pipeline import (
    _build_recognizer_and_mic,
    _listen_for_wake_word,
    _capture_question,
)
from intelligence_pipeline import retrieve_context, generate_answer
from tts_pipeline import speak
from session_logger import _blocking_log

# ─── Camera ──────────────────────────────────────────────────────────────────

def open_camera():
    """Auto-detect first available USB webcam (indices 0-4)."""
    for idx in range(5):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)
            logger.info("[CAMERA] Opened camera index %d", idx)
            return cap
        cap.release()
    logger.error("[CAMERA] No camera found on indices 0-4.")
    return None

camera_lock = threading.Lock()
camera = None

def get_camera():
    global camera
    with camera_lock:
        if camera is None or not camera.isOpened():
            camera = open_camera()
    return camera

def generate_frames():
    """Stream live webcam as MJPEG. Retries if camera disconnects."""
    while True:
        cam = get_camera()
        if cam is None:
            time.sleep(1)
            continue
        ok, frame = cam.read()
        if not ok:
            with camera_lock:
                global camera
                if camera is not None:
                    camera.release()
                    camera = None
            time.sleep(0.5)
            continue
        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')

# ─── Flask + Socket.IO ───────────────────────────────────────────────────────

app = Flask(__name__)
app.config['SECRET_KEY'] = 'surgeai-merged'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Shared state for Loop A simulation
current_step = {"stepNumber": 1, "stepName": "Incision Preparation"}
metrics = {"fps": 30, "latency": 12}

def make_envelope(event_type, payload):
    return {
        "eventVersion": 1,
        "timestamp": datetime.now().isoformat(),
        "type": event_type,
        "payload": payload,
    }

# ─── HTTP Routes ─────────────────────────────────────────────────────────────

@app.route('/video')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/health')
def health():
    cam = get_camera()
    return jsonify({
        "ok": True,
        "camera": cam is not None and cam.isOpened(),
        "platform": platform.system(),
        "loops": {"a": True, "b": True},
    })

# ─── Socket.IO — /realtime namespace ─────────────────────────────────────────

@socketio.on('connect', namespace='/realtime')
def handle_connect():
    logger.info("[SOCKET] Client connected")
    emit('step_update', make_envelope("step_update", current_step))
    emit('system_health', make_envelope("system_health", metrics))

@socketio.on('disconnect', namespace='/realtime')
def handle_disconnect():
    logger.info("[SOCKET] Client disconnected")

# ─── Thread: Loop A — Step/Warning events ────────────────────────────────────

def loop_a_emitter():
    """Emit simulated surgical step events every 5 seconds."""
    while True:
        time.sleep(5)
        current_step["stepNumber"] = (current_step["stepNumber"] % 4) + 1
        steps = ["Incision Preparation", "Tool Selection", "Tissue Manipulation", "Closure"]
        current_step["stepName"] = steps[current_step["stepNumber"] - 1]

        socketio.emit('step_update',
            make_envelope("step_update", current_step.copy()),
            namespace='/realtime')

        if current_step["stepNumber"] == 2:
            socketio.emit('warning',
                make_envelope("warning", {"message": "Incorrect tool detected! Use scalpel #3"}),
                namespace='/realtime')
            time.sleep(3)
            socketio.emit('clear',
                make_envelope("clear", {"status": "nominal"}),
                namespace='/realtime')

        metrics["fps"] = 28 + random.randint(-2, 4)
        metrics["latency"] = 10 + random.randint(-2, 5)
        socketio.emit('system_health',
            make_envelope("system_health", metrics.copy()),
            namespace='/realtime')

# ─── Thread: Loop B — Voice Q&A pipeline ─────────────────────────────────────

def on_question_captured(question_text):
    """
    Callback fired by the audio pipeline when a question is captured.
    Runs RAG → LLM → emits qa_update → TTS → MongoDB log.
    """
    logger.info("[LOOP B] Question captured: %s", question_text)

    # 1. RAG retrieval
    try:
        context_chunks = retrieve_context(question_text)
    except Exception as exc:
        logger.error("[LOOP B] RAG error: %s", exc)
        context_chunks = []

    # 2. LLM generation
    try:
        answer = generate_answer(question_text, context_chunks)
    except Exception as exc:
        logger.error("[LOOP B] LLM error: %s", exc)
        socketio.emit('qa_update',
            make_envelope("qa_update", {
                "question": question_text,
                "answer": "",
                "error": str(exc),
            }),
            namespace='/realtime')
        return

    # 3. Broadcast qa_update to frontend
    socketio.emit('qa_update',
        make_envelope("qa_update", {
            "question": question_text,
            "answer": answer,
        }),
        namespace='/realtime')
    logger.info("[LOOP B] qa_update emitted")

    # 4. TTS — speak answer aloud (blocking, runs in this thread)
    try:
        speak(answer)
    except Exception as exc:
        logger.error("[LOOP B] TTS error: %s", exc)

    # 5. MongoDB log
    try:
        _blocking_log(question_text, answer)
    except Exception as exc:
        logger.error("[LOOP B] MongoDB log error: %s", exc)

def loop_b_audio():
    """
    Blocking audio listener loop.
    Detects 'Hey Surgeon' wake word, captures question, calls on_question_captured.
    Retries mic init if it fails.
    """
    while True:
        try:
            recognizer, mic = _build_recognizer_and_mic()
            break
        except Exception as exc:
            logger.error("[LOOP B] Mic init failed (%s) — retrying in 5s", exc)
            time.sleep(5)

    logger.info("[LOOP B] Audio pipeline started — say 'Hey Surgeon' to ask a question.")

    while True:
        try:
            if _listen_for_wake_word(recognizer, mic):
                question = _capture_question(recognizer, mic)
                if question:
                    # Run the full pipeline in a separate thread so audio
                    # listener isn't blocked during RAG + LLM + TTS
                    threading.Thread(
                        target=on_question_captured,
                        args=(question,),
                        daemon=True,
                    ).start()
        except Exception as exc:
            logger.error("[LOOP B] Audio loop error: %s", exc)
            time.sleep(1)

# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    PORT = 5001

    print(f"{'='*55}")
    print(f"  SurgeonAI Merged Backend — {platform.system()}")
    print(f"  Loop A: Webcam + Step Events (simulated)")
    print(f"  Loop B: Voice Q&A (Hey Surgeon → RAG → LLM → TTS)")
    print(f"  Video:     http://localhost:{PORT}/video")
    print(f"  Health:    http://localhost:{PORT}/health")
    print(f"  Socket.IO: http://localhost:{PORT}/realtime")
    print(f"{'='*55}")

    # Pre-open camera (triggers macOS permission dialog)
    cam = open_camera()
    if cam:
        logger.info("[CAMERA] Live webcam ready — %dx%d",
            int(cam.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        camera = cam
    else:
        logger.warning("[CAMERA] No webcam detected. Plug in your Logi Brio and restart.")

    # Start Loop A (step events) in background
    threading.Thread(target=loop_a_emitter, daemon=True).start()

    # Start Loop B (audio Q&A) in background
    threading.Thread(target=loop_b_audio, daemon=True).start()

    # Run the Flask-SocketIO server
    socketio.run(app, host='0.0.0.0', port=PORT, debug=False)
