"""
YOLOv8-nano surgical demo detector — hardcoded for banana/knife/scissors.

Detects red marker line on banana via HSV thresholding, computes scalpel
approach angle relative to the incision line, emits telemetry payload.
Runs entirely on CPU at 20-30+ FPS.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("surgeai.vision.yolo")

# ── COCO class IDs we care about ──────────────────────────────────────────────
_COCO_MAP: Dict[int, str] = {
    46: "Patient Tissue",   # banana
    43: "Scalpel",          # knife
    76: "Forceps",          # scissors
}

_ALLOWED_IDS = frozenset(_COCO_MAP.keys())


# ── Red-line detection via HSV ────────────────────────────────────────────────

def _detect_red_line_angle(frame: np.ndarray, bbox_xyxy: Tuple[int, int, int, int]) -> Optional[float]:
    """Return the dominant red-line angle (degrees, 0-180) inside the banana bbox.

    Returns None if no red line is found.  Never raises.
    """
    try:
        x1, y1, x2, y2 = bbox_xyxy
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

        # Red wraps around hue 0/180 — two ranges
        mask1 = cv2.inRange(hsv, np.array([0, 80, 60]), np.array([12, 255, 255]))
        mask2 = cv2.inRange(hsv, np.array([165, 80, 60]), np.array([180, 255, 255]))
        red_mask = cv2.bitwise_or(mask1, mask2)

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel, iterations=1)

        # Need minimum red pixels to be meaningful
        if cv2.countNonZero(red_mask) < 80:
            return None

        # Strategy 1: PCA on red pixel coordinates (most robust for thick lines)
        coords = cv2.findNonZero(red_mask)
        if coords is None or len(coords) < 20:
            return None

        coords_flat = coords.reshape(-1, 2).astype(np.float64)
        mean, eigenvectors = cv2.PCACompute(coords_flat, mean=None, maxComponents=1)
        vx, vy = eigenvectors[0]
        angle_rad = math.atan2(vy, vx)
        angle_deg = math.degrees(angle_rad) % 180  # normalize to 0-180°

        return angle_deg

    except Exception as exc:
        logger.debug("Red-line detection failed: %s", exc)
        return None


def _bbox_orientation_angle(bbox_xyxy: Tuple[float, float, float, float]) -> float:
    """Estimate tool orientation from bounding-box aspect ratio.

    A knife/scalpel bbox is elongated along its length.
    Returns angle in degrees 0-180.
    """
    x1, y1, x2, y2 = bbox_xyxy
    w = x2 - x1
    h = y2 - y1
    if w < 1 and h < 1:
        return 0.0
    # atan2 of the bbox diagonal direction (long axis)
    if h > w:
        # Tall box → instrument oriented more vertically
        angle = math.degrees(math.atan2(h, w))
    else:
        # Wide box → instrument oriented more horizontally
        angle = math.degrees(math.atan2(w, h))
        angle = 90.0 - angle  # flip to match coordinate semantics

    return angle % 180


def _refined_tool_angle(frame: np.ndarray, bbox_xyxy: Tuple[int, int, int, int]) -> float:
    """Try contour-PCA on grayscale edges inside the scalpel box for a better angle.

    Falls back to bbox orientation if the contour is too small.
    """
    try:
        x1, y1, x2, y2 = bbox_xyxy
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return _bbox_orientation_angle(bbox_xyxy)

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        coords = cv2.findNonZero(edges)
        if coords is None or len(coords) < 30:
            return _bbox_orientation_angle(bbox_xyxy)

        coords_flat = coords.reshape(-1, 2).astype(np.float64)
        _, eigenvectors = cv2.PCACompute(coords_flat, mean=None, maxComponents=1)
        vx, vy = eigenvectors[0]
        return math.degrees(math.atan2(vy, vx)) % 180

    except Exception:
        return _bbox_orientation_angle(bbox_xyxy)


def _compute_approach_telemetry(
    approach_angle_deg: float,
) -> Dict[str, Any]:
    """Given the relative angle (0-90 scale), classify and build telemetry dict."""
    angle_int = int(round(approach_angle_deg))
    if 85 <= angle_int <= 95:
        status = "Perfect"
    elif angle_int < 85:
        status = "Too Shallow"
    else:
        status = "Too Steep"
    return {"approach_angle": angle_int, "status": status}


# ── Main detector ─────────────────────────────────────────────────────────────

class YoloDetector:
    """YOLOv8-nano detector hardcoded for surgical banana-demo objects."""

    def __init__(self, model_path: str = "yolov8n.pt", confidence: float = 0.4) -> None:
        from ultralytics import YOLO
        self._model = YOLO(model_path)
        self._conf = confidence
        self._names: Dict[int, str] = self._model.names or {}
        # Pre-build the list of class indices to pass to YOLO
        self._classes = list(_ALLOWED_IDS)
        logger.info(
            "YOLO loaded: %s (tracking classes %s, conf=%.2f)",
            model_path,
            self._classes,
            confidence,
        )

    def ping(self) -> bool:
        return self._model is not None

    def detect(self, frame: np.ndarray) -> Dict[str, Any]:
        """Run detection on a BGR numpy frame.

        Returns:
            {
                "boxes": [
                    {"x": 0.12, "y": 0.34, "width": 0.2, "height": 0.15,
                     "label": "Patient Tissue", "confidence": 0.91},
                    ...
                ],
                "telemetry": {"approach_angle": 88, "status": "Perfect"} | None
            }
        """
        h, w = frame.shape[:2]
        results = self._model.predict(
            frame,
            conf=self._conf,
            verbose=False,
            imgsz=640,
            classes=self._classes,  # only detect our 3 classes
        )

        ar_boxes: List[Dict[str, Any]] = []
        banana_xyxy: Optional[Tuple[int, int, int, int]] = None
        scalpel_xyxy: Optional[Tuple[int, int, int, int]] = None

        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                if cls_id not in _ALLOWED_IDS:
                    continue

                conf = float(boxes.conf[i].item())
                label = _COCO_MAP[cls_id]

                # Raw pixel coords
                x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                ix1, iy1, ix2, iy2 = int(x1), int(y1), int(x2), int(y2)

                # Normalized bounding box (xyxy → xywh normalized 0-1)
                nx = x1 / w
                ny = y1 / h
                nw = (x2 - x1) / w
                nh = (y2 - y1) / h

                ar_boxes.append({
                    "x": round(nx, 4),
                    "y": round(ny, 4),
                    "width": round(nw, 4),
                    "height": round(nh, 4),
                    "label": label,
                    "confidence": round(conf, 3),
                })

                # Track specific detections for angle calc
                if cls_id == 46:  # banana / Patient Tissue
                    banana_xyxy = (ix1, iy1, ix2, iy2)
                elif cls_id == 43:  # knife / Scalpel
                    scalpel_xyxy = (ix1, iy1, ix2, iy2)

        # ── Angle telemetry ───────────────────────────────────────────────
        telemetry: Optional[Dict[str, Any]] = None

        if banana_xyxy is not None and scalpel_xyxy is not None:
            red_line_angle = _detect_red_line_angle(frame, banana_xyxy)
            if red_line_angle is not None:
                scalpel_angle = _refined_tool_angle(frame, scalpel_xyxy)
                # Relative angle between scalpel and red line
                raw_diff = abs(scalpel_angle - red_line_angle)
                # Normalize to 0–90 range (perpendicular = 90°)
                if raw_diff > 90:
                    raw_diff = 180 - raw_diff
                telemetry = _compute_approach_telemetry(raw_diff)

        return {"boxes": ar_boxes, "telemetry": telemetry}
