#!/usr/bin/env python3
"""
SurgeonAI — 6-Phase Demo Backend
Live webcam + YOLOv8 + OpenCV red-rectangle detection + State Machine + Socket.IO

Run:  python3 simulate_demo.py
"""

import cv2
import math
import time
import logging
import threading
import numpy as np
import argparse
from flask import Flask, Response, jsonify
from flask_socketio import SocketIO, emit

# ── YOLO (graceful import) ────────────────────────────────────────────────────
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

from backend.app.vision.smart_crop import SmartCropper
from backend.app.vision.gemini_client import GeminiVisionClient
from backend.app.core.settings import load_settings
from backend.app.loop_b.tts_pipeline import speak

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("surgeai.demo")

# ── Constants ─────────────────────────────────────────────────────────────────
PORT = 5001
NAMESPACE = "/realtime"

BANANA_ID = 46
KNIFE_ID = 43
SCISSORS_ID = 76
FORK_ID = 42
ALLOWED_CLASSES = [BANANA_ID, KNIFE_ID, SCISSORS_ID, FORK_ID]

LABEL_MAP = {
    BANANA_ID: "Patient Tissue",
    KNIFE_ID: "Scalpel",
    SCISSORS_ID: "Forceps",
    FORK_ID: "Forceps",
}
LABEL_COLORS = {
    "Patient Tissue": "#22d3ee",
    "Scalpel": "#ef4444",
    "Forceps": "#facc15",
}


# ── Utility functions ─────────────────────────────────────────────────────────

def deviation_to_hex(t):
    """Map 0→green, 0.5→yellow, 1→red."""
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        r = int(255 * (t * 2))
        g = 255
    else:
        r = 255
        g = int(255 * (1 - (t - 0.5) * 2))
    return f"#{r:02x}{g:02x}00"


def bbox_center(bbox):
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def pt_distance(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def scalpel_angle_from_bbox(bbox_xyxy):
    """Orientation from bbox aspect ratio. 0=horizontal, 90=vertical."""
    x1, y1, x2, y2 = bbox_xyxy
    w, h = x2 - x1, y2 - y1
    if w < 1 and h < 1:
        return 0.0
    return math.degrees(math.atan2(abs(h), abs(w)))


# ── OpenCV: Red Rectangle Detection ──────────────────────────────────────────

def detect_red_rectangle(frame, bbox_xyxy):
    """Find red marker rectangle inside banana bbox.
    Returns (center_x, center_y, angle_deg, rect_points_abs) or None.
    """
    try:
        x1, y1, x2, y2 = [int(v) for v in bbox_xyxy]
        # Clamp to frame bounds
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

        # Red wraps around hue 0/180
        m1 = cv2.inRange(hsv, np.array([0, 70, 50]), np.array([12, 255, 255]))
        m2 = cv2.inRange(hsv, np.array([160, 70, 50]), np.array([180, 255, 255]))
        red_mask = cv2.bitwise_or(m1, m2)

        # Morphological cleanup
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, k, iterations=2)
        red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, k, iterations=1)

        if cv2.countNonZero(red_mask) < 80:
            return None

        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < 40:
            return None

        rect = cv2.minAreaRect(largest)
        center, size, angle = rect

        # Normalize angle to long-axis orientation
        if size[0] < size[1]:
            angle += 90

        # Absolute coordinates
        abs_cx = x1 + center[0]
        abs_cy = y1 + center[1]

        box_pts = cv2.boxPoints(rect).astype(np.float64)
        box_pts[:, 0] += x1
        box_pts[:, 1] += y1

        return (abs_cx, abs_cy, angle, box_pts)
    except Exception as exc:
        logger.debug("Red rect detection failed: %s", exc)
        return None


# ── DemoOrchestrator (State Machine) ──────────────────────────────────────────

class DemoOrchestrator:
    """6-phase surgical demo state machine with debounced transitions."""

    DEBOUNCE = 6              # consecutive frames to trigger transition
    INCISION_DURATION = 6.0   # seconds of sustained incision before Phase 3→4
    COMPLETE_DELAY = 3.0      # seconds before showing success overlay in Phase 5

    VOICE_PROMPTS = {
        1: "Patient tissue detected. Please pick up your scalpel.",
        2: "Scalpel acquired. Make your incision along the highlighted zone. Maintain a 30 to 60 degree angle.",
        4: "Incision complete. Put down the scalpel and pick up your clamps.",
        5: "Excellent. Peel the skin back.",
    }

    def __init__(self):
        self.phase = 0
        self._deb_count = 0
        self._deb_target = None
        self._voice_queue = None
        self._voices_sent = set()
        self._incision_start = None
        self._complete_time = None

    def _try_advance(self, target, condition):
        if not condition:
            if self._deb_target == target:
                self._deb_count = max(0, self._deb_count - 1)
            return False
        if self._deb_target == target:
            self._deb_count += 1
        else:
            self._deb_target = target
            self._deb_count = 1
        if self._deb_count >= self.DEBOUNCE:
            self.phase = target
            self._deb_count = 0
            self._deb_target = None
            if target in self.VOICE_PROMPTS and target not in self._voices_sent:
                self._voice_queue = self.VOICE_PROMPTS[target]
                self._voices_sent.add(target)
            logger.info("▶ Phase → %d", target)
            return True
        return False

    def process(self, detections, red_rect, fh, fw):
        """Process one frame. Returns frame_state dict."""
        warning = None
        angle_data = None
        ar_elements = []

        # Shorthand lookups
        banana = next((d for d in detections if d["cid"] == BANANA_ID), None)
        knife = next((d for d in detections if d["cid"] == KNIFE_ID), None)
        clamp = next((d for d in detections if d["cid"] in (SCISSORS_ID, FORK_ID)), None)

        # Build ar_elements for every detected object
        for d in detections:
            lbl = LABEL_MAP.get(d["cid"], "Unknown")
            x1, y1, x2, y2 = d["box"]
            ar_elements.append({
                "type": "box",
                "x": x1 / fw, "y": y1 / fh,
                "width": (x2 - x1) / fw, "height": (y2 - y1) / fh,
                "color": LABEL_COLORS.get(lbl, "#22d3ee"),
                "label": lbl,
                "confidence": round(d["conf"], 2),
            })

        # Red rect overlay (Phase 2+)
        if red_rect and self.phase >= 2:
            pts = [(p[0] / fw, p[1] / fh) for p in red_rect[3]]
            ar_elements.append({
                "type": "polygon",
                "points": pts,
                "color": "#ef4444",
                "label": "Incision Zone",
            })

        # ── Phase transitions ─────────────────────────────────────────────
        if self.phase == 0:
            self._try_advance(1, banana is not None)

        elif self.phase == 1:
            self._try_advance(2, banana is not None and knife is not None)

        elif self.phase == 2:
            if banana and knife:
                bc = bbox_center(banana["box"])
                kc = bbox_center(knife["box"])
                diag = math.sqrt(fw ** 2 + fh ** 2)
                close = pt_distance(bc, kc) < diag * 0.30
                if self._try_advance(3, close and red_rect is not None):
                    self._incision_start = time.time()

        elif self.phase == 3:
            if knife and red_rect:
                rcx, rcy, rangle, _ = red_rect
                s_angle = scalpel_angle_from_bbox(knife["box"])
                raw_diff = abs(s_angle - rangle)
                if raw_diff > 90:
                    raw_diff = 180 - raw_diff

                if 30 <= raw_diff <= 60:
                    status = "Optimal"
                elif raw_diff > 60:
                    status = "Too Steep"
                else:
                    status = "Too Shallow"

                angle_data = {"approach_angle": int(round(raw_diff)), "status": status}

                if raw_diff > 60:
                    warning = "CRITICAL: Angle too steep! You are piercing crucial arteries!"

                # Distance deviation → color
                kc = bbox_center(knife["box"])
                dist = pt_distance(kc, (rcx, rcy))
                deviation = min(1.0, dist / max(200.0, fw * 0.15))
                trace_color = deviation_to_hex(deviation)

                ar_elements.append({
                    "type": "line",
                    "x1": kc[0] / fw, "y1": kc[1] / fh,
                    "x2": rcx / fw, "y2": rcy / fh,
                    "color": trace_color,
                })

                # Auto-advance after sustained incision
                if self._incision_start and (time.time() - self._incision_start) > self.INCISION_DURATION:
                    self._try_advance(4, True)
            else:
                # Lost scalpel during incision — reset timer
                if self._incision_start:
                    self._incision_start = time.time()

        elif self.phase == 4:
            if clamp and banana:
                bc = bbox_center(banana["box"])
                cc = bbox_center(clamp["box"])
                diag = math.sqrt(fw ** 2 + fh ** 2)
                if self._try_advance(5, pt_distance(bc, cc) < diag * 0.35):
                    self._complete_time = time.time()

        elif self.phase == 5:
            if self._complete_time and (time.time() - self._complete_time) > self.COMPLETE_DELAY:
                ar_elements.append({"type": "success_overlay"})

        # Consume voice
        voice = self._voice_queue
        self._voice_queue = None

        return {
            "current_phase": self.phase,
            "voice_prompt": voice,
            "warning": warning,
            "ar_elements": ar_elements,
            "angle_data": angle_data,
        }


# ── Camera ────────────────────────────────────────────────────────────────────

camera_lock = threading.Lock()
camera = None
latest_frame = None
latest_frame_lock = threading.Lock()

# ── Smart crop state (shared between vision_loop and MJPEG generator) ─────────
cropper = SmartCropper(jpeg_quality=80, ema_alpha=0.08)
cropper_lock = threading.Lock()
latest_yolo_boxes: list = []
latest_yolo_boxes_lock = threading.Lock()


def open_camera(target_idx=None):
    indices = [target_idx] if target_idx is not None else range(5)
    for idx in indices:
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)
            logger.info("Opened camera index %d", idx)
            return cap
        cap.release()
    logger.error("No camera found on indices %s", list(indices))
    return None


def capture_thread(target_idx=None):
    """High-FPS capture thread — feeds MJPEG and frame buffer."""
    global camera, latest_frame
    while True:
        with camera_lock:
            if camera is None or not camera.isOpened():
                camera = open_camera(target_idx)
            cap = camera
        if cap is None:
            time.sleep(1)
            continue
        ok, frame = cap.read()
        if not ok:
            with camera_lock:
                if camera is not None:
                    camera.release()
                    camera = None
            time.sleep(0.5)
            continue
        with latest_frame_lock:
            latest_frame = frame.copy()
        time.sleep(0.015)  # ~60fps capture ceiling


def generate_mjpeg():
    """MJPEG generator for /video endpoint — streams 512x512 banana-zoomed crop."""
    while True:
        with latest_frame_lock:
            frame = latest_frame
        if frame is None:
            time.sleep(0.05)
            continue
        with latest_yolo_boxes_lock:
            boxes = list(latest_yolo_boxes)
        try:
            with cropper_lock:
                jpeg = cropper.detect_and_crop(frame, boxes)
        except Exception:
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            jpeg = buf.tobytes()
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
        time.sleep(0.033)  # ~30 fps mjpeg


# ── Flask + Socket.IO ─────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"] = "surgeai-demo"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


@app.route("/video")
def video_feed():
    return Response(generate_mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/health")
def health():
    with camera_lock:
        cam_ok = camera is not None and camera.isOpened()
    return jsonify({"ok": True, "camera": cam_ok, "yolo": YOLO_AVAILABLE})


@socketio.on("connect", namespace=NAMESPACE)
def on_connect():
    logger.info("[Socket] Client connected")
    emit("system_health", {"payload": {"loopAAlive": True, "fps": 30, "latency": 0}})


@socketio.on("disconnect", namespace=NAMESPACE)
def on_disconnect():
    logger.info("[Socket] Client disconnected")


# ── Vision Loop ───────────────────────────────────────────────────────────────

def vision_loop():
    """YOLO + OpenCV + DemoOrchestrator → Socket.IO frame_state."""
    # Load YOLO
    model = None
    if YOLO_AVAILABLE:
        try:
            model = YOLO("yolov8n.pt")
            logger.info("YOLOv8n loaded")
        except Exception as e:
            logger.error("YOLO load failed: %s", e)

    orchestrator = DemoOrchestrator()
    fps_ema = 0.0

    while True:
        with latest_frame_lock:
            frame = latest_frame
        if frame is None:
            time.sleep(0.05)
            continue

        t0 = time.time()
        fh, fw = frame.shape[:2]

        # ── YOLO Detection ────────────────────────────────────────────────
        detections = []
        if model is not None:
            results = model.predict(
                frame, conf=0.35, verbose=False, imgsz=640, classes=ALLOWED_CLASSES
            )
            for r in results:
                if r.boxes is None:
                    continue
                for i in range(len(r.boxes)):
                    cid = int(r.boxes.cls[i].item())
                    conf = float(r.boxes.conf[i].item())
                    box = r.boxes.xyxy[i].tolist()
                    detections.append({"cid": cid, "conf": conf, "box": box})

        # ── Publish normalized boxes for smart crop ───────────────────────
        norm_boxes = []
        for d in detections:
            x1, y1, x2, y2 = d["box"]
            norm_boxes.append({
                "x": x1 / fw,
                "y": y1 / fh,
                "width": (x2 - x1) / fw,
                "height": (y2 - y1) / fh,
                "label": LABEL_MAP.get(d["cid"], "Unknown"),
                "confidence": d["conf"],
            })
        with latest_yolo_boxes_lock:
            latest_yolo_boxes.clear()
            latest_yolo_boxes.extend(norm_boxes)

        # ── Red rect detection (only when banana present) ─────────────────
        red_rect = None
        banana_det = next((d for d in detections if d["cid"] == BANANA_ID), None)
        if banana_det is not None:
            red_rect = detect_red_rectangle(frame, banana_det["box"])

        # ── DemoOrchestrator ──────────────────────────────────────────────
        state = orchestrator.process(detections, red_rect, fh, fw)

        # ── Metrics ───────────────────────────────────────────────────────
        dt = max(1e-6, time.time() - t0)
        fps_ema = 0.85 * fps_ema + 0.15 * (1.0 / dt)
        latency_ms = int(dt * 1000)

        # ── Emit ──────────────────────────────────────────────────────────
        socketio.emit("frame_state", {"payload": state}, namespace=NAMESPACE)
        socketio.emit(
            "system_health",
            {"payload": {"loopAAlive": True, "fps": round(fps_ema, 1), "latency": latency_ms}},
            namespace=NAMESPACE,
        )

        # Throttle to ~10-15 Hz (YOLO on CPU is the bottleneck anyway)
        elapsed = time.time() - t0
        if elapsed < 0.066:
            time.sleep(0.066 - elapsed)


# ── Narrator Thread (Gemini 2.0 Flash) ──────────────────────────────────────

def narrator_thread(model_override=None):
    """Gemini 1 FPS narrator for testing purposes."""
    import sys
    if sys.platform == "win32":
        import pythoncom
        pythoncom.CoInitialize()

    settings = load_settings()
    if model_override:
        settings.gemini_model = model_override
        
    client = GeminiVisionClient(settings)
    if not client.ping():
        logger.error("[Narrator] Gemini client failed to initialize. Check GEMINI_API_KEY.")
        return

    logger.info("[Narrator] Narrator thread started (1 frame / 10s) using %s", client.model)
    while True:
        time.sleep(10.0)
        
        with latest_frame_lock:
            frame = latest_frame
        
        if frame is None:
            continue
            
        with latest_yolo_boxes_lock:
            boxes = list(latest_yolo_boxes)
            
        try:
            with cropper_lock:
                jpeg = cropper.detect_and_crop(frame, boxes)
            narration = client.narrate_scene(jpeg)
            logger.info("[Narrator] %s", narration)
            speak(narration)  # Play the text to speech audio synchronously
        except Exception as e:
            logger.warning("[Narrator] Error: %s", e)

# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SurgeonAI Demo Backend")
    parser.add_argument("--narrate", action="store_true", help="Enable 1 FPS Gemini VLM narrator")
    parser.add_argument("--camera", type=int, default=None, help="Specific camera index to use")
    parser.add_argument("--model", type=str, default=None, help="Gemini model to use for narrator (default: from .env)")
    parser.add_argument("--list-cameras", action="store_true", help="List available cameras and exit")
    args = parser.parse_args()

    if args.list_cameras:
        print("Scanning for available cameras...")
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                print(f"[{i}] Camera found")
                cap.release()
        print("Done.")
        import sys
        sys.exit(0)

    print(f"{'=' * 55}")
    print(f"  SurgeonAI Demo Backend")
    print(f"  Video:     http://localhost:{PORT}/video")
    print(f"  Health:    http://localhost:{PORT}/health")
    print(f"  Socket.IO: http://localhost:{PORT}{NAMESPACE}")
    print(f"  YOLO:      {'✅ Loaded' if YOLO_AVAILABLE else '❌ Not installed'}")
    print(f"  Model:     {args.model or 'default from .env'}")
    print(f"{'=' * 55}")

    cam = open_camera(args.camera)
    if cam:
        camera = cam
        logger.info(
            "Camera ready — %dx%d",
            int(cam.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
    else:
        logger.warning("No camera detected. Plug in webcam and restart.")

    threading.Thread(target=capture_thread, args=(args.camera,), daemon=True).start()
    threading.Thread(target=vision_loop, daemon=True).start()
    
    if args.narrate:
        threading.Thread(target=narrator_thread, args=(args.model,), daemon=True).start()

    socketio.run(app, host="0.0.0.0", port=PORT, debug=False, log_output=False)
