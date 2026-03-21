"""
Loop A + Loop B orchestration: camera, YOLO detection, state machine, Cortex
guidance, Socket.IO, optional voice Q&A.

Canonical Loop B modules: `backend.app.loop_b`.
"""

from __future__ import annotations

import logging
import time
from threading import Thread
from typing import Any, Dict, Optional

logger = logging.getLogger("surgeai.backend")

try:
    from backend.app.api.flask_factory import (
        create_app,
        create_socketio,
        register_routes,
        register_socketio_namespace_handlers,
    )
    from backend.app.audio.tts import GuidanceSpeaker
    from backend.app.config import load_settings
    from backend.app.contracts.events import make_event
    from backend.app.llm.cortex_client import CortexGuidanceClient
    from backend.app.logic.step_tracker import StepTracker
    from backend.app.state import SharedState
    from backend.app.storage.mongo_logger import MongoEventLogger
    from backend.app.vision.camera import open_camera
    from backend.app.vision.frame_encoding import LatestFrameBuffer, encode_jpeg, sleep_until_next_frame
    from backend.app.vision.yolo_detector import YoloDetector
except ModuleNotFoundError:
    from app.api.flask_factory import (
        create_app,
        create_socketio,
        register_routes,
        register_socketio_namespace_handlers,
    )
    from app.audio.tts import GuidanceSpeaker
    from app.config import load_settings
    from app.contracts.events import make_event
    from app.llm.cortex_client import CortexGuidanceClient
    from app.logic.step_tracker import StepTracker
    from app.state import SharedState
    from app.storage.mongo_logger import MongoEventLogger
    from app.vision.camera import open_camera
    from app.vision.frame_encoding import LatestFrameBuffer, encode_jpeg, sleep_until_next_frame
    from app.vision.yolo_detector import YoloDetector

_LOOP_B_MODULES_OK = False
try:
    from backend.app.loop_b.audio_pipeline import _build_recognizer_and_mic, _capture_question, _listen_for_wake_word
    from backend.app.loop_b.intelligence_pipeline import generate_answer, retrieve_context
    from backend.app.loop_b.tts_pipeline import speak as loop_b_speak

    _LOOP_B_MODULES_OK = True
except ModuleNotFoundError as exc:
    if getattr(exc, "name", None) == "backend":
        try:
            from app.loop_b.audio_pipeline import _build_recognizer_and_mic, _capture_question, _listen_for_wake_word
            from app.loop_b.intelligence_pipeline import generate_answer, retrieve_context
            from app.loop_b.tts_pipeline import speak as loop_b_speak

            _LOOP_B_MODULES_OK = True
        except ImportError as exc2:
            logger.warning("Loop B modules not importable (%s). Voice Q&A disabled.", exc2)
    else:
        logger.warning("Loop B modules not importable (%s). Voice Q&A disabled.", exc)
except ImportError as exc:
    logger.warning("Loop B modules not importable (%s). Voice Q&A disabled.", exc)


class LoopAService:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.state = SharedState()
        self.tracker = StepTracker()
        self.cap = open_camera(self.settings.brio_camera_index, self.settings.camera_backend)
        self.frame_buffer = LatestFrameBuffer()
        self.mongo_logger = MongoEventLogger(self.settings)
        self.yolo = YoloDetector(
            model_path=self.settings.yolo_model,
            confidence=self.settings.yolo_confidence_threshold,
        )
        self.cortex_client = CortexGuidanceClient(self.settings)
        self.speaker = GuidanceSpeaker(self.settings)
        self.running = True
        self._last_guidance_spoken = 0.0
        self._last_vlm_ts = 0.0
        self._prev_step_number = 0
        self.deps: Dict[str, bool] = {
            "camera": True,
            "yolo": True,
            "cortex": True,
            "elevenlabs": True,
            "mongo": True,
            "loop_b": _LOOP_B_MODULES_OK and self.settings.loop_b_enabled,
        }

        self.app = create_app(self.settings.frontend_origin)
        self.socketio = create_socketio(self.app)
        register_socketio_namespace_handlers(self.socketio, self.settings.socket_namespace)
        register_routes(self.app, self.state.snapshot, self.mjpeg_stream, self.deps_snapshot)
        self.deps["mongo"] = self.mongo_logger.ping()
        self.deps["yolo"] = self.yolo.ping()
        self.deps["cortex"] = self.cortex_client.ping()
        self.deps["elevenlabs"] = self.speaker.ping()
        if not _LOOP_B_MODULES_OK:
            self.deps["loop_b"] = False

    def deps_snapshot(self) -> Dict[str, bool]:
        return dict(self.deps)

    def mjpeg_stream(self):
        while self.running:
            frame_bytes = self.state.last_frame_jpeg
            if frame_bytes:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                )
            time.sleep(0.03)

    def _vlm_min_interval_seconds(self) -> float:
        hz = max(0.01, float(self.settings.vlm_max_hz))
        from_hz = 1.0 / hz
        legacy = float(self.settings.loop_a_interval_seconds)
        if legacy > 0:
            return max(from_hz, legacy)
        return from_hz

    def emit_step_event(self, step_number: int, step_name: str, warning: str) -> None:
        step_event = make_event(
            event_version=self.settings.event_schema_version,
            event_type="step_update",
            payload={
                "stepNumber": step_number,
                "stepName": step_name,
                "confidence": 0.8,
            },
        )
        self.socketio.emit("step_update", step_event, namespace=self.settings.socket_namespace)

        if warning:
            warn_event = make_event(
                event_version=self.settings.event_schema_version,
                event_type="warning",
                payload={
                    "severity": "critical",
                    "message": warning,
                    "currentStep": step_number,
                },
            )
            self.socketio.emit("warning", warn_event, namespace=self.settings.socket_namespace)
        else:
            clear_event = make_event(
                event_version=self.settings.event_schema_version,
                event_type="clear",
                payload={"status": "nominal"},
            )
            self.socketio.emit("clear", clear_event, namespace=self.settings.socket_namespace)

    def emit_vlm_overlay(self, boxes: Any) -> None:
        if not isinstance(boxes, list):
            boxes = []
        evt = make_event(
            event_version=self.settings.event_schema_version,
            event_type="vlm_update",
            payload={"boxes": boxes},
        )
        self.socketio.emit("vlm_update", evt, namespace=self.settings.socket_namespace)

    def run_capture(self) -> None:
        """High-FPS grab + JPEG encode; updates SharedState for MJPEG and VLM buffer."""
        fps_ema: Optional[float] = None
        while self.running:
            t0 = time.time()
            ok, frame = self.cap.read()
            if not ok:
                self.deps["camera"] = False
                time.sleep(0.05)
                continue
            self.deps["camera"] = True
            enc_ok, jpeg = encode_jpeg(frame, self.settings.vlm_jpeg_quality)
            if enc_ok:
                self.frame_buffer.put(jpeg, frame)
                self.state.update(last_frame_jpeg=jpeg, loop_a_alive=True)
                dt = max(1e-6, time.time() - t0)
                inst_fps = 1.0 / dt
                fps_ema = inst_fps if fps_ema is None else (0.85 * fps_ema + 0.15 * inst_fps)
                self.state.update(metrics_fps=float(fps_ema or 0.0))
            sleep_until_next_frame(t0, self.settings.capture_target_fps)

    def run_vlm_loop(self) -> None:
        """YOLO detection + step tracker + Cortex guidance + TTS (Loop A)."""
        min_ivl = self._vlm_min_interval_seconds()
        while self.running:
            pair = self.frame_buffer.get()
            if not pair:
                time.sleep(0.02)
                continue
            frame_bytes, frame = pair
            now = time.time()
            if now - self._last_vlm_ts < min_ivl:
                time.sleep(0.02)
                continue
            self._last_vlm_ts = now
            t_infer = time.time()

            # --- YOLO local detection (fast, no API) ---
            yolo_result = self.yolo.detect(frame)
            objects = yolo_result.get("objects", [])
            ar_boxes = yolo_result.get("ar_boxes", [])

            # --- State machine evaluation ---
            step_number, step_name, warning = self.tracker.advance(objects)
            step_changed = step_number != self._prev_step_number
            self._prev_step_number = step_number

            # --- Cortex guidance (only on state changes or warnings) ---
            guidance = ""
            event_type = ""
            if step_changed:
                event_type = "step_update"
            elif warning:
                event_type = "warning"

            if event_type:
                detected_tool = objects[0]["display_label"] if objects else "none"
                try:
                    guidance = self.cortex_client.generate_guidance(step_name, detected_tool, event_type)
                except Exception as exc:
                    logger.error("Cortex guidance failed: %s", exc)
                    from backend.app.logic.step_tracker import FALLBACK_GUIDANCE  # noqa: F811
                    guidance = FALLBACK_GUIDANCE.get(step_number, f"Continue with {step_name}.")
            elif warning:
                guidance = warning

            # --- TTS (only on new events, deduplicated in GuidanceSpeaker) ---
            if guidance and (
                now - self._last_guidance_spoken >= self.settings.guidance_min_interval_seconds
            ):
                self.speaker.speak(guidance)
                self._last_guidance_spoken = now

            latency_ms = int(max(0.0, (time.time() - t_infer) * 1000))
            labels_summary = ", ".join(f"{o['display_label']}({o['confidence']})" for o in objects) or "none"
            self.state.update(
                current_step=step_number,
                current_step_name=step_name,
                current_warning=warning or None,
                last_guidance=guidance or self.state.last_guidance,
                last_scene_summary=f"YOLO: [{labels_summary}]",
                loop_a_alive=True,
                metrics_latency_ms=latency_ms,
            )
            self.emit_step_event(step_number, step_name, warning)
            self.emit_vlm_overlay(ar_boxes)

            if event_type:
                self.mongo_logger.log_event(
                    "loop_a_step",
                    {
                        "step_number": step_number,
                        "step_name": step_name,
                        "warning": warning,
                        "objects": objects,
                        "guidance": guidance,
                    },
                )

            health_event = make_event(
                event_version=self.settings.event_schema_version,
                event_type="system_health",
                payload={
                    "loopAAlive": True,
                    "fps": round(self.state.metrics_fps, 1),
                    "latency": latency_ms,
                    "apiLatencyMs": latency_ms,
                    "degraded": not self.deps.get("cortex", True),
                },
            )
            self.socketio.emit("system_health", health_event, namespace=self.settings.socket_namespace)

    def _on_loop_b_question(self, question_text: str) -> None:
        """RAG -> Cortex -> Socket `qa_update` -> ElevenLabs TTS -> Mongo (Loop B)."""
        logger.info("[Loop B] Question: %s", question_text)
        try:
            chunks = retrieve_context(question_text)
        except Exception as exc:
            logger.error("[Loop B] RAG error: %s", exc)
            chunks = []

        try:
            answer = generate_answer(question_text, chunks)
        except Exception as exc:
            logger.error("[Loop B] LLM error: %s", exc)
            err_evt = make_event(
                event_version=self.settings.event_schema_version,
                event_type="qa_update",
                payload={"question": question_text, "answer": "", "error": str(exc)},
            )
            self.socketio.emit("qa_update", err_evt, namespace=self.settings.socket_namespace)
            return

        qa_evt = make_event(
            event_version=self.settings.event_schema_version,
            event_type="qa_update",
            payload={"question": question_text, "answer": answer},
        )
        self.socketio.emit("qa_update", qa_evt, namespace=self.settings.socket_namespace)
        self.state.update(last_question=question_text, last_answer=answer)

        try:
            loop_b_speak(answer)
        except Exception as exc:
            logger.error("[Loop B] TTS error: %s", exc)

        try:
            self.mongo_logger.log_event(
                "qa_session",
                {"question": question_text, "answer": answer},
            )
        except Exception as exc:
            logger.error("[Loop B] Mongo log error: %s", exc)

    def run_loop_b_audio(self) -> None:
        if not self.deps.get("loop_b"):
            logger.info("Loop B disabled or modules missing — skipping audio thread.")
            return
        retries = 0
        while self.running:
            try:
                recognizer, mic = _build_recognizer_and_mic()
                break
            except Exception as exc:
                retries += 1
                if retries <= 3:
                    logger.error("[Loop B] Mic init failed (%s) — retry in 5s", exc)
                elif retries == 4:
                    logger.error("[Loop B] Mic init failed after %d attempts. Giving up.", retries)
                    self.deps["loop_b"] = False
                    return
                time.sleep(5)

        logger.info("Loop B listening — say 'Hey Surgeon' then your question.")
        while self.running:
            try:
                if _listen_for_wake_word(recognizer, mic):
                    question = _capture_question(recognizer, mic)
                    if question:
                        Thread(target=self._on_loop_b_question, args=(question,), daemon=True).start()
            except Exception as exc:
                logger.error("[Loop B] Audio loop error: %s", exc)
                time.sleep(1)

    def run(self) -> None:
        logger.info("Loop A starting — port=%s", self.settings.port)
        Thread(target=self.run_capture, daemon=True).start()
        Thread(target=self.run_vlm_loop, daemon=True).start()
        if self.settings.loop_b_enabled and _LOOP_B_MODULES_OK:
            Thread(target=self.run_loop_b_audio, daemon=True).start()

        self.socketio.run(
            self.app,
            host="0.0.0.0",
            port=self.settings.port,
            allow_unsafe_werkzeug=True,
            log_output=False,
        )
