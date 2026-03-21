"""
Local YOLOv8-nano object detection for surgical demo.

Runs entirely on CPU at 20-30+ FPS. No API calls.
Maps COCO classes to demo surgical labels.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger("surgeai.vision.yolo")

# COCO class IDs -> demo surgical labels
_COCO_MAP: Dict[int, str] = {
    46: "banana",       # patient arm stand-in
    43: "knife",        # xacto knife -> scalpel
    76: "scissors",     # scissors -> clamp
    42: "fork",         # fork -> forceps
}

# Display labels shown on HUD
_DISPLAY_LABELS: Dict[str, str] = {
    "banana": "patient arm",
    "knife": "scalpel",
    "scissors": "clamp",
    "fork": "forceps",
}

# Which COCO labels count as "surgical tools" (for wrong-tool detection)
_TOOL_COCO_NAMES = {"knife", "scissors", "fork"}

# Extra COCO classes that should trigger "wrong_tool" if visible
_WRONG_TOOL_COCO_IDS = {
    # spoon, bowl, cup, bottle, cell phone — common desk objects
    44, 45, 41, 39, 67,
}


class YoloDetector:
    """YOLOv8-nano detector with COCO-to-surgical class mapping."""

    def __init__(self, model_path: str = "yolov8n.pt", confidence: float = 0.4) -> None:
        from ultralytics import YOLO
        self._model = YOLO(model_path)
        self._conf = confidence
        self._names: Dict[int, str] = self._model.names or {}
        logger.info(
            "YOLO loaded: %s (%d classes, conf=%.2f)",
            model_path,
            len(self._names),
            confidence,
        )

    def ping(self) -> bool:
        return self._model is not None

    def detect(self, frame: np.ndarray) -> Dict[str, Any]:
        """Run detection on a BGR numpy frame.

        Returns dict with:
            objects  – list of {label, display_label, confidence, x, y}
            ar_boxes – list of {x, y, width, height, label, confidence} (normalized 0-1)
        """
        h, w = frame.shape[:2]
        results = self._model.predict(
            frame,
            conf=self._conf,
            verbose=False,
            imgsz=640,
        )

        objects: List[Dict[str, Any]] = []
        ar_boxes: List[Dict[str, Any]] = []

        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                conf = float(boxes.conf[i].item())
                coco_name = self._names.get(cls_id, "")

                # Map to surgical label
                if cls_id in _COCO_MAP:
                    label = _COCO_MAP[cls_id]
                elif cls_id in _WRONG_TOOL_COCO_IDS:
                    label = "wrong_tool"
                else:
                    continue

                display = _DISPLAY_LABELS.get(label, label)

                # Normalized bounding box (xyxy -> xywh normalized)
                x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                nx = x1 / w
                ny = y1 / h
                nw = (x2 - x1) / w
                nh = (y2 - y1) / h

                objects.append({
                    "label": label,
                    "display_label": display,
                    "confidence": round(conf, 3),
                    "x": round(nx, 4),
                    "y": round(ny, 4),
                })

                ar_boxes.append({
                    "x": round(nx, 4),
                    "y": round(ny, 4),
                    "width": round(nw, 4),
                    "height": round(nh, 4),
                    "label": display,
                    "confidence": round(conf, 3),
                })

        return {"objects": objects, "ar_boxes": ar_boxes}
