"""
Central logging: colored terminal (green INFO, red ERROR) + rotating file under logging/logs/.
Call setup_logging() once at process entry (see backend.app.main).
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

_LOGGED_SETUP = False


def _repo_root() -> Path:
    # backend/app/core/runtime_logging.py -> parents[3] == repo root
    return Path(__file__).resolve().parents[3]


def _backend_env_path() -> Path:
    # backend/app/core -> parents[2] == backend/
    return Path(__file__).resolve().parents[2] / ".env"


def _default_log_dir() -> Path:
    override = os.getenv("SURGEAI_LOG_DIR", "").strip()
    if override:
        return Path(override)
    return _repo_root() / "logging" / "logs"


def setup_logging(
    *,
    level: str | None = None,
    log_dir: Path | None = None,
    force: bool = True,
) -> Path:
    """Configure root logging: console (color) + rotating file. Returns log directory used."""
    global _LOGGED_SETUP
    if _LOGGED_SETUP and not force:
        return _default_log_dir()

    load_dotenv(_backend_env_path())
    load_dotenv()

    lvl_name = (level or os.getenv("LOG_LEVEL", "INFO")).upper().strip()
    level_no = getattr(logging, lvl_name, logging.INFO)

    log_path = log_dir or _default_log_dir()
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "surgeai-backend.log"

    root = logging.getLogger()
    if force:
        for h in root.handlers[:]:
            root.removeHandler(h)
            h.close()

    root.setLevel(level_no)

    try:
        import colorlog
    except ImportError:
        colorlog = None  # type: ignore[assignment]

    if colorlog is not None:
        console = colorlog.StreamHandler(sys.stdout)
        console.setFormatter(
            colorlog.ColoredFormatter(
                "%(log_color)s%(levelname)-8s%(reset)s %(name)s %(message)s",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red,bg_white",
                },
            )
        )
    else:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(
            logging.Formatter("%(levelname)-8s %(name)s %(message)s")
        )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s %(message)s")
    )

    root.addHandler(console)
    root.addHandler(file_handler)

    # Quieter third-party noise unless DEBUG
    logging.getLogger("werkzeug").setLevel(logging.WARNING if level_no > logging.DEBUG else logging.DEBUG)
    logging.getLogger("engineio.server").setLevel(logging.WARNING)
    logging.getLogger("socketio.server").setLevel(logging.WARNING)

    logging.getLogger("surgeai.backend").info(
        "Logging initialized — level=%s file=%s",
        lvl_name,
        log_file,
    )
    _LOGGED_SETUP = True
    return log_path
