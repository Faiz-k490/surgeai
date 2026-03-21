"""OpenCV camera helpers. On Windows, DirectShow (CAP_DSHOW) is often more reliable than MSMF for USB webcams."""

from __future__ import annotations

import logging
import platform
from typing import Any, Optional, Tuple

import cv2

logger = logging.getLogger("surgeai.vision.camera")


def _try_open(index: int, api_preference: Optional[int], label: str) -> Optional[cv2.VideoCapture]:
    """Open capture and verify we can read at least one frame."""
    try:
        cap = (
            cv2.VideoCapture(index, api_preference)
            if api_preference is not None
            else cv2.VideoCapture(index)
        )
    except Exception as exc:
        logger.debug("VideoCapture(%s, %s) raised: %s", index, label, exc)
        return None
    if not cap.isOpened():
        cap.release()
        return None
    ok, frame = cap.read()
    if not ok or frame is None:
        cap.release()
        return None
    return cap


def open_camera(index: int, backend: str = "auto") -> cv2.VideoCapture:
    """
    Open a camera by index.

    Parameters
    ----------
    index :
        OpenCV device index (0 = default; glasses/Brio often 1 or 2).
    backend :
        ``auto`` — on Windows, try DirectShow first, then MSMF, then default.
        ``dshow`` — force ``cv2.CAP_DSHOW`` (recommended if MSMF spams "can't grab frame").
        ``msmf`` — force Media Foundation.
        ``default`` — OpenCV default backend only.
    """
    b = (backend or "auto").strip().lower()
    candidates: list[tuple[Optional[int], str]] = []

    cap_dshow = getattr(cv2, "CAP_DSHOW", None)
    cap_msmf = getattr(cv2, "CAP_MSMF", None)

    if b == "auto":
        if platform.system() == "Windows":
            # MSMF often opens USB cameras but fails grabFrame (-1072875772); DSHOW is more stable.
            candidates = []
            if cap_dshow is not None:
                candidates.append((cap_dshow, "CAP_DSHOW"))
            if cap_msmf is not None:
                candidates.append((cap_msmf, "CAP_MSMF"))
            candidates.append((None, "default"))
        else:
            candidates = [(None, "default")]
    elif b in ("dshow", "directshow", "ds"):
        candidates = [(cap_dshow, "CAP_DSHOW")] if cap_dshow is not None else [(None, "default")]
    elif b in ("msmf",):
        candidates = [(cap_msmf, "CAP_MSMF")] if cap_msmf is not None else [(None, "default")]
    elif b in ("default", "any"):
        candidates = [(None, "default")]
    else:
        logger.warning("Unknown CAMERA_BACKEND=%r — using default", backend)
        candidates = [(None, "default")]

    last_detail = ""
    for api, label in candidates:
        cap = _try_open(index, api, label)
        if cap is not None:
            logger.info("Opened camera index %s via %s", index, label)
            return cap
        last_detail = f"{label}"

    raise RuntimeError(
        f"Unable to open camera index {index} (last tried: {last_detail}). "
        f"Set BRIO_CAMERA_INDEX to another value, close other apps using the camera, "
        f"or set CAMERA_BACKEND=dshow in backend/.env on Windows."
    )


def probe_camera_index(max_index: int = 3) -> Optional[int]:
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx)
        ok, _ = cap.read()
        cap.release()
        if ok:
            return idx
    return None


def read_encoded_frame(cap: cv2.VideoCapture) -> Tuple[bool, bytes, Any]:
    ok, frame = cap.read()
    if not ok:
        return False, b"", None
    enc_ok, buf = cv2.imencode(".jpg", frame)
    if not enc_ok:
        return False, b"", frame
    return True, buf.tobytes(), frame
