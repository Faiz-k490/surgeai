"""
Backward-compatible re-exports.

Prefer `from backend.app.core.state import SharedState` in new code.
"""

try:
    from backend.app.core.state import SharedState, utc_now_iso
except ModuleNotFoundError:
    from app.core.state import SharedState, utc_now_iso

__all__ = ["SharedState", "utc_now_iso"]
