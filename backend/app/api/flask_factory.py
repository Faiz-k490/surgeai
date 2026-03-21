"""Flask application factory and Socket.IO wiring (HTTP + MJPEG routes)."""

import logging
from typing import Callable

from flask import Flask, Response, jsonify
from flask_socketio import SocketIO

logger = logging.getLogger("surgeai.backend")

try:
    from backend.app.contracts.http import health_payload, session_state_payload
except ModuleNotFoundError:
    from app.contracts.http import health_payload, session_state_payload


def create_app(frontend_origin: str) -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.config["FRONTEND_ORIGIN"] = frontend_origin
    return app


def create_socketio(app: Flask) -> SocketIO:
    return SocketIO(app, cors_allowed_origins="*")


def register_socketio_namespace_handlers(socketio: SocketIO, namespace: str) -> None:
    """Accept clients on the HUD namespace (e.g. `/realtime`).

    Without at least a `connect` handler, some Flask-SocketIO / python-socketio
    setups reject namespace connections; polling then returns 400 on follow-up
    requests with `sid=...`.
    """

    @socketio.on("connect", namespace=namespace)
    def _on_connect():  # noqa: ANN001
        logger.info("Socket.IO client connected (namespace=%s)", namespace)

    @socketio.on("disconnect", namespace=namespace)
    def _on_disconnect():  # noqa: ANN001
        logger.info("Socket.IO client disconnected (namespace=%s)", namespace)


def register_routes(
    app: Flask,
    state_snapshot: Callable,
    mjpeg_stream: Callable,
    deps_snapshot: Callable,
) -> None:
    @app.get("/health")
    def health():
        deps = deps_snapshot()
        return jsonify(health_payload(ok=all(deps.values()), deps=deps))

    @app.get("/session/state")
    def session_state():
        return jsonify(session_state_payload(state_snapshot()))

    @app.get("/video")
    def video():
        return Response(mjpeg_stream(), mimetype="multipart/x-mixed-replace; boundary=frame")
