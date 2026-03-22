#!/usr/bin/env python3
"""
SurgeonAI — 6-Phase Demo Backend
Live webcam + YOLOv8 + OpenCV red-rectangle detection + State Machine + Socket.IO

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

# ── Config via .env ──────────────────────────────────────────────────────────
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)

PORT = int(os.getenv("PORT", "5000"))
NAMESPACE = os.getenv("SOCKET_NAMESPACE", "/realtime")
YOLO_MODEL = os.getenv("YOLO_MODEL", "yolov8n.pt")
YOLO_CONF = float(os.getenv("YOLO_CONFIDENCE", "0.3"))  # migration spec §7 requires 0.3
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "1"))
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

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
    """Spatial override: right half = scalpel, left half = clamp.
    Returns (final_label, source)."""
    x1, _, x2, _ = box
    center_x = (x1 + x2) / 2
    mid = fw / 2
    margin = SPATIAL_MARGIN * fw

    if center_x >= mid + margin:
        return "Scalpel", "spatial_override"
    elif center_x <= mid - margin:
        return "Forceps", "spatial_override"
    else:
        return LABEL_MAP.get(cid, "Unknown"), "yolo"


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


# ── DemoOrchestrator (State Machine) ──────────────────────────────────────────

class DemoOrchestrator:
    """6-phase surgical demo state machine with debounced transitions."""

    DEBOUNCE = 6
    INCISION_DURATION = 6.0
    COMPLETE_DELAY = 3.0
    ANGLE_TTL = 0.5  # seconds to persist last-known angle data when YOLO drops scalpel

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
        # Angle data persistence — carry forward last valid angle for ANGLE_TTL seconds
        self._last_angle_data = {"approach_angle": 0, "status": "idle"}
        self._last_angle_time = 0.0

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
            logger.info("Phase -> %d", target)
            return True
        return False

    def process(self, detections, red_rect, fh, fw):
        """Process one frame. Returns frame_state dict."""
        warning = None
        angle_data = {"approach_angle": 0, "status": "idle"}
        ar_elements = []

        banana = next((d for d in detections if d["cid"] == BANANA_ID), None)
        knife = next((d for d in detections if d["cid"] == KNIFE_ID), None)
        clamp = next((d for d in detections if d["cid"] in (SCISSORS_ID, FORK_ID)), None)

        for d in detections:
            lbl = d.get("label", LABEL_MAP.get(d["cid"], "Unknown"))
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
                # Cache the fresh angle data + timestamp for TTL persistence
                self._last_angle_data = angle_data
                self._last_angle_time = time.time()

                if raw_diff > 60:
                    warning = "CRITICAL: Angle too steep! You are piercing crucial arteries!"

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

                if self._incision_start and (time.time() - self._incision_start) > self.INCISION_DURATION:
                    self._try_advance(4, True)
            else:
                # FIX (BUG-1): Do NOT reset _incision_start on missed frames.
                # The ObjectTracker TTL keeps the knife alive for 0.5s anyway.
                # Angle data TTL: keep last known values for ANGLE_TTL seconds
                if (time.time() - self._last_angle_time) < self.ANGLE_TTL:
                    angle_data = self._last_angle_data

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
    global camera, latest_frame
    while True:
        with camera_lock:
            if camera is None or not camera.isOpened():
                camera = open_camera()
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

def _contour_scalpel_fallback(frame, fw, fh, bg_subtractor):
    """
    Fallback scalpel detection using contour analysis on the right half of the frame.
    Triggered when YOLO does not detect any instrument on the right side.
    Migration spec §15b Issue 1 fix: inject synthetic Scalpel detection from
    contour/motion activity in right half when YOLO misses.
    Returns a detection dict or None.
    """
    try:
        right_x = fw // 2
        right_half = frame[:, right_x:]

        # Apply background subtractor for motion detection
        fg_mask = bg_subtractor.apply(right_half)

        # Morphological clean-up to remove noise
        k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, k3, iterations=1)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, k3, iterations=2)

        # Noise gate: require meaningful pixel count
        if cv2.countNonZero(fg_mask) < 200:
            return None

        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        best = None
        best_score = 0.0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 300 or area > 0.25 * (fw / 2) * fh:
                continue
            rect = cv2.minAreaRect(cnt)
            rw, rh = rect[1]
            if rw < 1 or rh < 1:
                continue
            long_s = max(rw, rh)
            short_s = min(rw, rh)
            ratio = short_s / long_s
            # Instruments are elongated; reject near-square (head/body) shapes
            if ratio > 0.75:
                continue
            score = area * (1.0 - ratio)
            if score > best_score:
                best_score = score
                best = rect

        if best is None:
            return None

        center, size, _ = best
        abs_cx = right_x + center[0]
        abs_cy = center[1]
        half_w = max(size) / 2
        half_h = min(size) / 2
        box = [
            max(0.0, abs_cx - half_w), max(0.0, abs_cy - half_h),
            min(float(fw), abs_cx + half_w), min(float(fh), abs_cy + half_h),
        ]
        logger.debug("[FALLBACK] Contour scalpel at (%.0f, %.0f)", abs_cx, abs_cy)
        return {
            "cid": KNIFE_ID,
            "conf": 0.25,  # synthetic — flagged as contour_fallback
            "box": box,
            "label": "Scalpel",
            "source": "contour_fallback",
        }
    except Exception as exc:
        logger.debug("Contour fallback error: %s", exc)
        return None


def vision_loop():
    """YOLO + OpenCV + DemoOrchestrator -> Socket.IO frame_state."""
    model = None
    if YOLO_AVAILABLE:
        try:
            model = YOLO(YOLO_MODEL)
            logger.info("YOLOv8n loaded: %s", YOLO_MODEL)
        except Exception as e:
            logger.error("YOLO load failed: %s", e)

    orchestrator = DemoOrchestrator()
    tracker = ObjectTracker()
    fps_ema = 0.0
    # Background subtractor for motion-based scalpel fallback (migration spec §15b Issue 1)
    bg_subtractor = cv2.createBackgroundSubtractorMOG2(
        history=30, varThreshold=40, detectShadows=False
    )

    while True:
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

        # ── Contour/motion fallback (migration spec §15b Issue 1 & 3) ─────────────
        # Only inject when YOLO found no instrument on the right side of frame
        yolo_has_right_instrument = any(
            d["label"] in ("Scalpel", "Forceps")
            and (d["box"][0] + d["box"][2]) / 2 >= fw / 2
            for d in detections
        )
        if not yolo_has_right_instrument:
            fallback = _contour_scalpel_fallback(frame, fw, fh, bg_subtractor)
            if fallback is not None:
                # Don't add if tracker already has a live Scalpel track
                if "Scalpel" not in {d["label"] for d in detections}:
                    detections.append(fallback)
        else:
            # Keep BG subtractor warm even when YOLO wins
            bg_subtractor.apply(frame[:, fw // 2:])

        red_rect = None
        banana_det = next((d for d in detections if d["cid"] == BANANA_ID), None)
        if banana_det is not None:
            red_rect = detect_red_rectangle(frame, banana_det["box"])

        now = time.time()
        tracked = tracker.update(detections, now)
        state = orchestrator.process(tracked, red_rect, fh, fw)

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


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"{'=' * 55}")
    print(f"  SurgeonAI Demo Backend")
    print(f"  Video:     http://localhost:{PORT}/video")
    print(f"  Health:    http://localhost:{PORT}/health")
    print(f"  Socket.IO: http://localhost:{PORT}{NAMESPACE}")
    print(f"  YOLO:      {'Loaded' if YOLO_AVAILABLE else 'Not installed'}")
    print(f"{'=' * 55}")

    camera = open_camera()

    threading.Thread(target=capture_thread, daemon=True).start()
    threading.Thread(target=vision_loop, daemon=True).start()

    socketio.run(app, host="0.0.0.0", port=PORT, debug=False, log_output=False,
                 allow_unsafe_werkzeug=True)
