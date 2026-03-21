"""Application settings loaded from environment (see `backend/.env`)."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load `backend/.env` even when the process is started from the repo root.
_BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_BACKEND_ENV)
load_dotenv()


@dataclass
class Settings:
    gemini_api_key: str
    gemini_model: str
    groq_api_key: str
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
    # Windows: use "dshow" if MSMF logs "can't grab frame" (-1072875772); "auto" tries DSHOW then MSMF.
    camera_backend: str
    brio_mic_index: int
    loop_a_interval_seconds: float
    capture_target_fps: float
    vlm_max_hz: float
    vlm_jpeg_quality: int
    guidance_min_interval_seconds: float
    # After Gemini errors, pause VLM calls to avoid burning quota (seconds).
    gemini_rate_limit_backoff_seconds: float
    gemini_error_backoff_seconds: float
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
    # Snowflake connector wheel support is currently reliable on 3.11-3.13 here.
    if sys.version_info >= (3, 14):
        raise RuntimeError(
            "Python 3.14 is not supported for this backend environment yet. "
            "Use Python 3.11 or 3.13 for dependency compatibility."
        )

    load_dotenv()
    return Settings(
        gemini_api_key=_must("GEMINI_API_KEY"),
        groq_api_key=_must("GROQ_API_KEY"),
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
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        brio_camera_index=int(os.getenv("BRIO_CAMERA_INDEX", "0")),
        camera_backend=os.getenv("CAMERA_BACKEND", "auto").strip().lower() or "auto",
        brio_mic_index=int(os.getenv("BRIO_MIC_INDEX", "0")),
        loop_a_interval_seconds=float(os.getenv("LOOP_A_INTERVAL_SECONDS", "0")),
        capture_target_fps=float(os.getenv("CAPTURE_TARGET_FPS", "20")),
        # Default ~1 Gemini vision call per 5s — raise VLM_MAX_HZ only when you need snappier VLM.
        vlm_max_hz=float(os.getenv("VLM_MAX_HZ", "0.2")),
        vlm_jpeg_quality=int(os.getenv("VLM_JPEG_QUALITY", "65")),
        guidance_min_interval_seconds=float(os.getenv("GUIDANCE_MIN_INTERVAL_SECONDS", "10")),
        gemini_rate_limit_backoff_seconds=float(os.getenv("GEMINI_RATE_LIMIT_BACKOFF_SECONDS", "120")),
        gemini_error_backoff_seconds=float(os.getenv("GEMINI_ERROR_BACKOFF_SECONDS", "30")),
        loop_b_enabled=os.getenv("LOOP_B_ENABLED", "true").lower() in ("1", "true", "yes"),
        port=int(os.getenv("PORT", "5000")),
        env=os.getenv("ENV", "development"),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
        socket_namespace=os.getenv("SOCKET_NAMESPACE", "/realtime"),
        event_schema_version=int(os.getenv("EVENT_SCHEMA_VERSION", "1")),
    )
