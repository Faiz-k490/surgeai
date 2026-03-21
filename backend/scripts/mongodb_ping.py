"""
Quick MongoDB Atlas connectivity check.

Usage from repo root:
  .\.venv311\Scripts\python backend\scripts\mongodb_ping.py
"""

from pathlib import Path
import sys

# Allow "from app..." imports when script is run directly from repo root.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import load_settings
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi


def main() -> int:
    settings = load_settings()
    client = MongoClient(settings.mongodb_uri, server_api=ServerApi("1"))
    client.admin.command("ping")
    print("MongoDB ping successful.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
