"""
Loop A + Loop B orchestration: camera, VLM, guidance, Socket.IO, optional voice Q&A.

Canonical Loop B modules: `backend.app.loop_b`.
"""

from __future__ import annotations

import logging
import time
from threading import Thread
from typing import Any, Dict, Optional

import cv2

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
    from backend.app.llm.groq_client import GroqGuidanceClient
    from backend.app.logic.step_tracker import StepTracker
    from backend.app.rag.snowflake_client import SnowflakeRAGClient
    from backend.app.state import SharedState
    from backend.app.storage.mongo_logger import MongoEventLogger
    from backend.app.vision.camera import open_camera
    from backend.app.vision.color_detection import detect_demo_colors
    from backend.app.vision.frame_encoding import LatestFrameBuffer, encode_jpeg, sleep_until_next_frame
    from backend.app.vision.smart_crop import SmartCropper
    from backend.app.vision.gemini_client import (
        SURGEAI_GEMINI_BACKOFF_KEY,
        SURGEAI_SKIP_LLM_RAG_KEY,
        GeminiVisionClient,
        strip_internal_gemini_keys,
    )
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
    from app.llm.groq_client import GroqGuidanceClient
    from app.logic.step_tracker import StepTracker
    from app.rag.snowflake_client import SnowflakeRAGClient
    from app.state import SharedState
    from app.storage.mongo_logger import MongoEventLogger
    from app.vision.camera import open_camera
    from app.vision.color_detection import detect_demo_colors
    from app.vision.frame_encoding import LatestFrameBuffer, encode_jpeg, sleep_until_next_frame
    from app.vision.smart_crop import SmartCropper
    from app.vision.gemini_client import (
        SURGEAI_GEMINI_BACKOFF_KEY,
        SURGEAI_SKIP_LLM_RAG_KEY,
        GeminiVisionClient,
        strip_internal_gemini_keys,
    )

_LOOP_B_MODULES_OK = False
try:
    from backend.app.loop_b.audio_pipeline import _build_recognizer_and_mic, _capture_question, _listen_for_wake_word
    from backend.app.loop_b.intelligence_pipeline import generate_answer, retrieve_context
    from backend.app.loop_b.tts_pipeline import speak as loop_b_speak

    _LOOP_B_MODULES_OK = True
except ModuleNotFoundError as exc:
    # Only fall back to `app.loop_b` when the *top-level* package is `backend`
    # (e.g. `python -m app.main` from `backend/`). Do not retry on missing optional
    # deps like `speech_recognition` — that would incorrectly import `app` from repo root.
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
        self.gemini_client = GeminiVisionClient(self.settings)
        self.snowflake_client = SnowflakeRAGClient(self.settings)
        self.groq_client = GroqGuidanceClient(self.settings)
        self.speaker = GuidanceSpeaker(self.settings)
        self.running = True
        self._last_guidance_spoken = 0.0
        self._last_vlm_ts = 0.0
        self._gemini_backoff_until = 0.0
        self._last_gemini_boxes: list = []
        self.cropper = SmartCropper(jpeg_quality=self.settings.vlm_jpeg_quality)
        self.deps: Dict[str, bool] = {
            "camera": True,
            "gemini": True,
            "snowflake": True,
            "groq": True,
            "elevenlabs": True,
            "mongo": True,
            "loop_b": _LOOP_B_MODULES_OK and self.settings.loop_b_enabled,
        }

        self.app = create_app(self.settings.frontend_origin)
        self.socketio = create_socketio(self.app)
        register_socketio_namespace_handlers(self.socketio, self.settings.socket_namespace)
        register_routes(self.app, self.state.snapshot, self.mjpeg_stream, self.deps_snapshot)
        self.deps["mongo"] = self.mongo_logger.ping()
        self.deps["gemini"] = self.gemini_client.ping()
        self.deps["snowflake"] = self.snowflake_client.ping()
        self.deps["groq"] = self.groq_client.ping()
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
            # Draw the SmartCropper zoom box on a copy of the frame for the MJPEG stream.
            # The VLM buffer gets the clean frame; the viewer sees the annotated one.
            overlay = self.cropper.get_overlay()
            if overlay is not None:
                (x1, y1, x2, y2), label = overlay
                display = frame.copy()
                cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 100), 2)
                if label:
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    (tw, th), baseline = cv2.getTextSize(label, font, 0.65, 2)
                    cv2.rectangle(display, (x1, y1 - th - baseline - 6), (x1 + tw + 8, y1), (0, 255, 100), -1)
                    cv2.putText(display, label, (x1 + 4, y1 - baseline - 2), font, 0.65, (0, 0, 0), 2, cv2.LINE_AA)
            else:
                display = frame
            enc_ok, jpeg = encode_jpeg(display, self.settings.vlm_jpeg_quality)
            if enc_ok:
                self.frame_buffer.put(jpeg, frame)  # VLM gets the clean frame
                self.state.update(last_frame_jpeg=jpeg, loop_a_alive=True)
                dt = max(1e-6, time.time() - t0)
                inst_fps = 1.0 / dt
                fps_ema = inst_fps if fps_ema is None else (0.85 * fps_ema + 0.15 * inst_fps)
                self.state.update(metrics_fps=float(fps_ema or 0.0))
            sleep_until_next_frame(t0, self.settings.capture_target_fps)

    def run_vlm_loop(self) -> None:
        """Throttled Gemini + step tracker + RAG + Groq + TTS (Loop A)."""
        min_ivl = self._vlm_min_interval_seconds()
        while self.running:
            pair = self.frame_buffer.get()
            if not pair:
                time.sleep(0.02)
                continue
            frame_bytes, frame = pair
            now = time.time()
            if now < self._gemini_backoff_until:
                time.sleep(min(0.05, max(0.0, self._gemini_backoff_until - now)))
                continue
            if now - self._last_vlm_ts < min_ivl:
                time.sleep(0.02)
                continue
            self._last_vlm_ts = now
            t_infer = time.time()

            scene = detect_demo_colors(frame)
            # Dynamic-zoom smart crop: use previous frame's boxes to tightly
            # frame the subject, then upscale to 512x512 for the VLM.
            try:
                vlm_frame_bytes = self.cropper.detect_and_crop(frame, self._last_gemini_boxes)
            except Exception as _crop_err:
                logger.warning("Smart crop failed (%s) — sending full frame", _crop_err)
                vlm_frame_bytes = frame_bytes
            gemini_data = self.gemini_client.analyze_scene(vlm_frame_bytes, scene)

            backoff_sec = gemini_data.pop(SURGEAI_GEMINI_BACKOFF_KEY, None)
            skip_llm_rag = bool(gemini_data.pop(SURGEAI_SKIP_LLM_RAG_KEY, False))
            if backoff_sec is not None:
                self._gemini_backoff_until = time.time() + float(backoff_sec)

            # Build detection list from Gemini ar_boxes for the step tracker.
            # Gemini uses tool names like "scalpel"; map to COCO labels the
            # tracker's state machine expects ("knife", "scissors", "banana").
            _GEMINI_TO_COCO = {
                "scalpel": "knife", "knife": "knife",
                "clamp": "scissors", "scissors": "scissors", "forceps": "scissors",
                "banana": "banana", "patient": "banana", "tissue": "banana",
            }
            gemini_boxes = gemini_data.get("ar_boxes", [])
            # Cache boxes for the next frame's smart crop
            if isinstance(gemini_boxes, list) and gemini_boxes:
                self._last_gemini_boxes = gemini_boxes
            objects = []
            for b in gemini_boxes if isinstance(gemini_boxes, list) else []:
                raw = str(b.get("label", "")).lower() if isinstance(b, dict) else ""
                coco = _GEMINI_TO_COCO.get(raw, raw)
                conf = float(b.get("confidence", gemini_data.get("confidence", 0.7)) if isinstance(b, dict) else 0.0)
                if coco:
                    objects.append({"label": coco, "confidence": conf})
            step_number, step_name, warning = self.tracker.advance(objects)
            combined_warning = warning or str(gemini_data.get("warning", "")).strip()

            if skip_llm_rag:
                rag = {"context": "", "source": None}
                guidance = (
                    combined_warning
                    or str(gemini_data.get("instruction") or "").strip()
                    or "Guidance paused — Gemini rate limited or unavailable."
                )
            else:
                rag = self.snowflake_client.fetch_context(str(scene), step_name)
                guidance = self.groq_client.generate_guidance(str(scene), rag["context"], step_name)
                if combined_warning:
                    guidance = combined_warning

            if not skip_llm_rag and (
                now - self._last_guidance_spoken >= self.settings.guidance_min_interval_seconds
            ):
                self.speaker.speak(guidance)
                self._last_guidance_spoken = now

            latency_ms = int(max(0.0, (time.time() - t_infer) * 1000))
            gemini_for_log = strip_internal_gemini_keys(gemini_data)
            self.state.update(
                current_step=step_number,
                current_step_name=step_name,
                current_warning=combined_warning or None,
                last_guidance=guidance,
                last_scene_summary=str({"hsv_scene": scene, "gemini": gemini_for_log}),
                loop_a_alive=True,
                metrics_latency_ms=latency_ms,
            )
            self.emit_step_event(step_number, step_name, combined_warning)
            self.emit_vlm_overlay(gemini_data.get("ar_boxes") or [])

            self.mongo_logger.log_event(
                "loop_a_step",
                {
                    "step_number": step_number,
                    "step_name": step_name,
                    "warning": combined_warning,
                    "scene": scene,
                    "gemini": gemini_for_log,
                    "rag_source": rag.get("source"),
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
                    "degraded": not self.deps.get("gemini", True),
                },
            )
            self.socketio.emit("system_health", health_event, namespace=self.settings.socket_namespace)

    def _on_loop_b_question(self, question_text: str) -> None:
        """RAG → Groq → Socket `qa_update` → ElevenLabs TTS → Mongo (Loop B)."""
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
        while self.running:
            try:
                recognizer, mic = _build_recognizer_and_mic()
                break
            except Exception as exc:
                logger.error("[Loop B] Mic init failed (%s) — retry in 5s", exc)
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
