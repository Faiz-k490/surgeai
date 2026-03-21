"""
CLI entrypoint for the unified SurgeAI backend (Loop A + Loop B).

Run from repository root:
  python -m backend.app.main
"""

from __future__ import annotations

try:
    from backend.app.core.runtime_logging import setup_logging
    from backend.app.services.loop_a_service import LoopAService
except ModuleNotFoundError:
    from app.core.runtime_logging import setup_logging
    from app.services.loop_a_service import LoopAService


def main() -> None:
    setup_logging()
    LoopAService().run()


if __name__ == "__main__":
    main()
