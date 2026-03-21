"""
Snowflake Cortex COMPLETE() client for surgical guidance generation.

Sends a constrained prompt to Cortex and returns 1-2 sentence clinical
instructions. Falls back to static guidance if the SQL call fails.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

import snowflake.connector

logger = logging.getLogger("surgeai.llm.cortex")

_FALLBACK: Dict[str, str] = {
    "Identify incision zone": "Confirm incision zone location before instrument selection.",
    "Incision": "Use scalpel for shallow incision. Maintain controlled depth.",
    "Clamp application": "Apply clamp to secure incision site. Monitor for bleeding.",
    "Completion": "Procedure complete. Verify tissue alignment and closure.",
}


class CortexGuidanceClient:
    """Generates surgical guidance via Snowflake Cortex COMPLETE()."""

    def __init__(self, settings) -> None:
        self._settings = settings
        self._model = getattr(settings, "cortex_model", None) or os.getenv("CORTEX_MODEL", "mistral-large")
        self._conn: Optional[snowflake.connector.SnowflakeConnection] = None
        self._connect()

    def _connect(self) -> None:
        try:
            self._conn = snowflake.connector.connect(
                account=self._settings.snowflake_account,
                user=self._settings.snowflake_user,
                password=self._settings.snowflake_password,
                warehouse=self._settings.snowflake_warehouse,
                database=self._settings.snowflake_database,
                schema=self._settings.snowflake_schema,
                role=self._settings.snowflake_role,
            )
        except Exception as exc:
            logger.error("Snowflake connection failed: %s", exc)
            self._conn = None

    def ping(self) -> bool:
        if self._conn is None:
            self._connect()
        if self._conn is None:
            return False
        try:
            cur = self._conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            return True
        except Exception:
            return False

    def generate_guidance(
        self,
        step_name: str,
        detected_tool: str,
        event_type: str,
    ) -> str:
        """Build a constrained prompt and call Cortex COMPLETE().

        Falls back to static guidance on any failure.
        """
        prompt = (
            "You are a surgical training assistant.\n"
            "Context: This is a simulated surgery. "
            'The object labeled "banana" represents a human arm.\n'
            f"Current Step: {step_name}\n"
            f"Detected Tool: {detected_tool}\n"
            f"Event: {event_type}\n"
            "Generate a concise (1-2 sentence) clinical instruction. "
            "Be precise, calm, and professional."
        )

        if self._conn is None:
            logger.warning("No Snowflake connection — using fallback guidance.")
            return _FALLBACK.get(step_name, f"Continue with {step_name}.")

        try:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)",
                (self._model, prompt),
            )
            row = cur.fetchone()
            cur.close()
            if row and row[0]:
                text = str(row[0]).strip()
                if text:
                    return text
        except Exception as exc:
            logger.error("Cortex COMPLETE() failed: %s", exc)

        return _FALLBACK.get(step_name, f"Continue with {step_name}.")
