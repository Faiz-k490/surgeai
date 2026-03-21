"""
Compatibility shim — canonical implementation lives in `backend.app.loop_b.session_logger`.
"""

try:
    from backend.app.loop_b.session_logger import *  # noqa: F403
except ModuleNotFoundError as _e:
    if getattr(_e, "name", None) not in ("backend", "app"):
        raise
    from app.loop_b.session_logger import *  # noqa: F403
