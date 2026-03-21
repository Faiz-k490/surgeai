from typing import Callable

from flask import Flask, Response, jsonify
from flask_socketio import SocketIO

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
    return SocketIO(app, cors_allowed_origins=[app.config["FRONTEND_ORIGIN"]])


def register_routes(app: Flask, state_snapshot: Callable, mjpeg_stream: Callable, deps_snapshot: Callable) -> None:
    @app.get("/health")
    def health():
        deps = deps_snapshot()
        return jsonify(health_payload(ok=all(deps.values()), deps=deps))

    @app.get("/session/state")
    def session_state():
        return jsonify(session_state_payload(state_snapshot()))

    @app.get("/video")
    def video():
        # MJPEG lets frontend render live frames without WebRTC complexity.
        return Response(mjpeg_stream(), mimetype="multipart/x-mixed-replace; boundary=frame")
