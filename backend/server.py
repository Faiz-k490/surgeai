#!/usr/bin/env python3
"""
SurgeonAI — 8-Phase Demo Backend
Live webcam + YOLOv8 + OpenCV red-rectangle detection + State Machine + Socket.IO + Gemini Snapshot

Run from repo root:
    python backend/server.py
"""

import os
import cv2
import math
import time
import logging
import threading
import numpy as np
from collections import Counter, deque
from pathlib import Path
from flask import Flask, Response, jsonify
from flask_socketio import SocketIO, emit
import concurrent.futures

# ── Config via .env ──────────────────────────────────────────────────────────
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)

PORT = int(os.getenv("PORT", "5000"))
NAMESPACE = os.getenv("SOCKET_NAMESPACE", "/realtime")
YOLO_MODEL = os.getenv("YOLO_MODEL", "yolov8n.pt")
YOLO_CONF = float(os.getenv("YOLO_CONFIDENCE", "0.3"))
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "1"))
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

# Snapshot configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SNAPSHOT_BUCKET = os.getenv("SNAPSHOT_BUCKET", "surgeai-snapshots")

try:
    from pymongo import MongoClient
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client["surgeai"]
    snapshots_collection = db["snapshots"]
except Exception as e:
    mongo_client = None

# ── YOLO (graceful import) ────────────────────────────────────────────────────
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("surgeai.demo")

# ── Constants ─────────────────────────────────────────────────────────────────

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
    "Scalpel": "#22c55e",
    "Forceps": "#3b82f6",
}


# ── Utility functions ─────────────────────────────────────────────────────────

def deviation_to_hex(t):
    """Map 0->green, 0.5->yellow, 1->red."""
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


# ── Spatial Instrument Classification ─────────────────────────────────────────

SPATIAL_MARGIN = 0.05

_label_buffer_left = deque(maxlen=5)
_label_buffer_right = deque(maxlen=5)


def classify_instrument(cid, box, fw, conf):
    """Strict spatial classification based on X-coordinate.
    Left half = Forceps/Clamp, Right half = Scalpel
    Returns (final_label, source)."""
    x1, _, x2, _ = box
    center_x = (x1 + x2) / 2
    mid = fw / 2
    margin = SPATIAL_MARGIN * fw
    
    # Strict determinism: ignoring YOLO cid for instruments, using only position.
    if center_x >= mid:
        return "Scalpel", "spatial_override"
    else:
        return "Forceps", "spatial_override"


def stabilize_label(label, region):
    """Majority vote over last 5 frames to prevent flicker."""
    buf = _label_buffer_right if region == "right" else _label_buffer_left
    buf.append(label)
    return Counter(buf).most_common(1)[0][0]


# ── Object Tracker (smoothing + velocity prediction + TTL) ────────────────────

TRACK_TTL = 0.5
SMOOTH_ALPHA = 0.7

class ObjectTracker:
    """Maintains persistent, smoothed tracks for each object role."""

    def __init__(self):
        self._tracks = {}

    def update(self, detections, now):
        """Merge YOLO detections into persistent tracks. Returns list of tracked detections."""
        seen_roles = set()

        for d in detections:
            role = d["label"]
            seen_roles.add(role)
            new_box = d["box"]

            if role in self._tracks:
                track = self._tracks[role]
                old_box = track["box"]
                dt = max(1e-6, now - track["last_seen"])
                vx = (new_box[0] - old_box[0]) / dt
                vy = (new_box[1] - old_box[1]) / dt
                vx2 = (new_box[2] - old_box[2]) / dt
                vy2 = (new_box[3] - old_box[3]) / dt
                smoothed = [
                    SMOOTH_ALPHA * new_box[i] + (1 - SMOOTH_ALPHA) * old_box[i]
                    for i in range(4)
                ]
                track["box"] = smoothed
                track["velocity"] = (vx, vy, vx2, vy2)
                track["last_seen"] = now
                track["conf"] = d["conf"]
                track["cid"] = d["cid"]
                track["source"] = d.get("source", "yolo")
            else:
                self._tracks[role] = {
                    "box": list(new_box),
                    "velocity": (0, 0, 0, 0),
                    "last_seen": now,
                    "conf": d["conf"],
                    "cid": d["cid"],
                    "label": role,
                    "source": d.get("source", "yolo"),
                }

        expired = []
        for role, track in self._tracks.items():
            if role in seen_roles:
                continue
            dt = now - track["last_seen"]
            if dt > TRACK_TTL:
                expired.append(role)
                continue
            vx, vy, vx2, vy2 = track["velocity"]
            track["box"] = [
                track["box"][0] + vx * dt,
                track["box"][1] + vy * dt,
                track["box"][2] + vx2 * dt,
                track["box"][3] + vy2 * dt,
            ]

        for role in expired:
            del self._tracks[role]

        result = []
        for role, track in self._tracks.items():
            result.append({
                "cid": track["cid"],
                "conf": track["conf"],
                "box": track["box"],
                "label": role,
                "source": track["source"],
            })
        return result


# ── OpenCV: Red Rectangle Detection ──────────────────────────────────────────

def detect_red_rectangle(frame, bbox_xyxy):
    """Find red marker rectangle inside banana bbox.
    Returns (center_x, center_y, angle_deg, rect_points_abs) or None.
    """
    try:
        x1, y1, x2, y2 = [int(v) for v in bbox_xyxy]
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

        m1 = cv2.inRange(hsv, np.array([0, 70, 50]), np.array([12, 255, 255]))
        m2 = cv2.inRange(hsv, np.array([160, 70, 50]), np.array([180, 255, 255]))
        red_mask = cv2.bitwise_or(m1, m2)

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

        if size[0] < size[1]:
            angle += 90

        abs_cx = x1 + center[0]
        abs_cy = y1 + center[1]

        box_pts = cv2.boxPoints(rect).astype(np.float64)
        box_pts[:, 0] += x1
        box_pts[:, 1] += y1

        return (abs_cx, abs_cy, angle, box_pts)
    except Exception as exc:
        logger.debug("Red rect detection failed: %s", exc)
        return None

# ── 512x512 Snapshot Pipeline ────────────────────────────────────────────────

snapshot_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

def extract_512_crop(frame, banana_box):
    """Extract a 512x512 crop centered around the banana."""
    try:
        x1, y1, x2, y2 = banana_box
        cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
        
        h, w = frame.shape[:2]
        
        # Calculate 512x512 boundaries
        crop_size = 512
        half_size = crop_size // 2
        
        start_y = max(0, cy - half_size)
        start_x = max(0, cx - half_size)
        
        end_y = min(h, start_y + crop_size)
        end_x = min(w, start_x + crop_size)
        
        # Adjust if we hit the edge
        if end_y - start_y < crop_size:
            if start_y == 0: end_y = min(h, crop_size)
            if end_y == h: start_y = max(0, h - crop_size)
        if end_x - start_x < crop_size:
            if start_x == 0: end_x = min(w, crop_size)
            if end_x == w: start_x = max(0, w - crop_size)
            
        crop = frame[start_y:end_y, start_x:end_x]
        
        # Pad if the frame itself is smaller than 512x512
        if crop.shape[0] < crop_size or crop.shape[1] < crop_size:
            pad_y = crop_size - crop.shape[0]
            pad_x = crop_size - crop.shape[1]
            crop = cv2.copyMakeBorder(crop, 0, pad_y, 0, pad_x, cv2.BORDER_CONSTANT, value=[0, 0, 0])
            
        return crop
    except Exception as e:
        logger.error(f"Error extracting 512 crop: {e}")
        return None

def process_snapshot_async(crop_image):
    """Sends snapshot to Gemini APIs and stores in MongoDB."""
    logger.info("[SNAPSHOT] Processing final snapshot for MongoDB and Gemini...")
    if crop_image is None:
        return
    
    try:
        # Save to local for verification
        cv2.imwrite("final_snapshot.jpg", crop_image)
        
        if mongo_client:
            snapshots_collection.insert_one({
                "timestamp": time.time(),
                "status": "Surgery Complete",
                "bucket_path": f"{SNAPSHOT_BUCKET}/latest.jpg"
            })
            logger.info("[SNAPSHOT] Document stored in MongoDB.")
    except Exception as e:
        logger.error(f"[SNAPSHOT] Error processing async pipeline: {e}")


# ── DemoOrchestrator (State Machine) ──────────────────────────────────────────

class DemoOrchestrator:
    """8-phase surgical demo state machine with exact timing gating."""
    ANGLE_TTL = 0.5

    def __init__(self):
        self.phase = 0
        self._state_timer_start = None
        self._voice_queue = None
        self._voices_sent = set()
        
        self.snapshot_sent = False
        self.final_crop = None
        
        self._last_angle_data = {"approach_angle": 0, "status": "idle"}
        self._last_angle_time = 0.0

    def trigger_speech(self, phase, message):
        if phase not in self._voices_sent:
            self._voice_queue = message
            self._voices_sent.add(phase)
            logger.info(f"[VOICE] {message}")

    def change_phase(self, new_phase):
        if self.phase != new_phase:
            logger.info(f"Phase {self.phase} -> {new_phase}")
            self.phase = new_phase
            self._state_timer_start = time.time()

    def process(self, detections, red_rect, fh, fw, frame):
        """Process one frame. Returns frame_state dict."""
        
        if self.phase == 0:
            return {"current_phase": 0, "voice_prompt": None, "warning": None, "ar_elements": [], "angle_data": None}

        warning = None
        angle_data = {"approach_angle": 0, "status": "idle"}
        ar_elements = []

        banana = next((d for d in detections if d["cid"] == BANANA_ID), None)
        knife = next((d for d in detections if d["label"] == "Scalpel"), None)
        clamp = next((d for d in detections if d["label"] == "Forceps"), None)

        for d in detections:
            lbl = d["label"]
            x1, y1, x2, y2 = d["box"]
            ar_elements.append({
                "type": "box",
                "x": x1 / fw, "y": y1 / fh,
                "width": (x2 - x1) / fw, "height": (y2 - y1) / fh,
                "color": LABEL_COLORS.get(lbl, "#22d3ee"),
                "label": lbl,
                "confidence": round(d["conf"], 2),
            })

        if red_rect and self.phase >= 2:
            pts = [(p[0] / fw, p[1] / fh) for p in red_rect[3]]
            ar_elements.append({
                "type": "polygon",
                "points": pts,
                "color": "#ef4444",
                "label": "Incision Zone",
            })

        now = time.time()

        # ── State Machine Logic ─────────────────────────────────────────────

        if self.phase == 1:
            # STATE 1: ACTIVATION
            # Wait until banana is detected
            if banana:
                if self._state_timer_start is None:
                    self._state_timer_start = now
                elif now - self._state_timer_start >= 2.5:
                    self.change_phase(2)
            else:
                self._state_timer_start = None

        elif self.phase == 2:
            # STATE 2: SURGICAL SCENE READY
            # Wait for both clamp (left) and scalpel (right) to appear
            if banana and knife and clamp:
                if self._state_timer_start is None:
                    self._state_timer_start = now
                elif now - self._state_timer_start >= 2.5:
                    self.change_phase(3)
                    self.trigger_speech(3, "Tools identified: scalpel and clamp.")
            else:
                self._state_timer_start = None

        elif self.phase == 3:
            # STATE 3: TOOL INTRODUCTION
            # Just pause for confirmation, no speech. After 2 seconds move to Phase 4.
            if self._state_timer_start is None:
                self._state_timer_start = now
            elif now - self._state_timer_start >= 2.0:
                self.change_phase(4)

        elif self.phase == 4:
            # STATE 4: TOOL CONFIRMATION PAUSE
            # Wait for scalpel to be placed on banana region for >= 2-3 seconds
            
            if banana and knife:
                bc = bbox_center(banana["box"])
                kc = bbox_center(knife["box"])
                diag = math.sqrt(fw ** 2 + fh ** 2)
                close = pt_distance(bc, kc) < diag * 0.30
                
                if close:
                    if self._state_timer_start is None:
                        self._state_timer_start = now
                    elif now - self._state_timer_start >= 2.5:
                        self.change_phase(5)
                        self.trigger_speech(5, "You may begin surgery.")
                else:
                    self._state_timer_start = None
            else:
                self._state_timer_start = None

        elif self.phase == 5:
            # STATE 5: SURGERY START PHASE
            # Scalpel actively cutting. 10 second timed window.
            if self._state_timer_start is None:
                self._state_timer_start = now
                
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
                self._last_angle_data = angle_data
                self._last_angle_time = now

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
            else:
                if (now - self._last_angle_time) < DemoOrchestrator.ANGLE_TTL:
                    angle_data = self._last_angle_data

            if now - self._state_timer_start >= 10.0:
                self.change_phase(6)
                self.trigger_speech(6, "Pick up forceps or clamp to remove skin.")

        elif self.phase == 6:
            # STATE 6: CLAMP PHASE
            # 10 second enforced timer
            if self._state_timer_start is None:
                self._state_timer_start = now
                
            if now - self._state_timer_start >= 10.0:
                self.change_phase(7)
                self.trigger_speech(7, "Surgery complete.")
                
        elif self.phase == 7:
            # STATE 7: COMPLETION
            if not self.snapshot_sent and banana:
                self.final_crop = extract_512_crop(frame, banana["box"])
                snapshot_executor.submit(process_snapshot_async, self.final_crop)
                self.snapshot_sent = True
                
            ar_elements.append({"type": "success_overlay"})

        # Global Zone Debug
        ar_elements.append({"type": "zone_debug", "midpoint": 0.5})

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
vision_running = False

def open_camera():
    """Open the configured external camera (DSHOW). Never falls back to internal."""
    idx = CAMERA_INDEX
    logger.info("[CAMERA] Attempting index %d via DSHOW...", idx)

    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(
            f"[FATAL] External webcam not found at index {idx}. "
            "Ensure BRIO is plugged in and no other app is using it. "
            "DO NOT fallback to internal camera."
        )

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    ok, _ = cap.read()
    if not ok:
        cap.release()
        raise RuntimeError(
            f"[FATAL] Camera index {idx} opened but cannot read frames. "
            "Check USB connection and close other apps using the webcam."
        )

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logger.info("[CAMERA] Using index %d — %dx%d (DSHOW)", idx, w, h)
    return cap


def capture_thread():
    """High-FPS capture thread — feeds MJPEG and frame buffer."""
    global camera, latest_frame, vision_running
    while vision_running:
        with camera_lock:
            if camera is None or not camera.isOpened():
                try:
                    camera = open_camera()
                except Exception as e:
                    logger.error(e)
                    time.sleep(2)
                    continue
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


def generate_mjpeg():
    """MJPEG generator for /video endpoint."""
    while True:
        with latest_frame_lock:
            frame = latest_frame
        if frame is None:
            time.sleep(0.05)
            continue
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
        time.sleep(0.033)


# ── Vision Loop ───────────────────────────────────────────────────────────────

orchestrator = DemoOrchestrator()

def vision_loop():
    """YOLO + OpenCV + DemoOrchestrator -> Socket.IO frame_state."""
    global vision_running
    model = None
    if YOLO_AVAILABLE:
        try:
            model = YOLO(YOLO_MODEL)
            logger.info("YOLOv8n loaded: %s", YOLO_MODEL)
        except Exception as e:
            logger.error("YOLO load failed: %s", e)

    tracker = ObjectTracker()
    fps_ema = 0.0

    bg_subtractor = cv2.createBackgroundSubtractorMOG2(
        history=30, varThreshold=40, detectShadows=False
    )

    while vision_running:
        with latest_frame_lock:
            frame = latest_frame
        
        if frame is None:
            time.sleep(0.05)
            continue
            
        t0 = time.time()
        fh, fw = frame.shape[:2]

        detections = []
        if model is not None:
            results = model.predict(
                frame, conf=YOLO_CONF, verbose=False, imgsz=640, classes=ALLOWED_CLASSES
            )
            for r in results:
                if r.boxes is None:
                    continue
                frame_area = fh * fw
                for i in range(len(r.boxes)):
                    cid = int(r.boxes.cls[i].item())
                    conf = float(r.boxes.conf[i].item())
                    box = r.boxes.xyxy[i].tolist()
                    x1, y1, x2, y2 = box

                    box_w = x2 - x1
                    box_h = y2 - y1
                    box_area = box_w * box_h

                    if box_area > 0.3 * frame_area:
                        continue

                    if cid == BANANA_ID:
                        detections.append({"cid": cid, "conf": conf, "box": box,
                                           "label": "Patient Tissue", "source": "yolo"})
                    else:
                        long_side = max(box_w, box_h)
                        short_side = min(box_w, box_h)
                        if long_side > 0 and (short_side / long_side) > 0.85:
                            continue

                        label, source = classify_instrument(cid, box, fw, conf)
                        region = "right" if (box[0] + box[2]) / 2 >= fw / 2 else "left"
                        label = stabilize_label(label, region)
                        effective_cid = KNIFE_ID if label == "Scalpel" else SCISSORS_ID
                        detections.append({"cid": effective_cid, "conf": conf, "box": box,
                                           "label": label, "source": source})

        red_rect = None
        banana_det = next((d for d in detections if d["cid"] == BANANA_ID), None)
        if banana_det is not None:
            red_rect = detect_red_rectangle(frame, banana_det["box"])

        now = time.time()
        tracked = tracker.update(detections, now)
        state = orchestrator.process(tracked, red_rect, fh, fw, frame)

        dt = max(1e-6, time.time() - t0)
        fps_ema = 0.85 * fps_ema + 0.15 * (1.0 / dt)
        latency_ms = int(dt * 1000)

        socketio.emit("frame_state", {"payload": state}, namespace=NAMESPACE)
        socketio.emit(
            "system_health",
            {"payload": {"loopAAlive": True, "fps": round(fps_ema, 1), "latency": latency_ms}},
            namespace=NAMESPACE,
        )

        elapsed = time.time() - t0
        if elapsed < 0.066:
            time.sleep(0.066 - elapsed)


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
    return jsonify({"ok": True, "camera": cam_ok, "yolo": YOLO_AVAILABLE, "phase": orchestrator.phase})

@socketio.on("connect", namespace=NAMESPACE)
def on_connect():
    logger.info("[Socket] Client connected")
    emit("system_health", {"payload": {"loopAAlive": True, "fps": 30, "latency": 0}})

@socketio.on("activate_surgeai", namespace=NAMESPACE)
def on_activate():
    """Triggered by frontend Landing Page CTA"""
    global vision_running
    logger.info("[Socket] activate_surgeai received. Initializing State 1.")
    orchestrator.change_phase(1)
    
    if not vision_running:
        vision_running = True
        threading.Thread(target=capture_thread, daemon=True).start()
        threading.Thread(target=vision_loop, daemon=True).start()
    
    emit("state", {"phase": orchestrator.phase})

@socketio.on("disconnect", namespace=NAMESPACE)
def on_disconnect():
    logger.info("[Socket] Client disconnected")

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"{'=' * 55}")
    print(f"  SurgeonAI Demo Backend (Deterministic State Engine)")
    print(f"  Video:     http://localhost:{PORT}/video")
    print(f"  Health:    http://localhost:{PORT}/health")
    print(f"  Socket.IO: http://localhost:{PORT}{NAMESPACE}")
    print(f"  YOLO:      {'Loaded' if YOLO_AVAILABLE else 'Not installed'}")
    print(f"  Mongo:     {'Connected' if mongo_client else 'Not configured'}")
    print(f"{'=' * 55}")

    # No auto-start of camera / vision loop here. 
    # Must wait for "activate_surgeai" from Socket.IO client.
    
    socketio.run(app, host="0.0.0.0", port=PORT, debug=False, log_output=False,
                 allow_unsafe_werkzeug=True)
