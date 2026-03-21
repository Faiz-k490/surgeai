from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SharedState:
    current_step: int = 1
    current_step_name: str = "Identify zone"
    current_warning: Optional[str] = None
    last_guidance: str = ""
    last_scene_summary: str = ""
    last_frame_jpeg: bytes = b""
    loop_a_alive: bool = False
    last_updated: str = field(default_factory=utc_now_iso)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def update(self, **kwargs: Any) -> None:
        # Single lock keeps state reads/writes coherent across Loop A and API threads.
        with self._lock:
            for key, value in kwargs.items():
                setattr(self, key, value)
            self.last_updated = utc_now_iso()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "current_step": self.current_step,
                "current_step_name": self.current_step_name,
                "current_warning": self.current_warning,
                "last_guidance": self.last_guidance,
                "last_scene_summary": self.last_scene_summary,
                "loop_a_alive": self.loop_a_alive,
                "last_updated": self.last_updated,
            }
