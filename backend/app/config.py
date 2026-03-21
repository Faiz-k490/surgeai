"""
Backward-compatible re-exports.

Prefer `from backend.app.core.settings import Settings, load_settings` in new code.
"""

try:
    from backend.app.core.settings import Settings, load_settings
except ModuleNotFoundError:
    from app.core.settings import Settings, load_settings

__all__ = ["Settings", "load_settings"]
