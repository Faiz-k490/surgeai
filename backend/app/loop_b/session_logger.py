"""
session_logger.py — MongoDB Atlas session logging for SurgeAI.

Persists every Q&A exchange (question, answer, timestamp) to a MongoDB
collection so the React frontend can render session history.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache

from pymongo import MongoClient

logger = logging.getLogger("surgeai.session")

# ── Constants ────────────────────────────────────────────────────────────────

DB_NAME = "surgeai"
COLLECTION_NAME = "qa_sessions"


@lru_cache(maxsize=1)
def _get_collection():
    """
    Return the MongoDB collection handle, lazily creating the client once.
    The connection is cached for the lifetime of the process.
    """
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI is not set.")

    client = MongoClient(uri)
    db = client[DB_NAME]
    return db[COLLECTION_NAME]


def _blocking_log(question: str, answer: str) -> None:
    """
    Synchronous MongoDB insert — meant to be called inside a thread executor
    so it never blocks the asyncio event loop.
    """
    try:
        collection = _get_collection()
        doc = {
            "question": question,
            "answer": answer,
            "timestamp": datetime.now(timezone.utc),
        }
        result = collection.insert_one(doc)
        logger.info("Session logged → _id=%s", result.inserted_id)
    except Exception as exc:
        logger.error("MongoDB session log failed: %s", exc)


async def log_qa(question: str, answer: str) -> None:
    """
    Non-blocking async wrapper around the synchronous PyMongo insert.
    Offloads the write to a thread so the event loop stays free.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _blocking_log, question, answer)
