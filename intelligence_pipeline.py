"""
Compatibility shim — canonical implementation lives in `backend.app.loop_b.intelligence_pipeline`.
"""

try:
    from backend.app.loop_b.intelligence_pipeline import *  # noqa: F403
except ModuleNotFoundError as _e:
    if getattr(_e, "name", None) not in ("backend", "app"):
        raise
    from app.loop_b.intelligence_pipeline import *  # noqa: F403
