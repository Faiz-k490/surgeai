"""Core domain: settings and shared runtime state."""

from .settings import Settings, load_settings
from .state import SharedState, utc_now_iso

__all__ = ["Settings", "SharedState", "load_settings", "utc_now_iso"]
