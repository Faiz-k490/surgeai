from typing import Dict

import snowflake.connector


class SnowflakeRAGClient:
    def __init__(self, settings):
        self.settings = settings
        self.conn = snowflake.connector.connect(
            account=settings.snowflake_account,
            user=settings.snowflake_user,
            password=settings.snowflake_password,
            warehouse=settings.snowflake_warehouse,
            database=settings.snowflake_database,
            schema=settings.snowflake_schema,
            role=settings.snowflake_role,
        )

    def ping(self) -> bool:
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            return True
        except Exception:
            return False

    def fetch_context(self, scene_summary: str, step_name: str) -> Dict[str, str]:
        # Prefer DB-backed context if a protocols table exists; otherwise use safe fallback text.
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT protocol_text
                FROM SURGICAL_PROTOCOLS
                WHERE step_name = %s
                LIMIT 1
                """,
                (step_name,),
            )
            row = cur.fetchone()
            cur.close()
            if row:
                return {"source": "snowflake_table", "context": str(row[0])}
        except Exception:
            pass

        fallback = {
            "Identify zone": "Confirm incision zone before instrument selection.",
            "Select scalpel": "Use scalpel for shallow incision, maintain controlled depth.",
            "Incision and clamp prep": "Prepare clamp after incision and monitor bleeding risk.",
            "Closure": "Confirm closure technique and tissue alignment.",
        }
        return {
            "source": "fallback",
            "context": fallback.get(step_name, f"Protocol context for {step_name}. Scene: {scene_summary}"),
        }
