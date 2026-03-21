"""
Snowflake environment probe for backend/.env values.

Usage (PowerShell):
  $env:SF_ACCOUNT="your_account_identifier"
  $env:SF_USER="your_username"
  $env:SF_PASSWORD="your_password"
  .\.venv311\Scripts\python backend\scripts\snowflake_env_probe.py

This script prints values for:
  SNOWFLAKE_ACCOUNT
  SNOWFLAKE_USER
  SNOWFLAKE_WAREHOUSE
  SNOWFLAKE_DATABASE
  SNOWFLAKE_SCHEMA
  SNOWFLAKE_ROLE

It never reads or prints an existing backend/.env password value.
"""

import os
import sys

import snowflake.connector


def _need(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> int:
    account = _need("SF_ACCOUNT")
    user = _need("SF_USER")
    password = _need("SF_PASSWORD")

    conn = snowflake.connector.connect(
        account=account,
        user=user,
        password=password,
    )

    try:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                  CURRENT_ACCOUNT(),
                  CURRENT_USER(),
                  CURRENT_ROLE(),
                  CURRENT_WAREHOUSE(),
                  CURRENT_DATABASE(),
                  CURRENT_SCHEMA()
                """
            )
            current_account, current_user, current_role, current_wh, current_db, current_schema = cursor.fetchone()
        finally:
            cursor.close()
    finally:
        conn.close()

    print("Paste into backend/.env:")
    print(f"SNOWFLAKE_ACCOUNT={account or current_account}")
    print(f"SNOWFLAKE_USER={current_user}")
    print("SNOWFLAKE_PASSWORD=replace_me")
    print(f"SNOWFLAKE_WAREHOUSE={current_wh or 'replace_me'}")
    print(f"SNOWFLAKE_DATABASE={current_db or 'replace_me'}")
    print(f"SNOWFLAKE_SCHEMA={current_schema or 'replace_me'}")
    print(f"SNOWFLAKE_ROLE={current_role or 'replace_me'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - utility error path
        print(f"Snowflake probe failed: {exc}")
        print("Tip: verify SF_ACCOUNT / SF_USER / SF_PASSWORD and network connectivity.")
        raise SystemExit(1)
