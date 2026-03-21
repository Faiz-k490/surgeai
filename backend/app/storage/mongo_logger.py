from datetime import datetime, timezone
from typing import Any, Dict

from pymongo import MongoClient
from pymongo.errors import PyMongoError
from pymongo.server_api import ServerApi


class MongoEventLogger:
    def __init__(self, settings):
        self.settings = settings
        self.client = MongoClient(settings.mongodb_uri, server_api=ServerApi("1"))
        self.db = self.client[settings.mongodb_db_name]
        self.collection = self.db["events"]

    def ping(self) -> bool:
        try:
            self.client.admin.command("ping")
            return True
        except PyMongoError:
            return False

    def log_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        try:
            # Store minimal structured event data for replay and debugging.
            self.collection.insert_one(
                {
                    "event_name": event_name,
                    "payload": payload,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        except PyMongoError:
            # Logging failures should not break the live Loop A demo path.
            return
