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
from flask import Flask, Response, jsonify
from flask_socketio import SocketIO, emit

# ── YOLO (graceful import) ────────────────────────────────────────────────────
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

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


def scalpel_angle_from_contour(frame, bbox_xyxy):
    """True blade-axis angle via edge-PCA inside the scalpel bbox.
    The scalpel is a right-triangle blade — bbox aspect ratio is useless.
    Instead we run Canny inside the bbox, collect edge pixels, and use PCA
    to find the dominant axis.  Falls back to minAreaRect on dark-mask pixels
    if edges are too sparse.
    Returns angle in degrees: 0 = horizontal, 90 = vertical.
    """
    try:
        x1, y1, x2, y2 = [int(v) for v in bbox_xyxy]
        fh, fw = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(fw, x2), min(fh, y2)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return _bbox_fallback(bbox_xyxy)

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        # ── Strategy 1: Canny edge PCA ────────────────────────────────────
        edges = cv2.Canny(gray, 50, 150)
        pts = np.column_stack(np.nonzero(edges))  # (row, col)
        if pts.shape[0] >= 30:
            mean, eigenvectors = cv2.PCACompute(pts.astype(np.float64), mean=None)
            angle = math.degrees(math.atan2(eigenvectors[0, 1], eigenvectors[0, 0]))
            return abs(angle) % 180

        # ── Strategy 2: Dark-pixel minAreaRect ────────────────────────────
        _, dark_mask = cv2.threshold(gray, 60, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            biggest = max(contours, key=cv2.contourArea)
            if cv2.contourArea(biggest) > 50:
                rect = cv2.minAreaRect(biggest)
                _, size, angle = rect
                if size[0] < size[1]:
                    angle += 90
                return abs(angle) % 180

        return _bbox_fallback(bbox_xyxy)
    except Exception:
        return _bbox_fallback(bbox_xyxy)


def _bbox_fallback(bbox_xyxy):
    """Last resort: bbox aspect ratio."""
    x1, y1, x2, y2 = bbox_xyxy
    w, h = abs(x2 - x1), abs(y2 - y1)
    if w < 1 and h < 1:
        return 0.0
    return math.degrees(math.atan2(h, w))


# ── OpenCV: Black-tape Scalpel Fallback Detection ─────────────────────────────

def detect_black_scalpel(frame, exclude_bbox=None):
    """Detect a dark, elongated object (scalpel wrapped in black tape).
    Uses HSV value channel to find very dark regions, then filters by
    elongation (aspect ratio >= 2.5) and minimum area.
    Returns {cid, conf, box, angle} or None.
    exclude_bbox: banana bbox to ignore (xyxy format).
    """
    try:
        fh, fw = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Black tape: low value, any hue/sat
        dark_mask = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 55]))

        # Clean up noise
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, k, iterations=2)
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, k, iterations=1)

        # If banana bbox supplied, zero out that region to avoid false positives
        if exclude_bbox is not None:
            ex1, ey1, ex2, ey2 = [int(v) for v in exclude_bbox]
            # Add margin
            margin = 20
            ex1, ey1 = max(0, ex1 - margin), max(0, ey1 - margin)
            ex2, ey2 = min(fw, ex2 + margin), min(fh, ey2 + margin)
            dark_mask[ey1:ey2, ex1:ex2] = 0

        contours, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        best = None
        best_score = 0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 800:  # minimum pixel area
                continue
            rect = cv2.minAreaRect(cnt)
            _, (rw, rh), angle = rect
            if rw < 1 or rh < 1:
                continue
            aspect = max(rw, rh) / min(rw, rh)
            if aspect < 2.5:  # must be elongated like a scalpel
                continue
            # Score by area * aspect (prefer large elongated objects)
            score = area * aspect
            if score > best_score:
                best_score = score
                # Normalize angle to long-axis
                if rw < rh:
                    angle += 90
                bx, by, bw, bh = cv2.boundingRect(cnt)
                best = {
                    "cid": KNIFE_ID,
                    "conf": 0.70,
                    "box": [float(bx), float(by), float(bx + bw), float(by + bh)],
                    "angle": abs(angle) % 180,
                    "_source": "opencv",
                }

        return best
    except Exception as exc:
        logger.debug("Black scalpel detection failed: %s", exc)
        return None


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

    def process(self, detections, red_rect, fh, fw, frame=None):
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
                # Use pre-computed contour angle if available, else compute
                s_angle = knife.get("angle") or scalpel_angle_from_contour(frame, knife["box"])
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


def open_camera():
    for idx in range(5):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)
            logger.info("Opened camera index %d", idx)
            return cap
        cap.release()
    logger.error("No camera found on indices 0-4")
    return None


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
        time.sleep(0.015)  # ~60fps capture ceiling


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
                    det = {"cid": cid, "conf": conf, "box": box}
                    # Pre-compute contour angle for scalpel
                    if cid == KNIFE_ID:
                        det["angle"] = scalpel_angle_from_contour(frame, box)
                    detections.append(det)

        # ── OpenCV black-scalpel fallback (Phase 1+) ──────────────────────
        has_yolo_knife = any(d["cid"] == KNIFE_ID for d in detections)
        if not has_yolo_knife and orchestrator.phase >= 1:
            banana_det_for_exclude = next(
                (d for d in detections if d["cid"] == BANANA_ID), None
            )
            exclude = banana_det_for_exclude["box"] if banana_det_for_exclude else None
            cv_scalpel = detect_black_scalpel(frame, exclude_bbox=exclude)
            if cv_scalpel is not None:
                detections.append(cv_scalpel)
                logger.debug(
                    "OpenCV scalpel fallback: angle=%.1f box=%s",
                    cv_scalpel.get("angle", -1),
                    cv_scalpel["box"],
                )

        # ── Red rect detection (only when banana present) ─────────────────
        red_rect = None
        banana_det = next((d for d in detections if d["cid"] == BANANA_ID), None)
        if banana_det is not None:
            red_rect = detect_red_rectangle(frame, banana_det["box"])

        # ── DemoOrchestrator ──────────────────────────────────────────────
        state = orchestrator.process(detections, red_rect, fh, fw, frame=frame)

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


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"{'=' * 55}")
    print(f"  SurgeonAI Demo Backend")
    print(f"  Video:     http://localhost:{PORT}/video")
    print(f"  Health:    http://localhost:{PORT}/health")
    print(f"  Socket.IO: http://localhost:{PORT}{NAMESPACE}")
    print(f"  YOLO:      {'✅ Loaded' if YOLO_AVAILABLE else '❌ Not installed'}")
    print(f"{'=' * 55}")

    cam = open_camera()
    if cam:
        camera = cam
        logger.info(
            "Camera ready — %dx%d",
            int(cam.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
    else:
        logger.warning("No camera detected. Plug in webcam and restart.")

    threading.Thread(target=capture_thread, daemon=True).start()
    threading.Thread(target=vision_loop, daemon=True).start()

    socketio.run(app, host="0.0.0.0", port=PORT, debug=False, log_output=False)
