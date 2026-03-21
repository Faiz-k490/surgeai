"""Backward compatibility: use `flask_factory` in new code."""

from backend.app.api.flask_factory import create_app, create_socketio, register_routes

__all__ = ["create_app", "create_socketio", "register_routes"]
