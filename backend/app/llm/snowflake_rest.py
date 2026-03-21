"""
Lightweight Snowflake REST client using the session v1 query API.

Avoids snowflake-connector-python entirely — uses HTTP requests + session
tokens for Python 3.14 compatibility.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("surgeai.snowflake.rest")


class SnowflakeRestClient:
    """Execute SQL via Snowflake's internal REST query API."""

    def __init__(
        self,
        account: str,
        user: str,
        password: str,
        warehouse: str,
        database: str,
        schema: str,
        role: str,
    ) -> None:
        self._account = account
        self._user = user
        self._password = password
        self._warehouse = warehouse
        self._database = database
        self._schema = schema
        self._role = role
        self._base_url = f"https://{account}.snowflakecomputing.com"
        self._session = requests.Session()
        self._token: Optional[str] = None
        self._token_expires: float = 0.0
        self._context_set = False

    @classmethod
    def from_env(cls) -> "SnowflakeRestClient":
        return cls(
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            user=os.environ["SNOWFLAKE_USER"],
            password=os.environ["SNOWFLAKE_PASSWORD"],
            warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
            database=os.environ["SNOWFLAKE_DATABASE"],
            schema=os.environ["SNOWFLAKE_SCHEMA"],
            role=os.environ["SNOWFLAKE_ROLE"],
        )

    @classmethod
    def from_settings(cls, settings) -> "SnowflakeRestClient":
        return cls(
            account=settings.snowflake_account,
            user=settings.snowflake_user,
            password=settings.snowflake_password,
            warehouse=settings.snowflake_warehouse,
            database=settings.snowflake_database,
            schema=settings.snowflake_schema,
            role=settings.snowflake_role,
        )

    def _login(self) -> None:
        """Obtain a session token via username/password login."""
        url = f"{self._base_url}/session/v1/login-request"
        body = {
            "data": {
                "CLIENT_APP_ID": "SurgeAI",
                "CLIENT_APP_VERSION": "1.0",
                "ACCOUNT_NAME": self._account,
                "LOGIN_NAME": self._user,
                "PASSWORD": self._password,
            }
        }
        resp = self._session.post(
            url,
            json=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            msg = data.get("message", "Unknown login error")
            raise RuntimeError(f"Snowflake login failed: {msg}")

        self._token = data["data"]["token"]
        validity = data["data"].get("validityInSeconds", 3600)
        self._token_expires = time.time() + validity - 60
        self._context_set = False
        logger.info("Snowflake session established (valid for %ds).", validity)

    def _ensure_token(self) -> str:
        if self._token is None or time.time() >= self._token_expires:
            self._login()
        assert self._token is not None
        return self._token

    def _set_context(self) -> None:
        """Set warehouse/database/schema/role context for the session."""
        if self._context_set:
            return
        for sql in [
            f"USE ROLE {self._role}",
            f"USE WAREHOUSE {self._warehouse}",
            f"USE DATABASE {self._database}",
            f"USE SCHEMA {self._schema}",
        ]:
            self._raw_query(sql)
        self._context_set = True

    def _raw_query(self, sql: str) -> Dict[str, Any]:
        """Execute a single SQL statement and return the full response dict."""
        token = self._ensure_token()
        req_id = str(uuid.uuid4())
        url = f"{self._base_url}/queries/v1/query-request?requestId={req_id}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f'Snowflake Token="{token}"',
        }
        resp = self._session.post(
            url,
            json={"sqlText": sql},
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    def execute(self, sql: str) -> List[List[Any]]:
        """Execute a SQL statement and return rows."""
        self._set_context()
        result = self._raw_query(sql)

        if not result.get("success"):
            code = result.get("code", "?")
            msg = result.get("message", "Unknown SQL error")
            raise RuntimeError(f"Snowflake SQL error [{code}]: {msg}")

        return result.get("data", {}).get("rowset", [])

    def execute_scalar(self, sql: str) -> Optional[str]:
        """Execute SQL and return the first column of the first row as a string."""
        rows = self.execute(sql)
        if rows and rows[0]:
            return str(rows[0][0])
        return None

    def ping(self) -> bool:
        try:
            result = self.execute_scalar("SELECT 1")
            return result == "1"
        except Exception as exc:
            logger.warning("Snowflake ping failed: %s", exc)
            return False
