"""OpenCV camera helpers with auto-detection for external USB webcams (Brio).

On Windows, DirectShow (CAP_DSHOW) is often more reliable than MSMF for USB webcams.
"""

from __future__ import annotations

import logging
import platform
import subprocess
from typing import Any, Optional, Tuple

import cv2

logger = logging.getLogger("surgeai.vision.camera")

# Substrings that identify the glasses/external webcam (case-insensitive)
_EXTERNAL_CAM_KEYWORDS = ["brio", "logitech", "usb camera", "external"]


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


def _get_camera_device_names_windows() -> list[str]:
    """Return a list of camera friendly-names in PnP device order via PowerShell."""
    try:
        r = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "Get-PnpDevice -Class Camera -Status OK | Select-Object -ExpandProperty FriendlyName",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        names = [n.strip() for n in r.stdout.strip().splitlines() if n.strip()]
        return names
    except Exception as exc:
        logger.debug("Could not enumerate camera devices: %s", exc)
        return []


def _find_external_camera_index(max_index: int = 5) -> Optional[int]:
    """Auto-detect the external USB webcam index.

    Strategy:
      1. On Windows, list PnP camera device names and match against keywords.
         The PnP order often (but not always) matches OpenCV's index order.
      2. If an external camera name is found, try that index first.
      3. Fall back to probing indices 0..max_index and preferring the highest
         index that opens successfully (USB cameras are usually enumerated after
         the integrated camera).
    """
    if platform.system() == "Windows":
        names = _get_camera_device_names_windows()
        logger.info("Detected cameras: %s", names)
        for i, name in enumerate(names):
            low = name.lower()
            if any(kw in low for kw in _EXTERNAL_CAM_KEYWORDS):
                logger.info("External camera '%s' found at PnP index %d", name, i)
                return i

    # Fallback: probe and pick the highest working index (likely the USB cam)
    best: Optional[int] = None
    cap_dshow = getattr(cv2, "CAP_DSHOW", None)
    for idx in range(max_index):
        api = cap_dshow if (platform.system() == "Windows" and cap_dshow is not None) else None
        cap = _try_open(idx, api, "probe")
        if cap is not None:
            cap.release()
            best = idx
    return best


def open_camera(index: int, backend: str = "auto") -> cv2.VideoCapture:
    """
    Open a camera by index, with automatic external-webcam detection.

    If ``index`` is -1 (or the env var ``BRIO_CAMERA_INDEX`` is set to -1),
    the system will auto-detect the external USB webcam.

    Parameters
    ----------
    index :
        OpenCV device index. Use ``-1`` for auto-detect external webcam.
    backend :
        ``auto`` — on Windows, try DirectShow first, then MSMF, then default.
        ``dshow`` — force ``cv2.CAP_DSHOW``.
        ``msmf`` — force Media Foundation.
        ``default`` — OpenCV default backend only.
    """
    # Auto-detect external webcam
    if index < 0:
        detected = _find_external_camera_index()
        if detected is not None:
            logger.info("Auto-detected external webcam at index %d", detected)
            index = detected
        else:
            logger.warning("Could not auto-detect external webcam — falling back to index 0")
            index = 0
    else:
        # Even with a specified index, try to find external camera first
        detected = _find_external_camera_index()
        if detected is not None and detected != index:
            logger.info(
                "External webcam detected at index %d (overriding configured index %d)",
                detected, index,
            )
            index = detected

    b = (backend or "auto").strip().lower()
    candidates: list[tuple[Optional[int], str]] = []

    cap_dshow = getattr(cv2, "CAP_DSHOW", None)
    cap_msmf = getattr(cv2, "CAP_MSMF", None)

    if b == "auto":
        if platform.system() == "Windows":
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
        f"Close other apps using the camera, or check that the Brio/external webcam is connected."
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
