import time
from threading import Thread
from typing import Dict

try:
    # Supports running as "python -m backend.app.main" from repo root.
    from backend.app.api.server import create_app, create_socketio, register_routes
    from backend.app.audio.tts import GuidanceSpeaker
    from backend.app.config import load_settings
    from backend.app.contracts.events import make_event
    from backend.app.llm.groq_client import GroqGuidanceClient
    from backend.app.logic.step_tracker import StepTracker
    from backend.app.rag.snowflake_client import SnowflakeRAGClient
    from backend.app.state import SharedState
    from backend.app.storage.mongo_logger import MongoEventLogger
    from backend.app.vision.camera import open_camera, read_encoded_frame
    from backend.app.vision.color_detection import detect_demo_colors
    from backend.app.vision.gemini_client import GeminiVisionClient
except ModuleNotFoundError:
    # Supports running as "python -m app.main" from backend/ directory.
    from app.api.server import create_app, create_socketio, register_routes
    from app.audio.tts import GuidanceSpeaker
    from app.config import load_settings
    from app.contracts.events import make_event
    from app.llm.groq_client import GroqGuidanceClient
    from app.logic.step_tracker import StepTracker
    from app.rag.snowflake_client import SnowflakeRAGClient
    from app.state import SharedState
    from app.storage.mongo_logger import MongoEventLogger
    from app.vision.camera import open_camera, read_encoded_frame
    from app.vision.color_detection import detect_demo_colors
    from app.vision.gemini_client import GeminiVisionClient


class LoopAService:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.state = SharedState()
        self.tracker = StepTracker()
        self.cap = open_camera(self.settings.brio_camera_index)
        self.mongo_logger = MongoEventLogger(self.settings)
        self.gemini_client = GeminiVisionClient(self.settings)
        self.snowflake_client = SnowflakeRAGClient(self.settings)
        self.groq_client = GroqGuidanceClient(self.settings)
        self.speaker = GuidanceSpeaker(self.settings)
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
        self.deps["mongo"] = self.mongo_logger.ping()
        self.deps["gemini"] = self.gemini_client.ping()
        self.deps["snowflake"] = self.snowflake_client.ping()
        self.deps["groq"] = self.groq_client.ping()
        self.deps["elevenlabs"] = self.speaker.ping()

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
            gemini_data = self.gemini_client.analyze_scene(frame_bytes, scene)
            step_number, step_name, warning = self.tracker.advance(scene)
            combined_warning = warning or str(gemini_data.get("warning", "")).strip()

            rag = self.snowflake_client.fetch_context(str(scene), step_name)
            guidance = self.groq_client.generate_guidance(str(scene), rag["context"], step_name)
            if combined_warning:
                guidance = combined_warning
            self.speaker.speak(guidance)

            self.state.update(
                current_step=step_number,
                current_step_name=step_name,
                current_warning=combined_warning or None,
                last_guidance=guidance,
                last_scene_summary=str({"hsv_scene": scene, "gemini": gemini_data}),
                last_frame_jpeg=frame_bytes,
                loop_a_alive=True,
            )
            self.emit_step_event(step_number, step_name, combined_warning)
            self.mongo_logger.log_event(
                "loop_a_step",
                {
                    "step_number": step_number,
                    "step_name": step_name,
                    "warning": combined_warning,
                    "scene": scene,
                    "gemini": gemini_data,
                    "rag_source": rag.get("source"),
                    "guidance": guidance,
                },
            )

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
        # Hackathon/local environment uses Werkzeug intentionally.
        self.socketio.run(
            self.app,
            host="0.0.0.0",
            port=self.settings.port,
            allow_unsafe_werkzeug=True,
        )


if __name__ == "__main__":
    service = LoopAService()
    service.run()
