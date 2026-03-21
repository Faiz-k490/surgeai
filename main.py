"""
Compatibility entry: FastAPI + WebSocket Loop B experiment.

Production unified backend (Flask + Socket.IO + VLM + Loop B):
  python -m backend.app.main

Run this file from the repo root:
  python main.py
"""

try:
    from backend.app.api.fastapi_app import app
except ModuleNotFoundError:
    from app.api.fastapi_app import app

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.api.fastapi_app:app", host="0.0.0.0", port=5000, reload=True)
