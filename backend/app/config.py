import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Settings:
    gemini_api_key: str
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
    brio_mic_index: int
    loop_a_interval_seconds: int
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

    # Loads local .env values; .env.example documents required keys.
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
        brio_camera_index=int(os.getenv("BRIO_CAMERA_INDEX", "0")),
        brio_mic_index=int(os.getenv("BRIO_MIC_INDEX", "0")),
        loop_a_interval_seconds=int(os.getenv("LOOP_A_INTERVAL_SECONDS", "3")),
        port=int(os.getenv("PORT", "5000")),
        env=os.getenv("ENV", "development"),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
        socket_namespace=os.getenv("SOCKET_NAMESPACE", "/realtime"),
        event_schema_version=int(os.getenv("EVENT_SCHEMA_VERSION", "1")),
    )
