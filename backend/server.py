#!/usr/bin/env python3
"""
SurgeAI conversational backend.

This server keeps the raw MJPEG feed untouched while all detection, VLM
reasoning, session state, and voice orchestration remain backend-owned.
"""

from __future__ import annotations

import base64
import copy
import logging
import threading
import time
from typing import Any

import cv2
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit

from app.core.settings import settings
from app.runtime.snapshot import SnapshotService, extract_512_crop
from app.runtime.vision import VisionRuntime, YOLO_AVAILABLE
from app.runtime.vlm import VisionLanguageRuntime
from app.runtime.voice import VoiceRuntime
from app.runtime.workflow import ConversationOrchestrator, WorkflowContext


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("surgeai.backend")


app = Flask(__name__)
app.config["SECRET_KEY"] = "surgeai-demo"
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    logger=True,
    engineio_logger=True,
)


class RuntimeController:
    def __init__(self) -> None:
        self.workflow = ConversationOrchestrator(settings)
        self.vision = VisionRuntime(settings)
        self.snapshot_service = SnapshotService(settings)
        self.voice_runtime = VoiceRuntime(settings)
        self.vlm_runtime = VisionLanguageRuntime(settings)

        self.runtime_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.context_lock = threading.Lock()
        self.camera_lock = threading.Lock()
        self.frame_lock = threading.Lock()

        self.camera = None
        self.latest_frame = None
        self.latest_context: WorkflowContext | None = None
        self.capture_stop_event = threading.Event()
        self.vision_stop_event = threading.Event()
        self.capture_thread: threading.Thread | None = None
        self.vision_thread: threading.Thread | None = None

        self.metrics = {"fps": 0.0, "latency": 0, "camera_locked": False}
        self.voice_chunk_lock = threading.Lock()
        self.voice_chunks_by_client: dict[str, list[bytes]] = {}

    def current_state_payload(self) -> dict[str, Any]:
        with self.state_lock:
            context = self._context_snapshot()
            services = self._services_payload()
            return self.workflow.build_payload(context, self.snapshot_service, services)

    def health_payload(self) -> dict[str, Any]:
        with self.camera_lock:
            camera_open = self.camera is not None and self.camera.isOpened()

        with self.state_lock:
            workflow_health = self.workflow.health()
            services = self._services_payload()

        service_errors = [
            services["snapshot"].get("last_error"),
            services["voice"].get("last_error"),
            services["vlm"].get("last_error"),
        ]
        return {
            "fps": round(self.metrics["fps"], 1),
            "latency": int(self.metrics["latency"]),
            "phase": self.workflow.phase,
            "phase_name": workflow_health["runtime_state"],
            "runtime_state": workflow_health["runtime_state"],
            "surgical_step": workflow_health["surgical_step"],
            "session_id": self.workflow.session_id,
            "camera": {
                "locked": camera_open,
                "index": settings.camera_index,
                "label": settings.camera_label,
                "fallback_allowed": False,
            },
            "services": {
                **services,
                "last_error": next((error for error in service_errors if error), None),
            },
            "yolo_ready": self.vision.model is not None and YOLO_AVAILABLE,
            "voice_active": workflow_health["runtime_state"] in {"LISTENING", "THINKING", "SPEAKING"},
            "last_vlm_call_at": workflow_health["last_vlm_call_at"],
            "last_scene_change_at": workflow_health["last_major_scene_at"],
        }

    def start_or_restart_session(self) -> dict[str, Any]:
        with self.runtime_lock:
            previous_session = self.workflow.session_id
            self._stop_threads_locked()
            if previous_session:
                self.snapshot_service.reset_session(previous_session)

            with self.state_lock:
                self.vision.reset()
                self.workflow.activate()
                if self.workflow.session_id:
                    self.snapshot_service.reset_session(self.workflow.session_id)

            self.capture_stop_event = threading.Event()
            self.vision_stop_event = threading.Event()
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True, name="surgeai-capture")
            self.vision_thread = threading.Thread(target=self._vision_loop, daemon=True, name="surgeai-vision")
            self.capture_thread.start()
            self.vision_thread.start()

        payload = self.current_state_payload()
        self.broadcast_state(payload)
        return payload

    def broadcast_state(self, payload: dict[str, Any] | None = None) -> None:
        payload = payload or self.current_state_payload()
        socketio.emit("frame_state", {"payload": payload}, namespace=settings.namespace)
        socketio.emit("system_health", {"payload": self.health_payload()}, namespace=settings.namespace)

    def mjpeg_stream(self):
        while True:
            frame = self._read_latest_frame()
            if frame is None:
                time.sleep(0.03)
                continue
            ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
            if not ok:
                time.sleep(0.03)
                continue
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + encoded.tobytes() + b"\r\n"
            time.sleep(1.0 / max(1, settings.target_fps))

    def handle_voice_start(self, client_id: str) -> None:
        with self.voice_chunk_lock:
            self.voice_chunks_by_client[client_id] = []
        with self.state_lock:
            self.workflow.note_capture_started()
            payload = self.workflow.build_payload(self._context_snapshot(), self.snapshot_service, self._services_payload())
        self.broadcast_state(payload)

    def handle_voice_cancel(self) -> None:
        with self.state_lock:
            self.workflow.note_capture_cancelled()
            payload = self.workflow.build_payload(self._context_snapshot(), self.snapshot_service, self._services_payload())
        self.broadcast_state(payload)

    def handle_text_query(self, text: str, trigger_kind: str = "wake_phrase") -> None:
        clean_text = (text or "").strip()
        if not clean_text or not self.workflow.session_id:
            return

        with self.state_lock:
            self.workflow.note_capture_started()
            self.workflow.note_transcript(clean_text)
            payload = self.workflow.build_payload(self._context_snapshot(), self.snapshot_service, self._services_payload())
        self.broadcast_state(payload)
        self._run_vlm_turn(user_transcript=clean_text, trigger_reason=trigger_kind)

    def mark_playback_complete(self) -> None:
        with self.state_lock:
            self.workflow.mark_playback_complete()
            payload = self.workflow.build_payload(self._context_snapshot(), self.snapshot_service, self._services_payload())
        self.broadcast_state(payload)

    def append_voice_chunk(self, client_id: str, audio_b64: str) -> None:
        if not audio_b64:
            return
        try:
            chunk = base64.b64decode(audio_b64)
        except Exception:
            return
        with self.voice_chunk_lock:
            self.voice_chunks_by_client.setdefault(client_id, []).append(chunk)

    def handle_voice_turn(self, *, client_id: str, audio_b64: str, mime_type: str, trigger_kind: str) -> None:
        if not self.workflow.session_id:
            return

        audio_bytes = b""
        if audio_b64:
            try:
                audio_bytes = base64.b64decode(audio_b64)
            except Exception:
                audio_bytes = b""
        if not audio_bytes:
            with self.voice_chunk_lock:
                audio_bytes = b"".join(self.voice_chunks_by_client.pop(client_id, []))
        else:
            with self.voice_chunk_lock:
                self.voice_chunks_by_client.pop(client_id, None)
        if not audio_bytes:
            self._set_degraded("Audio upload could not be decoded.", "Try the talk button again.")
            return

        try:
            transcript = self.voice_runtime.transcribe_audio(audio_bytes, mime_type)
        except Exception as exc:
            logger.warning("Voice transcription failed: %s", exc)
            self._set_degraded("Voice transcription is unavailable.", "Use the talk button and try again.")
            return

        wake_detected, stripped_transcript = self.voice_runtime.strip_wake_word(transcript)
        effective_transcript = transcript.strip()
        if trigger_kind != "manual":
            if not wake_detected:
                with self.state_lock:
                    self.workflow.note_capture_cancelled()
                    self.workflow.transcript_preview = None
                    payload = self.workflow.build_payload(self._context_snapshot(), self.snapshot_service, self._services_payload())
                self.broadcast_state(payload)
                return
            effective_transcript = stripped_transcript or "What should I do next?"

        with self.state_lock:
            self.workflow.note_transcript(effective_transcript)
            payload = self.workflow.build_payload(self._context_snapshot(), self.snapshot_service, self._services_payload())
        self.broadcast_state(payload)
        self._run_vlm_turn(user_transcript=effective_transcript, trigger_reason=f"{trigger_kind}_voice")

    def handle_scene_trigger(self, trigger_reason: str) -> None:
        self._run_vlm_turn(user_transcript=None, trigger_reason=trigger_reason)

    def _run_vlm_turn(self, *, user_transcript: str | None, trigger_reason: str | None) -> None:
        with self.state_lock:
            if not self.workflow.session_id or not self.workflow.can_call_vlm():
                return
            session_id = self.workflow.session_id
            context = self._context_snapshot()
            scene_events = list(self.workflow.scene_events)
            surgical_step = self.workflow.surgical_step
            previous_reply = self.workflow.last_assistant_reply
            self.workflow.note_vlm_call()
            payload = self.workflow.build_payload(context, self.snapshot_service, self._services_payload())
        self.broadcast_state(payload)

        crop_jpeg, _ = self.snapshot_service.latest_crop_jpeg(session_id, max_age_seconds=0.25)
        if crop_jpeg is None:
            banana = context.tracks.get("banana")
            banana_box = banana.box if banana and banana.box else None
            crop = extract_512_crop(context.frame, banana_box, settings.snapshot_size)
            if crop is not None:
                ok, encoded = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
                crop_jpeg = encoded.tobytes() if ok else None
        if crop_jpeg is None:
            crop_jpeg, _ = self.snapshot_service.latest_crop_jpeg(session_id)
        if crop_jpeg is None:
            self._set_degraded("ROI capture is unavailable.", "Move the banana back into view.")
            return

        try:
            result = self.vlm_runtime.analyze_scene(
                crop_jpeg=crop_jpeg,
                surgical_step=surgical_step,
                scene_events=scene_events,
                user_transcript=user_transcript,
                previous_reply=previous_reply,
                trigger_reason=trigger_reason,
            )
        except Exception as exc:
            logger.warning("VLM request failed: %s", exc)
            result = self._fallback_response(user_transcript, scene_events, surgical_step)
            with self.state_lock:
                audio_url = self._synthesize_if_possible(result, trigger_reason or "fallback")
                self.workflow.apply_degraded_response(
                    "Vision reasoning is degraded.",
                    result["next_instruction"],
                    audio_url=audio_url,
                )
                emitted = self.workflow.apply_assistant_result(result, audio_url=audio_url, source="fallback")
                payload = self.workflow.build_payload(self._context_snapshot(), self.snapshot_service, self._services_payload())
            self.broadcast_state(payload)
            if emitted and audio_url:
                self._emit_tts_ready(audio_url, payload)
            return

        with self.state_lock:
            audio_url = self._synthesize_if_possible(result, trigger_reason or "vlm")
            emitted = self.workflow.apply_assistant_result(result, audio_url=audio_url, source=trigger_reason or "vlm")
            payload = self.workflow.build_payload(self._context_snapshot(), self.snapshot_service, self._services_payload())
        self.broadcast_state(payload)
        if emitted and audio_url:
            self._emit_tts_ready(audio_url, payload)

    def _emit_tts_ready(self, audio_url: str, payload: dict[str, Any]) -> None:
        audio_base64 = None
        if audio_url.startswith("/artifacts/audio/"):
            file_name = audio_url.split("/artifacts/audio/", 1)[1]
            audio_path = settings.backend_root / "artifacts" / "audio" / file_name
            if audio_path.exists():
                audio_base64 = base64.b64encode(audio_path.read_bytes()).decode("utf-8")
        socketio.emit(
            "voice_tts_ready",
            {
                "payload": {
                    "audio_url": audio_url,
                    "audio_base64": audio_base64,
                    "voice_prompt": payload.get("voice_prompt"),
                    "voice_event_id": payload.get("voice_event_id"),
                }
            },
            namespace=settings.namespace,
        )

    def _synthesize_if_possible(self, result: dict[str, Any], trigger_label: str) -> str | None:
        speak_text = str(result.get("speak_text") or result.get("next_instruction") or "").strip()
        if not speak_text or not self.workflow.session_id:
            return None
        try:
            return self.voice_runtime.synthesize_audio(
                self.workflow.session_id,
                f"{trigger_label}_{int(time.time() * 1000)}",
                speak_text,
            )
        except Exception as exc:
            logger.warning("TTS synthesis failed: %s", exc)
            return None

    def _set_degraded(self, warning: str, hint: str) -> None:
        with self.state_lock:
            self.workflow.apply_degraded_response(warning, hint)
            payload = self.workflow.build_payload(self._context_snapshot(), self.snapshot_service, self._services_payload())
        self.broadcast_state(payload)

    def _fallback_response(self, user_transcript: str | None, scene_events: list[str], surgical_step: str) -> dict[str, Any]:
        if "banana_visible" not in scene_events:
            message = "Center the banana in view before we continue."
            next_step = "scene_setup"
        elif "clamp_locked" not in scene_events or "scalpel_locked" not in scene_events:
            message = "Show the clamp on the left and the scalpel on the right."
            next_step = "scene_setup"
        elif "scalpel_ready_to_cut" in scene_events:
            message = "Hold the scalpel on the marked incision line and cut slowly."
            next_step = "make_incision"
        elif "clamp_ready_to_lift" in scene_events:
            message = "Use the clamp to lift the skin away from the incision."
            next_step = "use_clamp"
        elif user_transcript:
            message = "Position the scalpel along the incision line and ask again when you are ready."
            next_step = surgical_step
        else:
            message = "Say 'Hey Surgeon, what do I do next?' when you want guidance."
            next_step = surgical_step

        return {
            "current_state": next_step,
            "step_complete": False,
            "next_instruction": message,
            "speak_text": message,
            "ui_hint": message,
            "confidence": 0.2,
            "should_advance_step": False,
        }

    def _services_payload(self) -> dict[str, Any]:
        return {
            "snapshot": self.snapshot_service.health(),
            "voice": self.voice_runtime.health(),
            "vlm": self.vlm_runtime.health(),
        }

    def _context_snapshot(self) -> WorkflowContext:
        with self.context_lock:
            if self.latest_context is not None:
                return copy.deepcopy(self.latest_context)

        frame = self._read_latest_frame()
        if frame is None:
            frame_height = settings.frame_height
            frame_width = settings.frame_width
        else:
            frame_height, frame_width = frame.shape[:2]

        return WorkflowContext(
            tracks=copy.deepcopy(self.vision.tracker.slots),
            red_rectangle=None,
            frame_width=frame_width,
            frame_height=frame_height,
            frame=frame,
        )

    def _capture_loop(self) -> None:
        while not self.capture_stop_event.is_set():
            with self.camera_lock:
                if self.camera is None or not self.camera.isOpened():
                    try:
                        self.camera = self._open_camera()
                    except Exception as exc:
                        logger.error("%s", exc)
                        self.metrics["camera_locked"] = False
                        time.sleep(1.0)
                        continue
                capture = self.camera

            ok, frame = capture.read()
            if not ok:
                self.metrics["camera_locked"] = False
                with self.camera_lock:
                    if self.camera is not None:
                        self.camera.release()
                        self.camera = None
                time.sleep(0.1)
                continue

            self.metrics["camera_locked"] = True
            with self.frame_lock:
                self.latest_frame = frame.copy()

    def _vision_loop(self) -> None:
        fps_ema = 0.0

        while not self.vision_stop_event.is_set():
            frame = self._read_latest_frame()
            if frame is None:
                time.sleep(0.02)
                continue

            start = time.time()
            frame_height, frame_width = frame.shape[:2]
            vision_frame = self.vision.process_frame(frame)

            session_id = self.workflow.session_id
            banana_track = vision_frame.tracks["banana"]
            banana_box = banana_track.box if banana_track.visible else None
            if session_id:
                self.snapshot_service.monitor_roi(session_id, frame, banana_box)

            context = WorkflowContext(
                tracks=copy.deepcopy(vision_frame.tracks),
                red_rectangle=copy.deepcopy(vision_frame.red_rectangle),
                frame_width=frame_width,
                frame_height=frame_height,
                frame=frame.copy(),
            )
            with self.context_lock:
                self.latest_context = copy.deepcopy(context)

            with self.state_lock:
                should_nudge, reason = self.workflow.should_auto_nudge(context)
                payload = self.workflow.build_payload(context, self.snapshot_service, self._services_payload())

            duration = max(1e-6, time.time() - start)
            fps_ema = (fps_ema * 0.85) + ((1.0 / duration) * 0.15)
            self.metrics["fps"] = fps_ema
            self.metrics["latency"] = int(duration * 1000)

            self.broadcast_state(payload)
            if should_nudge and reason:
                socketio.start_background_task(self.handle_scene_trigger, reason)

            remaining = (1.0 / max(1, settings.target_fps)) - (time.time() - start)
            if remaining > 0:
                time.sleep(remaining)

    def _open_camera(self):
        logger.info("[CAMERA] Locking to %s at index %s", settings.camera_label, settings.camera_index)
        capture = cv2.VideoCapture(settings.camera_index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            raise RuntimeError(
                f"[FATAL] {settings.camera_label} was not found at index {settings.camera_index}. "
                "SurgeAI will not fall back to any other camera."
            )

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, settings.frame_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.frame_height)
        capture.set(cv2.CAP_PROP_FPS, settings.target_fps)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        ok, _ = capture.read()
        if not ok:
            capture.release()
            raise RuntimeError(
                f"[FATAL] Camera index {settings.camera_index} opened but did not return frames. "
                "Close other apps using the BRIO and try again."
            )
        return capture

    def _read_latest_frame(self):
        with self.frame_lock:
            if self.latest_frame is None:
                return None
            return self.latest_frame.copy()

    def _stop_threads_locked(self) -> None:
        self.capture_stop_event.set()
        self.vision_stop_event.set()

        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=1.5)
        if self.vision_thread and self.vision_thread.is_alive():
            self.vision_thread.join(timeout=1.5)

        self.capture_thread = None
        self.vision_thread = None

        with self.camera_lock:
            if self.camera is not None:
                self.camera.release()
                self.camera = None

        with self.frame_lock:
            self.latest_frame = None

        with self.context_lock:
            self.latest_context = None
        with self.voice_chunk_lock:
            self.voice_chunks_by_client.clear()


runtime = RuntimeController()


@app.route("/video")
def video_feed():
    return Response(runtime.mjpeg_stream(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/health")
def health():
    return jsonify({"ok": True, **runtime.health_payload()})


@app.route("/artifacts/audio/<path:filename>")
def audio_artifact(filename: str):
    audio_dir = settings.backend_root / "artifacts" / "audio"
    return send_from_directory(audio_dir, filename)


@socketio.on("connect", namespace=settings.namespace)
def on_connect():
    logger.info("[Socket] Client connected")
    emit("frame_state", {"payload": runtime.current_state_payload()})
    emit("system_health", {"payload": runtime.health_payload()})


@socketio.on("activate_surgeai", namespace=settings.namespace)
def on_activate():
    logger.info("[Socket] activate_surgeai received")
    payload = runtime.start_or_restart_session()
    emit("frame_state", {"payload": payload})
    emit("system_health", {"payload": runtime.health_payload()})


@socketio.on("voice_turn_start", namespace=settings.namespace)
def on_voice_turn_start(_data):
    runtime.handle_voice_start(request.sid)


@socketio.on("voice_audio_chunk", namespace=settings.namespace)
def on_voice_audio_chunk(data):
    payload = data or {}
    runtime.append_voice_chunk(request.sid, payload.get("audio_base64", ""))


@socketio.on("voice_turn_end", namespace=settings.namespace)
def on_voice_turn_end(data):
    payload = data or {}
    socketio.start_background_task(
        runtime.handle_voice_turn,
        client_id=request.sid,
        audio_b64=payload.get("audio_base64", ""),
        mime_type=payload.get("mime_type", "audio/webm"),
        trigger_kind=payload.get("trigger_kind", "auto"),
    )


@socketio.on("voice_text_query", namespace=settings.namespace)
def on_voice_text_query(data):
    payload = data or {}
    socketio.start_background_task(
        runtime.handle_text_query,
        text=payload.get("text", ""),
        trigger_kind=payload.get("trigger_kind", "wake_phrase"),
    )


@socketio.on("voice_cancel", namespace=settings.namespace)
def on_voice_cancel():
    runtime.handle_voice_cancel()


@socketio.on("voice_playback_complete", namespace=settings.namespace)
def on_voice_playback_complete():
    runtime.mark_playback_complete()


@socketio.on("disconnect", namespace=settings.namespace)
def on_disconnect():
    logger.info("[Socket] Client disconnected")


if __name__ == "__main__":
    print("=" * 55)
    print("  SurgeAI Conversational Backend")
    print(f"  Video:     http://localhost:{settings.port}/video")
    print(f"  Health:    http://localhost:{settings.port}/health")
    print(f"  Socket.IO: http://localhost:{settings.port}{settings.namespace}")
    print(f"  YOLO:      {'Loaded' if runtime.vision.model is not None else 'Not available'}")
    print(f"  Camera:    {settings.camera_label} locked to index {settings.camera_index}")
    print("=" * 55)

    socketio.run(
        app,
        host="0.0.0.0",
        port=settings.port,
        debug=False,
        log_output=False,
        allow_unsafe_werkzeug=True,
    )
