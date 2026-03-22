from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from app.core.settings import Settings

try:
    from ultralytics import YOLO

    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


logger = logging.getLogger("surgeai.vision")

BANANA_ID = 46
KNIFE_ID = 43
FORK_ID = 42
SCISSORS_ID = 76
ALLOWED_CLASSES = [BANANA_ID, KNIFE_ID, FORK_ID, SCISSORS_ID]

TRACK_COLORS = {
    "banana": "#ef4444",
    "clamp": "#3b82f6",
    "scalpel": "#22c55e",
}

TRACK_LABELS = {
    "banana": "Patient Tissue",
    "clamp": "Clamp",
    "scalpel": "Scalpel",
}


@dataclass
class DetectionCandidate:
    cid: int
    box: list[float]
    confidence: float
    slot_name: str
    source: str
    zone: str | None = None


@dataclass
class TrackSlot:
    slot_name: str
    label: str
    color: str
    cid: int
    box: list[float] | None = None
    confidence: float = 0.0
    source: str = "yolo"
    last_seen_at: float = 0.0
    active_since: float | None = None
    velocity: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    visible: bool = False
    predicted: bool = False
    locked: bool = False
    locked_at: float | None = None
    origin_zone: str | None = None
    last_box: list[float] | None = None

    def stable_for(self, now: float) -> float:
        if not self.visible or self.active_since is None:
            return 0.0
        return max(0.0, now - self.active_since)

    def is_recent(self, now: float, max_gap_seconds: float) -> bool:
        return self.visible and (now - self.last_seen_at) <= max_gap_seconds

    def as_overlay(self, frame_width: int, frame_height: int) -> dict[str, Any] | None:
        if not self.visible or not self.box:
            return None
        x1, y1, x2, y2 = self.box
        return {
            "type": "box",
            "id": self.slot_name,
            "x": x1 / frame_width,
            "y": y1 / frame_height,
            "width": (x2 - x1) / frame_width,
            "height": (y2 - y1) / frame_height,
            "label": self.label,
            "color": self.color,
            "confidence": round(self.confidence, 2),
            "predicted": self.predicted,
            "locked": self.locked,
        }


@dataclass
class RedRectangle:
    center_x: float
    center_y: float
    angle_degrees: float
    points: list[tuple[float, float]]


@dataclass
class VisionFrame:
    tracks: dict[str, TrackSlot]
    red_rectangle: RedRectangle | None


def bbox_center(box: list[float]) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def pt_distance(point_a: tuple[float, float], point_b: tuple[float, float]) -> float:
    return math.sqrt((point_a[0] - point_b[0]) ** 2 + (point_a[1] - point_b[1]) ** 2)


def scalpel_angle_from_bbox(box: list[float]) -> float:
    x1, y1, x2, y2 = box
    width = max(1.0, x2 - x1)
    height = max(1.0, y2 - y1)
    return math.degrees(math.atan2(abs(height), abs(width)))


def deviation_to_hex(value: float) -> str:
    value = max(0.0, min(1.0, value))
    if value < 0.5:
        red = int(255 * (value * 2))
        green = 255
    else:
        red = 255
        green = int(255 * (1 - ((value - 0.5) * 2)))
    return f"#{red:02x}{green:02x}00"


def _box_area(box: list[float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _box_iou(box_a: list[float] | None, box_b: list[float]) -> float:
    if box_a is None:
        return 0.0
    x_left = max(box_a[0], box_b[0])
    y_top = max(box_a[1], box_b[1])
    x_right = min(box_a[2], box_b[2])
    y_bottom = min(box_a[3], box_b[3])
    if x_right <= x_left or y_bottom <= y_top:
        return 0.0
    intersection = (x_right - x_left) * (y_bottom - y_top)
    union = _box_area(box_a) + _box_area(box_b) - intersection
    if union <= 0:
        return 0.0
    return intersection / union


class StableSlotTracker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.slots = {
            "banana": TrackSlot("banana", TRACK_LABELS["banana"], TRACK_COLORS["banana"], BANANA_ID),
            "clamp": TrackSlot("clamp", TRACK_LABELS["clamp"], TRACK_COLORS["clamp"], SCISSORS_ID),
            "scalpel": TrackSlot("scalpel", TRACK_LABELS["scalpel"], TRACK_COLORS["scalpel"], KNIFE_ID),
        }

    def reset(self) -> None:
        self.__init__(self.settings)

    def update(self, detections: list[DetectionCandidate], now: float) -> dict[str, TrackSlot]:
        grouped: dict[str, list[DetectionCandidate]] = {"banana": [], "instrument": []}
        for detection in detections:
            grouped[detection.slot_name].append(detection)

        banana_slot = self.slots["banana"]
        banana_candidate = self._select_candidate(banana_slot, grouped["banana"])
        if banana_candidate is None:
            self._predict_or_expire(banana_slot, now)
        else:
            self._merge_candidate(banana_slot, banana_candidate, now)

        remaining = list(grouped["instrument"])
        for slot_name in ("clamp", "scalpel"):
            slot = self.slots[slot_name]
            candidate_index = self._select_instrument_candidate_index(slot, remaining)
            if candidate_index is None:
                self._predict_or_expire(slot, now)
                continue
            candidate = remaining.pop(candidate_index)
            self._merge_candidate(slot, candidate, now)
            if slot_name in ("clamp", "scalpel") and not slot.locked:
                slot.locked = True
                slot.locked_at = now
                slot.origin_zone = "left" if slot_name == "clamp" else "right"

        return self.slots

    def _select_candidate(self, slot: TrackSlot, candidates: list[DetectionCandidate]) -> DetectionCandidate | None:
        if not candidates:
            return None

        def score(candidate: DetectionCandidate) -> float:
            return candidate.confidence + (_box_iou(slot.box, candidate.box) * 0.5)

        return max(candidates, key=score)

    def _select_instrument_candidate_index(self, slot: TrackSlot, candidates: list[DetectionCandidate]) -> int | None:
        if not candidates:
            return None

        eligible: list[tuple[int, DetectionCandidate]] = []
        if slot.locked:
            eligible = list(enumerate(candidates))
        else:
            target_zone = "left" if slot.slot_name == "clamp" else "right"
            eligible = [(index, candidate) for index, candidate in enumerate(candidates) if candidate.zone == target_zone]

        if not eligible:
            return None

        reference_box = slot.box or slot.last_box

        def score(item: tuple[int, DetectionCandidate]) -> float:
            _, candidate = item
            anchor_box = reference_box if slot.locked else None
            center_score = 0.0
            if anchor_box is not None:
                anchor_x, anchor_y = bbox_center(anchor_box)
                cand_x, cand_y = bbox_center(candidate.box)
                center_score = max(0.0, 1.0 - (pt_distance((anchor_x, anchor_y), (cand_x, cand_y)) / 320.0))
            zone_bonus = 0.2 if candidate.zone == slot.origin_zone else 0.0
            return candidate.confidence + (_box_iou(anchor_box, candidate.box) * 0.9) + center_score + zone_bonus

        best_index, _ = max(eligible, key=score)
        return best_index

    def _merge_candidate(self, slot: TrackSlot, candidate: DetectionCandidate, now: float) -> None:
        if slot.box is None or not slot.visible:
            slot.box = list(candidate.box)
            slot.velocity = [0.0, 0.0, 0.0, 0.0]
            slot.active_since = now
        else:
            previous_box = slot.box
            dt = max(1e-6, now - slot.last_seen_at)
            velocity = [(candidate.box[i] - previous_box[i]) / dt for i in range(4)]
            smoothed_box = [
                (self.settings.smoothing_alpha * candidate.box[i]) + ((1 - self.settings.smoothing_alpha) * previous_box[i])
                for i in range(4)
            ]
            slot.box = smoothed_box
            slot.velocity = velocity
            if now - slot.last_seen_at > self.settings.track_ttl_seconds:
                slot.active_since = now

        slot.last_seen_at = now
        slot.visible = True
        slot.predicted = False
        slot.confidence = candidate.confidence
        slot.cid = candidate.cid
        slot.source = candidate.source
        slot.last_box = list(slot.box)

    def _predict_or_expire(self, slot: TrackSlot, now: float) -> None:
        if not slot.visible:
            return
        gap = now - slot.last_seen_at
        if gap > self.settings.track_ttl_seconds:
            if slot.box is not None:
                slot.last_box = list(slot.box)
            slot.visible = False
            slot.predicted = False
            slot.box = None
            slot.confidence = 0.0
            slot.active_since = None
            slot.velocity = [0.0, 0.0, 0.0, 0.0]
            return
        if slot.box is None:
            return
        slot.box = [slot.box[i] + (slot.velocity[i] * gap) for i in range(4)]
        slot.predicted = True


def detect_red_rectangle(frame: np.ndarray, banana_box: list[float] | None) -> RedRectangle | None:
    if banana_box is None:
        return None

    try:
        x1, y1, x2, y2 = [int(value) for value in banana_box]
        frame_height, frame_width = frame.shape[:2]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(frame_width, x2)
        y2 = min(frame_height, y2)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        lower_red_one = cv2.inRange(hsv, np.array([0, 70, 50]), np.array([12, 255, 255]))
        lower_red_two = cv2.inRange(hsv, np.array([160, 70, 50]), np.array([180, 255, 255]))
        red_mask = cv2.bitwise_or(lower_red_one, lower_red_two)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel, iterations=1)

        if cv2.countNonZero(red_mask) < 80:
            return None

        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contour) < 40:
            return None

        rectangle = cv2.minAreaRect(contour)
        center, size, angle = rectangle
        if size[0] < size[1]:
            angle += 90

        points = cv2.boxPoints(rectangle).astype(np.float64)
        points[:, 0] += x1
        points[:, 1] += y1

        return RedRectangle(
            center_x=x1 + center[0],
            center_y=y1 + center[1],
            angle_degrees=angle,
            points=[(float(point[0]), float(point[1])) for point in points],
        )
    except Exception as exc:
        logger.debug("Red rectangle detection failed: %s", exc)
        return None


class VisionRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.tracker = StableSlotTracker(settings)
        self.model = None

        if YOLO_AVAILABLE:
            try:
                self.model = YOLO(settings.yolo_model_path)
                logger.info("YOLO loaded from %s", settings.yolo_model_path)
            except Exception as exc:
                logger.error("YOLO failed to load: %s", exc)
                self.model = None

    def reset(self) -> None:
        self.tracker.reset()

    def process_frame(self, frame: np.ndarray) -> VisionFrame:
        now = time.time()
        detections = self._run_yolo(frame)
        tracks = self.tracker.update(detections, now)

        banana_track = tracks["banana"]
        red_rectangle = None
        if banana_track.visible and banana_track.box:
            red_rectangle = detect_red_rectangle(frame, banana_track.box)

        return VisionFrame(tracks=tracks, red_rectangle=red_rectangle)

    def _run_yolo(self, frame: np.ndarray) -> list[DetectionCandidate]:
        if self.model is None:
            return []

        frame_height, frame_width = frame.shape[:2]
        frame_area = frame_height * frame_width

        detections: list[DetectionCandidate] = []
        results = self.model.predict(
            frame,
            conf=self.settings.yolo_confidence,
            imgsz=self.settings.inference_image_size,
            classes=ALLOWED_CLASSES,
            verbose=False,
        )

        midpoint = frame_width / 2.0
        neutral_margin = frame_width * self.settings.neutral_zone_ratio

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for index in range(len(boxes)):
                cid = int(boxes.cls[index].item())
                confidence = float(boxes.conf[index].item())
                box = [float(value) for value in boxes.xyxy[index].tolist()]
                area = _box_area(box)
                if area <= 0 or area > frame_area * 0.35:
                    continue

                if cid == BANANA_ID:
                    detections.append(DetectionCandidate(BANANA_ID, box, confidence, "banana", "yolo"))
                    continue

                width = max(1.0, box[2] - box[0])
                height = max(1.0, box[3] - box[1])
                aspect_ratio = min(width, height) / max(width, height)
                if aspect_ratio > 0.9:
                    continue

                center_x = bbox_center(box)[0]
                if center_x <= midpoint - neutral_margin:
                    detections.append(DetectionCandidate(SCISSORS_ID, box, confidence, "instrument", "spatial-x", zone="left"))
                elif center_x >= midpoint + neutral_margin:
                    detections.append(DetectionCandidate(KNIFE_ID, box, confidence, "instrument", "spatial-x", zone="right"))

        return detections
