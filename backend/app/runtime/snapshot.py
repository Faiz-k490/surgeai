from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import cv2

from app.core.settings import Settings

try:
    from bson.binary import Binary
    from pymongo import MongoClient

    MONGO_AVAILABLE = True
except ImportError:
    Binary = None
    MongoClient = None
    MONGO_AVAILABLE = False


logger = logging.getLogger("surgeai.snapshot")


def extract_512_crop(frame, banana_box: list[float] | None, crop_size: int) -> Any | None:
    if frame is None or banana_box is None:
        return None

    try:
        x1, y1, x2, y2 = banana_box
        center_x = int((x1 + x2) / 2)
        center_y = int((y1 + y2) / 2)
        frame_height, frame_width = frame.shape[:2]
        half = crop_size // 2

        start_x = max(0, center_x - half)
        start_y = max(0, center_y - half)
        end_x = min(frame_width, start_x + crop_size)
        end_y = min(frame_height, start_y + crop_size)

        if end_x - start_x < crop_size:
            start_x = max(0, end_x - crop_size)
        if end_y - start_y < crop_size:
            start_y = max(0, end_y - crop_size)

        crop = frame[start_y:end_y, start_x:end_x]
        if crop.shape[0] < crop_size or crop.shape[1] < crop_size:
            pad_y = crop_size - crop.shape[0]
            pad_x = crop_size - crop.shape[1]
            crop = cv2.copyMakeBorder(crop, 0, pad_y, 0, pad_x, cv2.BORDER_CONSTANT, value=[0, 0, 0])
        return crop
    except Exception as exc:
        logger.error("Failed to extract ROI crop: %s", exc)
        return None


class SnapshotService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="surgeai-snapshot")
        self.storage_dir = settings.backend_root / "artifacts"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._latest_crop_by_session: dict[str, Any] = {}
        self._latest_crop_at_by_session: dict[str, float] = {}
        self._finalized_sessions: set[str] = set()
        self._last_error: str | None = None
        self._last_snapshot_session: str | None = None

        self.mongo_client = None
        self.snapshots_collection = None
        if MONGO_AVAILABLE:
            try:
                self.mongo_client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=1500)
                self.mongo_client.admin.command("ping")
                self.snapshots_collection = self.mongo_client["surgeai"]["snapshots"]
            except Exception as exc:
                self._last_error = f"Mongo unavailable: {exc}"
                self.mongo_client = None
                self.snapshots_collection = None
                logger.warning(self._last_error)
        else:
            self._last_error = "Mongo unavailable: pymongo is not installed"

    def reset_session(self, session_id: str) -> None:
        with self._lock:
            self._latest_crop_by_session.pop(session_id, None)
            self._latest_crop_at_by_session.pop(session_id, None)
            self._finalized_sessions.discard(session_id)

    def monitor_roi(self, session_id: str, frame, banana_box: list[float] | None) -> None:
        crop = extract_512_crop(frame, banana_box, self.settings.snapshot_size)
        if crop is None:
            return
        with self._lock:
            self._latest_crop_by_session[session_id] = crop.copy()
            self._latest_crop_at_by_session[session_id] = time.time()

    def latest_crop_jpeg(self, session_id: str, max_age_seconds: float | None = None) -> tuple[bytes | None, float | None]:
        with self._lock:
            crop = self._latest_crop_by_session.get(session_id)
            captured_at = self._latest_crop_at_by_session.get(session_id)
            if crop is None:
                return None, captured_at
            if max_age_seconds is not None and captured_at is not None and (time.time() - captured_at) > max_age_seconds:
                return None, captured_at
            crop = crop.copy()

        ok, encoded = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            self._last_error = "Failed to encode ROI crop"
            logger.warning(self._last_error)
            return None, captured_at
        return encoded.tobytes(), captured_at

    def finalize_session(self, session_id: str, frame, banana_box: list[float] | None) -> bool:
        with self._lock:
            if session_id in self._finalized_sessions:
                return False
            crop = self._latest_crop_by_session.get(session_id)
            if crop is None:
                crop = extract_512_crop(frame, banana_box, self.settings.snapshot_size)
            if crop is None:
                self._last_error = "Completion snapshot skipped: banana ROI was unavailable"
                logger.warning(self._last_error)
                return False
            self._finalized_sessions.add(session_id)

        self.executor.submit(self._persist_final_snapshot, session_id, crop.copy())
        return True

    def health(self) -> dict[str, Any]:
        return {
            "mongo_connected": self.snapshots_collection is not None,
            "snapshot_bucket": self.settings.snapshot_bucket,
            "last_snapshot_session": self._last_snapshot_session,
            "latest_roi_available": bool(self._latest_crop_by_session),
            "last_error": self._last_error,
        }

    def _persist_final_snapshot(self, session_id: str, crop) -> None:
        timestamp = int(time.time() * 1000)
        filename = f"{session_id}_final_{timestamp}.jpg"
        artifact_path = self.storage_dir / filename
        root_snapshot_path = self.settings.repo_root / "final_snapshot.jpg"

        ok, encoded = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not ok:
            self._last_error = "Failed to encode completion snapshot"
            logger.error(self._last_error)
            return

        jpeg_bytes = encoded.tobytes()
        artifact_path.write_bytes(jpeg_bytes)
        root_snapshot_path.write_bytes(jpeg_bytes)

        if self.snapshots_collection is not None and Binary is not None:
            try:
                self.snapshots_collection.insert_one(
                    {
                        "session_id": session_id,
                        "timestamp": time.time(),
                        "status": "completed",
                        "bucket": self.settings.snapshot_bucket,
                        "bucket_path": f"{self.settings.snapshot_bucket}/{filename}",
                        "artifact_path": str(artifact_path),
                        "image_jpeg": Binary(jpeg_bytes),
                    }
                )
            except Exception as exc:
                self._last_error = f"Mongo write failed: {exc}"
                logger.warning(self._last_error)

        self._last_snapshot_session = session_id
        logger.info("Stored final ROI snapshot for session %s", session_id)
