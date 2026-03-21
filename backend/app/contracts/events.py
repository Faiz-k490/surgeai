from datetime import datetime, timezone
from typing import Any, Dict


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_event(event_version: int, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "eventVersion": event_version,
        "timestamp": _ts(),
        "type": event_type,
        "payload": payload,
    }
