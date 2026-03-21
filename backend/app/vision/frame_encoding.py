"""Helpers for capture FPS and a single-slot latest frame buffer for throttled VLM."""

from __future__ import annotations

import threading
import time
from typing import Any, Optional, Tuple

import cv2


def encode_jpeg(frame: Any, quality: int) -> Tuple[bool, bytes]:
    q = max(1, min(100, int(quality)))
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), q])
    if not ok:
        return False, b""
    return True, buf.tobytes()


class LatestFrameBuffer:
    """Thread-safe latest (jpeg, raw_frame) pair for VLM; capture always overwrites."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: Optional[Tuple[bytes, Any]] = None

    def put(self, jpeg_bytes: bytes, frame: Any) -> None:
        with self._lock:
            self._data = (jpeg_bytes, frame)

    def get(self) -> Optional[Tuple[bytes, Any]]:
        with self._lock:
            return self._data


def sleep_until_next_frame(start: float, target_fps: float) -> None:
    if target_fps <= 0:
        return
    interval = 1.0 / target_fps
    elapsed = time.time() - start
    remain = interval - elapsed
    if remain > 0:
        time.sleep(remain)
