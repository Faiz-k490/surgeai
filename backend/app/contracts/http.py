from typing import Any, Dict


def health_payload(ok: bool, deps: Dict[str, bool]) -> Dict[str, Any]:
    return {"ok": ok, "dependencies": deps}


def session_state_payload(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, "state": snapshot}
