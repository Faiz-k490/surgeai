from typing import Any, Dict


class MongoEventLogger:
    def __init__(self, _settings):
        self.settings = _settings

    def log_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        # TODO: Insert event document into MongoDB Atlas collection.
        _ = (event_name, payload)
