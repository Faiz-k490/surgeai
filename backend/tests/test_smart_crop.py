"""Unit tests for smart_crop._extract_best_box — validates both key formats."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.vision.smart_crop import _extract_best_box


def test_yolo_style_keys():
    """YOLO detector outputs {x, y, width, height} — standard format."""
    boxes = [{"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4, "confidence": 0.95, "label": "banana"}]
    cx, cy, side = _extract_best_box(720, 1280, boxes)
    # Centre should be at (0.1 + 0.15) * 1280 = 320, (0.2 + 0.2) * 720 = 288
    assert abs(cx - 320.0) < 1.0, f"cx={cx}"
    assert abs(cy - 288.0) < 1.0, f"cy={cy}"
    assert side > 0, f"side should be positive, got {side}"


def test_gemini_style_keys():
    """Gemini returns {x, y, w, h} — the format that was previously broken."""
    boxes = [{"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4, "confidence": 0.95, "label": "banana"}]
    cx, cy, side = _extract_best_box(720, 1280, boxes)
    assert abs(cx - 320.0) < 1.0, f"cx={cx}"
    assert abs(cy - 288.0) < 1.0, f"cy={cy}"
    assert side > 0, f"side should be positive, got {side}"


def test_both_formats_produce_same_result():
    """Both key formats should yield identical results."""
    yolo_box = [{"x": 0.25, "y": 0.30, "width": 0.5, "height": 0.4, "confidence": 0.9}]
    gemini_box = [{"x": 0.25, "y": 0.30, "w": 0.5, "h": 0.4, "confidence": 0.9}]
    r1 = _extract_best_box(480, 640, yolo_box)
    r2 = _extract_best_box(480, 640, gemini_box)
    assert r1 == r2, f"Mismatch: YOLO={r1} vs Gemini={r2}"


def test_empty_boxes_fallback():
    """No boxes → centre of frame, side = min(h, w)."""
    cx, cy, side = _extract_best_box(480, 640, [])
    assert abs(cx - 320.0) < 1.0
    assert abs(cy - 240.0) < 1.0
    assert abs(side - 480.0) < 1.0  # min(480, 640)
