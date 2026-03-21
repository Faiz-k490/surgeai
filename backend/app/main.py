import time
from threading import Thread
from typing import Dict

from app.api.server import create_app, create_socketio, register_routes
from app.config import load_settings
from app.contracts.events import make_event
from app.logic.step_tracker import StepTracker
from app.state import SharedState
from app.vision.camera import open_camera, read_encoded_frame
from app.vision.color_detection import detect_demo_colors


class LoopAService:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.state = SharedState()
        self.tracker = StepTracker()
        self.cap = open_camera(self.settings.brio_camera_index)
        self.running = True
        self.deps: Dict[str, bool] = {
            "camera": True,
            "gemini": True,
            "snowflake": True,
            "groq": True,
            "elevenlabs": True,
            "mongo": True,
        }

        self.app = create_app(self.settings.frontend_origin)
        self.socketio = create_socketio(self.app)
        register_routes(self.app, self.state.snapshot, self.mjpeg_stream, self.deps_snapshot)

    def deps_snapshot(self) -> Dict[str, bool]:
        return dict(self.deps)

    def mjpeg_stream(self):
        while self.running:
            frame_bytes = self.state.last_frame_jpeg
            if frame_bytes:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
            time.sleep(0.03)

    def emit_step_event(self, step_number: int, step_name: str, warning: str) -> None:
        step_event = make_event(
            event_version=self.settings.event_schema_version,
            event_type="step_update",
            payload={"stepNumber": step_number, "stepName": step_name, "confidence": 0.8},
        )
        self.socketio.emit("step_update", step_event, namespace=self.settings.socket_namespace)

        if warning:
            warn_event = make_event(
                event_version=self.settings.event_schema_version,
                event_type="warning",
                payload={"severity": "critical", "message": warning, "currentStep": step_number},
            )
            self.socketio.emit("warning", warn_event, namespace=self.settings.socket_namespace)
        else:
            clear_event = make_event(
                event_version=self.settings.event_schema_version,
                event_type="clear",
                payload={"status": "nominal"},
            )
            self.socketio.emit("clear", clear_event, namespace=self.settings.socket_namespace)

    def run_loop_a(self) -> None:
        while self.running:
            ok, frame_bytes, frame = read_encoded_frame(self.cap)
            if not ok:
                self.deps["camera"] = False
                time.sleep(0.2)
                continue

            scene = detect_demo_colors(frame)
            step_number, step_name, warning = self.tracker.advance(scene)

            # TODO: Replace with real Gemini -> Snowflake -> Groq -> ElevenLabs pipeline.
            guidance = f"Step {step_number}: {step_name}"
            if warning:
                guidance = warning

            self.state.update(
                current_step=step_number,
                current_step_name=step_name,
                current_warning=warning or None,
                last_guidance=guidance,
                last_scene_summary=str(scene),
                last_frame_jpeg=frame_bytes,
                loop_a_alive=True,
            )
            self.emit_step_event(step_number, step_name, warning)

            health_event = make_event(
                event_version=self.settings.event_schema_version,
                event_type="system_health",
                payload={"loopAAlive": True, "fps": 1, "apiLatencyMs": 0, "degraded": False},
            )
            self.socketio.emit("system_health", health_event, namespace=self.settings.socket_namespace)

            time.sleep(self.settings.loop_a_interval_seconds)

    def run(self) -> None:
        loop_thread = Thread(target=self.run_loop_a, daemon=True)
        loop_thread.start()
        self.socketio.run(self.app, host="0.0.0.0", port=self.settings.port)


if __name__ == "__main__":
    service = LoopAService()
    service.run()
