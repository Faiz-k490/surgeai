"""In-process shared state for Loop A / API threads."""

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
    last_question: str = ""
    last_answer: str = ""
    loop_a_alive: bool = False
    metrics_fps: float = 0.0
    metrics_latency_ms: int = 0
    last_updated: str = field(default_factory=utc_now_iso)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def update(self, **kwargs: Any) -> None:
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
                "last_question": self.last_question,
                "last_answer": self.last_answer,
                "loop_a_alive": self.loop_a_alive,
                "metrics_fps": self.metrics_fps,
                "metrics_latency_ms": self.metrics_latency_ms,
                "last_updated": self.last_updated,
            }
