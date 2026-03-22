"""Dynamic-zoom smart crop with EMA temporal smoothing.

Pipeline per frame
------------------
1. Extract the highest-confidence YOLO bounding box (cx, cy, box_w, box_h).
2. Compute a square crop whose side = max(box_w, box_h) * PADDING_FACTOR.
3. Apply Exponential Moving Average to (cx, cy, crop_side) to prevent jitter.
4. Clamp the square against the frame boundary — never out-of-bounds.
5. Slice the square out of the source frame.
6. Upscale to OUTPUT_SIZE x OUTPUT_SIZE with INTER_CUBIC.
7. Encode as JPEG and return bytes.

Coordinate convention for yolo_boxes dicts
-------------------------------------------
  x, y        -- top-left corner, *normalised* (0-1) relative to frame
  width, height -- box dimensions, *normalised* (0-1) relative to frame
  confidence  -- float 0-1
  label       -- str
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("surgeai.vision.smart_crop")

# ── tuneable constants ────────────────────────────────────────────────────────
OUTPUT_SIZE: int = 512          # final output resolution (px)
PADDING_FACTOR: float = 1.5     # enlarge the tight box by this factor
EMA_ALPHA: float = 0.30         # smoothing weight: higher = snappier, lower = smoother
MIN_CROP_FRACTION: float = 0.20 # smallest crop relative to frame (avoids tiny boxes)
JPEG_QUALITY: int = 85

# legacy alias so callers that import CROP_SIZE still work
CROP_SIZE: int = OUTPUT_SIZE


# ── internal helpers ──────────────────────────────────────────────────────────

def _extract_best_box(
    frame_h: int,
    frame_w: int,
    yolo_boxes: List[Dict[str, Any]],
) -> Tuple[float, float, float]:
    """Return (cx_px, cy_px, side_px) for the highest-confidence box.

    Falls back to frame centre / full-frame if no boxes are supplied.
    All returned values are in *pixel* units.
    """
    if not yolo_boxes:
        return frame_w / 2.0, frame_h / 2.0, float(min(frame_h, frame_w))

    best = max(yolo_boxes, key=lambda b: float(b.get("confidence", 0.0)))

    # normalised top-left + size → pixel centre
    bx = float(best.get("x", 0.0))
    by = float(best.get("y", 0.0))
    bw = float(best.get("width", 0.0) or best.get("w", 0.0))
    bh = float(best.get("height", 0.0) or best.get("h", 0.0))

    cx_px = (bx + bw / 2.0) * frame_w
    cy_px = (by + bh / 2.0) * frame_h

    box_w_px = bw * frame_w
    box_h_px = bh * frame_h

    # padded square side — at least MIN_CROP_FRACTION of the shorter frame dim
    padded = max(box_w_px, box_h_px) * PADDING_FACTOR
    min_side = min(frame_h, frame_w) * MIN_CROP_FRACTION
    side_px = max(padded, min_side)

    logger.debug(
        "Best box: label=%s conf=%.2f box=%dx%d -> padded_side=%.0f",
        best.get("label", "?"),
        best.get("confidence", 0.0),
        int(box_w_px),
        int(box_h_px),
        side_px,
    )
    return cx_px, cy_px, side_px


def _clamp_square(
    cx: float,
    cy: float,
    side: float,
    frame_h: int,
    frame_w: int,
) -> Tuple[int, int, int]:
    """Return (x1, y1, clamped_side) — integer pixel coords, never out-of-bounds."""
    half = side / 2.0

    # desired origin
    x1 = cx - half
    y1 = cy - half

    # clamp so the square fits entirely inside the frame
    x1 = max(0.0, min(x1, frame_w - side))
    y1 = max(0.0, min(y1, frame_h - side))

    # side must not exceed the frame dimensions (e.g. tiny frame)
    side = min(side, float(frame_w), float(frame_h))

    return int(round(x1)), int(round(y1)), int(round(side))


def _zoom_crop(
    frame: np.ndarray,
    cx: float,
    cy: float,
    side: float,
) -> np.ndarray:
    """Slice a square out of *frame* and upscale to OUTPUT_SIZE × OUTPUT_SIZE."""
    fh, fw = frame.shape[:2]
    x1, y1, s = _clamp_square(cx, cy, side, fh, fw)
    s = max(s, 1)  # guard against degenerate boxes

    crop = frame[y1 : y1 + s, x1 : x1 + s]

    if crop.shape[0] != OUTPUT_SIZE or crop.shape[1] != OUTPUT_SIZE:
        interp = cv2.INTER_CUBIC if s < OUTPUT_SIZE else cv2.INTER_LINEAR
        crop = cv2.resize(crop, (OUTPUT_SIZE, OUTPUT_SIZE), interpolation=interp)

    return np.ascontiguousarray(crop)


def encode_crop_jpeg(crop: np.ndarray, quality: int = JPEG_QUALITY) -> bytes:
    ok, buf = cv2.imencode(
        ".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), max(1, min(100, quality))]
    )
    if not ok or buf is None:
        raise RuntimeError("cv2.imencode failed for smart crop")
    return buf.tobytes()


# ── stateless entry point (no EMA — for one-shot use) ────────────────────────

def smart_crop_jpeg(
    frame: np.ndarray,
    yolo_boxes: Optional[List[Dict[str, Any]]] = None,
    quality: int = JPEG_QUALITY,
) -> bytes:
    """Single-frame dynamic zoom crop without temporal smoothing."""
    fh, fw = frame.shape[:2]
    cx, cy, side = _extract_best_box(fh, fw, yolo_boxes or [])
    crop = _zoom_crop(frame, cx, cy, side)
    return encode_crop_jpeg(crop, quality)


# ── stateful class with EMA smoothing (preferred for live video) ─────────────

class SmartCropper:
    """Per-instance EMA state prevents zoom jitter across consecutive frames.

    Usage
    -----
    cropper = SmartCropper()
    jpeg_bytes = cropper.detect_and_crop(frame, yolo_boxes)   # sync
    jpeg_bytes = await cropper.async_detect_and_crop(frame, yolo_boxes)  # async
    """

    def __init__(
        self,
        jpeg_quality: int = JPEG_QUALITY,
        ema_alpha: float = EMA_ALPHA,
        max_workers: int = 2,
    ) -> None:
        self._quality = jpeg_quality
        self._alpha = ema_alpha
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="smart_crop"
        )

        # EMA state — None until the first frame initialises them
        self._ema_cx: Optional[float] = None
        self._ema_cy: Optional[float] = None
        self._ema_side: Optional[float] = None

        # Overlay state — updated every crop, read by run_capture for HUD drawing
        self._overlay_box: Optional[Tuple[int, int, int, int]] = None  # x1,y1,x2,y2
        self._overlay_label: str = ""

        logger.info(
            "SmartCropper ready (output=%dpx jpeg_quality=%d ema_alpha=%.2f workers=%d)",
            OUTPUT_SIZE,
            jpeg_quality,
            ema_alpha,
            max_workers,
        )

    # ── EMA update ────────────────────────────────────────────────────────────

    def _ema_update(self, cx: float, cy: float, side: float) -> Tuple[float, float, float]:
        """Update EMA state and return smoothed (cx, cy, side)."""
        if self._ema_cx is None:
            # first frame — initialise directly, no smoothing
            self._ema_cx, self._ema_cy, self._ema_side = cx, cy, side
        else:
            a = self._alpha
            self._ema_cx   = a * cx   + (1 - a) * self._ema_cx
            self._ema_cy   = a * cy   + (1 - a) * self._ema_cy
            self._ema_side = a * side + (1 - a) * self._ema_side

        return self._ema_cx, self._ema_cy, self._ema_side  # type: ignore[return-value]

    # ── core crop (with EMA) ─────────────────────────────────────────────────

    def _crop(
        self,
        frame: np.ndarray,
        yolo_boxes: Optional[List[Dict[str, Any]]],
    ) -> bytes:
        fh, fw = frame.shape[:2]
        raw_cx, raw_cy, raw_side = _extract_best_box(fh, fw, yolo_boxes or [])
        s_cx, s_cy, s_side = self._ema_update(raw_cx, raw_cy, raw_side)

        crop = _zoom_crop(frame, s_cx, s_cy, s_side)
        jpeg = encode_crop_jpeg(crop, self._quality)

        # Store overlay for the MJPEG visualisation thread
        x1, y1, s = _clamp_square(s_cx, s_cy, s_side, fh, fw)
        self._overlay_box = (x1, y1, x1 + s, y1 + s)
        if yolo_boxes:
            best = max(yolo_boxes, key=lambda b: float(b.get("confidence", 0.0)))
            conf = float(best.get("confidence", 0.0))
            self._overlay_label = f"{best.get('label','?')}  {conf:.0%}"
        else:
            self._overlay_label = ""

        logger.debug(
            "DynZoom: raw=(%.0f,%.0f,%.0f) smooth=(%.0f,%.0f,%.0f) jpeg=%d B",
            raw_cx, raw_cy, raw_side,
            s_cx, s_cy, s_side,
            len(jpeg),
        )
        return jpeg

    # ── public API ────────────────────────────────────────────────────────────

    def detect_and_crop(
        self,
        frame: np.ndarray,
        yolo_boxes: Optional[List[Dict[str, Any]]] = None,
    ) -> bytes:
        """Synchronous — safe to call from any thread (not the asyncio loop)."""
        return self._crop(frame, yolo_boxes)

    async def async_detect_and_crop(
        self,
        frame: np.ndarray,
        yolo_boxes: Optional[List[Dict[str, Any]]] = None,
    ) -> bytes:
        """Async — runs the CPU work in the thread pool, non-blocking."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor, self._crop, frame, yolo_boxes
        )

    def get_overlay(self) -> Optional[Tuple[Tuple[int, int, int, int], str]]:
        """Return ((x1,y1,x2,y2), label) of the current smoothed crop box.

        Returns None until the first frame has been processed.
        Safe to call from any thread — reads are atomic on CPython.
        """
        box = self._overlay_box
        if box is None:
            return None
        return box, self._overlay_label

    def reset_ema(self) -> None:
        """Force EMA state reset (e.g. after a scene cut or camera swap)."""
        self._ema_cx = self._ema_cy = self._ema_side = None
        logger.info("SmartCropper EMA state reset")

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)
        logger.info("SmartCropper executor shut down")
