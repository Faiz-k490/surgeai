from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent

load_dotenv(BACKEND_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    port: int
    namespace: str
    frontend_origin: str
    yolo_model_path: str
    yolo_confidence: float
    inference_image_size: int
    camera_index: int
    camera_label: str
    frame_width: int
    frame_height: int
    target_fps: int
    neutral_zone_ratio: float
    track_ttl_seconds: float
    smoothing_alpha: float
    banana_stable_seconds: float
    tool_stable_seconds: float
    confirmation_pause_seconds: float
    scalpel_contact_seconds: float
    surgery_window_seconds: float
    clamp_window_seconds: float
    mongodb_uri: str
    openai_api_key: str
    openai_vision_model: str
    elevenlabs_api_key: str
    elevenlabs_stt_model: str
    elevenlabs_tts_model: str
    elevenlabs_tts_voice_id: str
    voice_chunk_ms: int
    voice_silence_ms: int
    vlm_cooldown_seconds: float
    major_scene_cooldown_seconds: float
    response_dedupe_seconds: float
    snapshot_bucket: str
    snapshot_size: int
    repo_root: Path
    backend_root: Path


def load_settings() -> Settings:
    yolo_model = os.getenv("YOLO_MODEL", "yolov8n.pt")
    yolo_path = Path(yolo_model)
    if not yolo_path.is_absolute():
        yolo_path = (BACKEND_ROOT / yolo_path).resolve()

    namespace = os.getenv("SOCKET_NAMESPACE", "/realtime").strip() or "/realtime"
    if not namespace.startswith("/"):
        namespace = f"/{namespace}"

    return Settings(
        port=int(os.getenv("PORT", "5000")),
        namespace=namespace,
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
        yolo_model_path=str(yolo_path),
        yolo_confidence=float(os.getenv("YOLO_CONFIDENCE", "0.3")),
        inference_image_size=int(os.getenv("INFERENCE_IMAGE_SIZE", "512")),
        camera_index=int(os.getenv("CAMERA_INDEX", "1")),
        camera_label=os.getenv("CAMERA_DEVICE_LABEL", "Logitech BRIO"),
        frame_width=int(os.getenv("FRAME_WIDTH", "640")),
        frame_height=int(os.getenv("FRAME_HEIGHT", "480")),
        target_fps=int(os.getenv("TARGET_FPS", "30")),
        neutral_zone_ratio=float(os.getenv("NEUTRAL_ZONE_RATIO", "0.08")),
        track_ttl_seconds=float(os.getenv("TRACK_TTL_SECONDS", "0.65")),
        smoothing_alpha=float(os.getenv("TRACK_SMOOTHING_ALPHA", "0.72")),
        banana_stable_seconds=float(os.getenv("BANANA_STABLE_SECONDS", "2.5")),
        tool_stable_seconds=float(os.getenv("TOOL_STABLE_SECONDS", "2.5")),
        confirmation_pause_seconds=float(os.getenv("CONFIRMATION_PAUSE_SECONDS", "2.0")),
        scalpel_contact_seconds=float(os.getenv("SCALPEL_CONTACT_SECONDS", "2.5")),
        surgery_window_seconds=float(os.getenv("SURGERY_WINDOW_SECONDS", "10.0")),
        clamp_window_seconds=float(os.getenv("CLAMP_WINDOW_SECONDS", "10.0")),
        mongodb_uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_vision_model=os.getenv("OPENAI_VISION_MODEL", "gpt-4-vision-preview").strip(),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", "").strip(),
        elevenlabs_stt_model=os.getenv("ELEVENLABS_STT_MODEL", "scribe_v1").strip(),
        elevenlabs_tts_model=os.getenv("ELEVENLABS_TTS_MODEL", "eleven_turbo_v2_5").strip(),
        elevenlabs_tts_voice_id=os.getenv("ELEVENLABS_TTS_VOICE_ID", "").strip(),
        voice_chunk_ms=int(os.getenv("VOICE_CHUNK_MS", "250")),
        voice_silence_ms=int(os.getenv("VOICE_SILENCE_MS", "1200")),
        vlm_cooldown_seconds=float(os.getenv("VLM_COOLDOWN_SECONDS", "2.5")),
        major_scene_cooldown_seconds=float(os.getenv("MAJOR_SCENE_COOLDOWN_SECONDS", "2.5")),
        response_dedupe_seconds=float(os.getenv("RESPONSE_DEDUPE_SECONDS", "8.0")),
        snapshot_bucket=os.getenv("SNAPSHOT_BUCKET", "surgeai-snapshots"),
        snapshot_size=int(os.getenv("SNAPSHOT_SIZE", "512")),
        repo_root=REPO_ROOT,
        backend_root=BACKEND_ROOT,
    )


settings = load_settings()
