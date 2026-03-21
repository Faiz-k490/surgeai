from typing import Any, Optional, Tuple

import cv2


def open_camera(index: int) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open camera index {index}")
    return cap


def probe_camera_index(max_index: int = 3) -> Optional[int]:
    # Probe 0..max_index-1 so setup is easy on laptops with multiple webcams.
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
