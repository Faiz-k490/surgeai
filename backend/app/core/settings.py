"""Application settings loaded from environment (see `backend/.env`)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_BACKEND_ENV)
load_dotenv()


@dataclass
class Settings:
    elevenlabs_api_key: str
    snowflake_account: str
    snowflake_user: str
    snowflake_password: str
    snowflake_warehouse: str
    snowflake_database: str
    snowflake_schema: str
    snowflake_role: str
    mongodb_uri: str
    mongodb_db_name: str
    brio_camera_index: int
    camera_backend: str
    brio_mic_index: int
    loop_a_interval_seconds: float
    capture_target_fps: float
    vlm_max_hz: float
    vlm_jpeg_quality: int
    guidance_min_interval_seconds: float
    yolo_model: str
    yolo_confidence_threshold: float
    cortex_model: str
    loop_b_enabled: bool
    port: int
    env: str
    frontend_origin: str
    socket_namespace: str
    event_schema_version: int


def _must(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value == "replace_me":
        raise ValueError(f"Missing required env var: {name}")
    return value


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        elevenlabs_api_key=_must("ELEVENLABS_API_KEY"),
        snowflake_account=_must("SNOWFLAKE_ACCOUNT"),
        snowflake_user=_must("SNOWFLAKE_USER"),
        snowflake_password=_must("SNOWFLAKE_PASSWORD"),
        snowflake_warehouse=_must("SNOWFLAKE_WAREHOUSE"),
        snowflake_database=_must("SNOWFLAKE_DATABASE"),
        snowflake_schema=_must("SNOWFLAKE_SCHEMA"),
        snowflake_role=_must("SNOWFLAKE_ROLE"),
        mongodb_uri=_must("MONGODB_URI"),
        mongodb_db_name=os.getenv("MONGODB_DB_NAME", "surgeai"),
        brio_camera_index=int(os.getenv("BRIO_CAMERA_INDEX", "0")),
        camera_backend=os.getenv("CAMERA_BACKEND", "auto").strip().lower() or "auto",
        brio_mic_index=int(os.getenv("BRIO_MIC_INDEX", "0")),
        loop_a_interval_seconds=float(os.getenv("LOOP_A_INTERVAL_SECONDS", "0")),
        capture_target_fps=float(os.getenv("CAPTURE_TARGET_FPS", "30")),
        vlm_max_hz=float(os.getenv("VLM_MAX_HZ", "2")),
        vlm_jpeg_quality=int(os.getenv("VLM_JPEG_QUALITY", "65")),
        guidance_min_interval_seconds=float(os.getenv("GUIDANCE_MIN_INTERVAL_SECONDS", "5")),
        yolo_model=os.getenv("YOLO_MODEL", "yolov8n.pt"),
        yolo_confidence_threshold=float(os.getenv("YOLO_CONFIDENCE", "0.4")),
        cortex_model=os.getenv("CORTEX_MODEL", "mistral-large"),
        loop_b_enabled=os.getenv("LOOP_B_ENABLED", "true").lower() in ("1", "true", "yes"),
        port=int(os.getenv("PORT", "5000")),
        env=os.getenv("ENV", "development"),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
        socket_namespace=os.getenv("SOCKET_NAMESPACE", "/realtime"),
        event_schema_version=int(os.getenv("EVENT_SCHEMA_VERSION", "1")),
    )
