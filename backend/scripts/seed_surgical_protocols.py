"""
Seed SURGICAL_PROTOCOLS table for Loop A grounding.

Usage from repo root:
  .\.venv311\Scripts\python backend\scripts\seed_surgical_protocols.py
"""

from pathlib import Path
import sys

import snowflake.connector

sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.config import load_settings  # noqa: E402


def main() -> int:
    settings = load_settings()
    conn = snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        password=settings.snowflake_password,
        warehouse=settings.snowflake_warehouse,
        database=settings.snowflake_database,
        schema=settings.snowflake_schema,
        role=settings.snowflake_role,
    )

    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS SURGICAL_PROTOCOLS (
              step_name STRING,
              protocol_text STRING
            )
            """
        )

        rows = [
            (
                "Identify zone",
                "Identify marked incision zone before tool engagement. Confirm stable view and clear margins.",
            ),
            (
                "Select scalpel",
                "Scalpel is required for step 2. Reject non-scalpel instrument near incision zone.",
            ),
            (
                "Incision and clamp prep",
                "Perform shallow controlled incision and prepare clamp for stabilization after incision.",
            ),
            (
                "Closure",
                "Confirm closure readiness, maintain alignment, and verify no active warning state.",
            ),
        ]

        cur.execute("DELETE FROM SURGICAL_PROTOCOLS")
        cur.executemany(
            "INSERT INTO SURGICAL_PROTOCOLS(step_name, protocol_text) VALUES(%s, %s)",
            rows,
        )
        conn.commit()
        print(f"Seeded SURGICAL_PROTOCOLS with {len(rows)} rows.")
    finally:
        cur.close()
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
