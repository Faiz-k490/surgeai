from __future__ import annotations

import hashlib
import logging
import math
import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.core.settings import Settings
from app.runtime.snapshot import SnapshotService
from app.runtime.vision import (
    RedRectangle,
    TrackSlot,
    bbox_center,
    deviation_to_hex,
    pt_distance,
    scalpel_angle_from_bbox,
)


logger = logging.getLogger("surgeai.workflow")


RUNTIME_STATES = {
    0: "IDLE",
    1: "ACTIVATING",
    2: "READY",
    3: "LISTENING",
    4: "THINKING",
    5: "SPEAKING",
    6: "DEGRADED",
}

SURGICAL_STEPS = {
    "scene_setup",
    "position_scalpel",
    "make_incision",
    "use_clamp",
    "complete",
}


@dataclass
class WorkflowContext:
    tracks: dict[str, TrackSlot]
    red_rectangle: RedRectangle | None
    frame_width: int
    frame_height: int
    frame: Any | None


class ConversationOrchestrator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.phase = 0
        self.runtime_state = RUNTIME_STATES[0]
        self.surgical_step = "scene_setup"
        self.session_id: str | None = None
        self.phase_started_at = 0.0
        self.voice_counter = 0
        self.pending_voice: dict[str, Any] | None = None
        self.warning: str | None = None
        self.next_step_hint = "Activate SurgeAI to begin."
        self.transcript_preview: str | None = None
        self.voice_audio_url: str | None = None
        self.last_user_transcript: str | None = None
        self.last_assistant_reply: str | None = None
        self.last_response_fingerprint: str | None = None
        self.last_response_at = 0.0
        self.last_vlm_call_at = 0.0
        self.last_major_scene_at = 0.0
        self.last_major_scene_reason: str | None = None
        self.scene_events: list[str] = []
        self.completion_snapshot_requested = False

    def activate(self) -> None:
        self.session_id = uuid.uuid4().hex[:8]
        self.phase = 1
        self.runtime_state = RUNTIME_STATES[1]
        self.surgical_step = "scene_setup"
        self.phase_started_at = time.time()
        self.voice_counter = 0
        self.pending_voice = None
        self.warning = None
        self.next_step_hint = "Show the banana, clamp, and scalpel to the camera."
        self.transcript_preview = None
        self.voice_audio_url = None
        self.last_user_transcript = None
        self.last_assistant_reply = None
        self.last_response_fingerprint = None
        self.last_response_at = 0.0
        self.last_vlm_call_at = 0.0
        self.last_major_scene_at = 0.0
        self.last_major_scene_reason = None
        self.scene_events = []
        self.completion_snapshot_requested = False
        logger.info("Activated conversational session %s", self.session_id)

    def reset(self) -> None:
        self.__init__(self.settings)

    def note_capture_started(self) -> None:
        if self.phase == 0:
            return
        self.runtime_state = RUNTIME_STATES[3]
        self.warning = "Listening for: 'Hey Surgeon...'"

    def note_capture_cancelled(self) -> None:
        if self.phase == 0:
            return
        self.runtime_state = RUNTIME_STATES[2]
        self.warning = None
        self.transcript_preview = None

    def note_transcript(self, transcript: str | None) -> None:
        self.transcript_preview = transcript.strip() if transcript else None
        self.last_user_transcript = self.transcript_preview
        if self.phase != 0:
            self.runtime_state = RUNTIME_STATES[4]

    def note_vlm_call(self, now: float | None = None) -> None:
        self.last_vlm_call_at = now or time.time()
        if self.phase != 0:
            self.runtime_state = RUNTIME_STATES[4]

    def can_call_vlm(self, now: float | None = None) -> bool:
        now = now or time.time()
        return (now - self.last_vlm_call_at) >= self.settings.vlm_cooldown_seconds

    def should_auto_nudge(self, context: WorkflowContext) -> tuple[bool, str | None]:
        now = time.time()
        if self.phase == 0 or self.runtime_state in {RUNTIME_STATES[3], RUNTIME_STATES[4], RUNTIME_STATES[5]}:
            return False, None
        reason = self._major_scene_reason(context, now)
        if reason is None:
            return False, None
        if (now - self.last_major_scene_at) < self.settings.major_scene_cooldown_seconds:
            return False, None
        self.last_major_scene_at = now
        self.last_major_scene_reason = reason
        return True, reason

    def apply_assistant_result(
        self,
        result: dict[str, Any],
        *,
        audio_url: str | None = None,
        source: str = "user",
    ) -> bool:
        self.warning = None
        requested_step = str(result.get("current_state") or "").strip()
        if requested_step in SURGICAL_STEPS:
            self.surgical_step = requested_step
        elif bool(result.get("step_complete")):
            self.surgical_step = self._advance_step(self.surgical_step)

        next_hint = str(result.get("next_instruction") or result.get("ui_hint") or "").strip()
        if next_hint:
            self.next_step_hint = next_hint

        speech = str(result.get("speak_text") or next_hint or "").strip()
        if not speech:
            self.runtime_state = RUNTIME_STATES[2]
            self.voice_audio_url = audio_url
            return False

        fingerprint = hashlib.sha1(speech.lower().encode("utf-8")).hexdigest()
        now = time.time()
        if (
            fingerprint == self.last_response_fingerprint
            and (now - self.last_response_at) < self.settings.response_dedupe_seconds
        ):
            logger.info("Suppressing duplicate response from %s trigger", source)
            self.runtime_state = RUNTIME_STATES[2]
            return False

        self.last_response_fingerprint = fingerprint
        self.last_response_at = now
        self.last_assistant_reply = speech
        self.voice_audio_url = audio_url
        self._queue_voice(speech)
        self.runtime_state = RUNTIME_STATES[5] if audio_url else RUNTIME_STATES[2]

        if self.surgical_step == "complete" and not self.completion_snapshot_requested:
            self.completion_snapshot_requested = True
        return True

    def apply_degraded_response(self, warning: str, next_hint: str, audio_url: str | None = None) -> None:
        self.runtime_state = RUNTIME_STATES[6]
        self.warning = warning
        self.next_step_hint = next_hint
        self.voice_audio_url = audio_url

    def mark_playback_complete(self) -> None:
        if self.phase != 0:
            self.runtime_state = RUNTIME_STATES[2]

    def observe_scene(self, context: WorkflowContext) -> None:
        now = time.time()
        if self.phase == 1 and context.frame is not None:
            self.phase = 1
            self.runtime_state = RUNTIME_STATES[2]

        self.scene_events = self._scene_events(context, now)
        self.warning = self._warning_for_scene(context, now)
        if not self.warning and self.runtime_state == RUNTIME_STATES[1]:
            self.runtime_state = RUNTIME_STATES[2]

        if self.phase != 0 and self.surgical_step != "complete":
            self.surgical_step = self._suggest_step(context, now, self.surgical_step)

    def maybe_finalize_completion(self, context: WorkflowContext, snapshot_service: SnapshotService) -> None:
        if not self.session_id or self.surgical_step != "complete" or not self.completion_snapshot_requested:
            return
        banana = context.tracks.get("banana")
        banana_box = banana.box if banana and banana.box else None
        if snapshot_service.finalize_session(self.session_id, context.frame, banana_box):
            self.completion_snapshot_requested = False

    def build_payload(self, context: WorkflowContext, snapshot_service: SnapshotService, services: dict[str, Any]) -> dict[str, Any]:
        self.observe_scene(context)
        self.maybe_finalize_completion(context, snapshot_service)

        ar_elements = self._build_ar_elements(context)
        voice = self.pending_voice
        self.pending_voice = None

        angle_data, trace_line = self._angle_guidance(
            context.tracks.get("scalpel"),
            context.red_rectangle,
            context.frame_width,
            context.frame_height,
        )
        if trace_line is not None:
            ar_elements.append(trace_line)

        if self.surgical_step == "complete":
            ar_elements.append({"type": "success_overlay"})

        return {
            "current_phase": self.phase,
            "phase_name": self.runtime_state,
            "runtime_state": self.runtime_state,
            "surgical_step": self.surgical_step,
            "session_id": self.session_id,
            "voice_prompt": voice["message"] if voice else None,
            "voice_event_id": voice["id"] if voice else None,
            "voice_audio_url": self.voice_audio_url,
            "warning": self.warning,
            "countdown_seconds": None,
            "angle_data": angle_data,
            "ar_elements": ar_elements,
            "scene_events": self.scene_events,
            "next_step_hint": self.next_step_hint,
            "listening_state": self.runtime_state.lower(),
            "transcript_preview": self.transcript_preview,
            "snapshot_status": snapshot_service.health(),
            "services": services,
        }

    def health(self) -> dict[str, Any]:
        return {
            "runtime_state": self.runtime_state,
            "surgical_step": self.surgical_step,
            "last_vlm_call_at": self.last_vlm_call_at,
            "last_major_scene_at": self.last_major_scene_at,
            "last_major_scene_reason": self.last_major_scene_reason,
        }

    def _queue_voice(self, message: str) -> None:
        if not self.session_id:
            return
        self.voice_counter += 1
        self.pending_voice = {"id": f"{self.session_id}:{self.voice_counter}", "message": message}
        logger.info("Voice event %s: %s", self.pending_voice["id"], message)

    def _advance_step(self, step: str) -> str:
        ordered = ["scene_setup", "position_scalpel", "make_incision", "use_clamp", "complete"]
        try:
            index = ordered.index(step)
        except ValueError:
            return "scene_setup"
        return ordered[min(index + 1, len(ordered) - 1)]

    def _suggest_step(self, context: WorkflowContext, now: float, current_step: str) -> str:
        tracks = context.tracks
        banana = tracks.get("banana")
        clamp = tracks.get("clamp")
        scalpel = tracks.get("scalpel")

        if not self._is_track_reliable(banana, now) or not clamp or not scalpel:
            return "scene_setup"
        if not clamp.locked or not scalpel.locked:
            return "scene_setup"
        if self._scalpel_near_target(scalpel, banana, context.red_rectangle, context.frame_width, context.frame_height):
            if context.red_rectangle is not None:
                return "make_incision"
            return "position_scalpel"
        if self._clamp_near_target(clamp, banana, context.red_rectangle, context.frame_width, context.frame_height):
            return "use_clamp"
        return current_step if current_step != "scene_setup" else "position_scalpel"

    def _major_scene_reason(self, context: WorkflowContext, now: float) -> str | None:
        events = set(self._scene_events(context, now))
        tracked_events = [
            "banana_visible",
            "clamp_locked",
            "scalpel_locked",
            "tools_ready",
            "scalpel_ready_to_cut",
            "clamp_ready_to_lift",
            "procedure_complete",
        ]
        for event_name in tracked_events:
            if event_name in events and event_name not in self.scene_events:
                return event_name
        return None

    def _scene_events(self, context: WorkflowContext, now: float) -> list[str]:
        tracks = context.tracks
        banana = tracks.get("banana")
        clamp = tracks.get("clamp")
        scalpel = tracks.get("scalpel")
        events: list[str] = []

        if self._is_track_reliable(banana, now):
            events.append("banana_visible")
        if clamp and clamp.locked:
            events.append("clamp_locked")
        if scalpel and scalpel.locked:
            events.append("scalpel_locked")
        if self._is_track_reliable(clamp, now) and self._is_track_reliable(scalpel, now):
            events.append("tools_ready")
        if context.red_rectangle is not None:
            events.append("incision_visible")
        if self._scalpel_near_target(scalpel, banana, context.red_rectangle, context.frame_width, context.frame_height):
            events.append("scalpel_ready_to_cut")
        if self._clamp_near_target(clamp, banana, context.red_rectangle, context.frame_width, context.frame_height):
            events.append("clamp_ready_to_lift")
        if self.surgical_step == "complete":
            events.append("procedure_complete")
        return events

    def _build_ar_elements(self, context: WorkflowContext) -> list[dict[str, Any]]:
        if self.phase == 0:
            return []

        ar_elements: list[dict[str, Any]] = []
        for slot_name in ("banana", "clamp", "scalpel"):
            overlay = context.tracks[slot_name].as_overlay(context.frame_width, context.frame_height)
            if overlay:
                ar_elements.append(overlay)

        if context.red_rectangle is not None:
            ar_elements.append(
                {
                    "type": "polygon",
                    "label": "Incision Zone",
                    "color": "#ef4444",
                    "points": [
                        (point_x / context.frame_width, point_y / context.frame_height)
                        for point_x, point_y in context.red_rectangle.points
                    ],
                }
            )

        ar_elements.append({"type": "zone_debug"})
        return ar_elements

    def _warning_for_scene(self, context: WorkflowContext, now: float) -> str | None:
        tracks = context.tracks
        banana = tracks.get("banana")
        clamp = tracks.get("clamp")
        scalpel = tracks.get("scalpel")

        if self.phase == 0:
            return None
        if context.frame is None:
            return "Waiting for BRIO camera frames."
        if not self._is_track_reliable(banana, now):
            return "Place the banana fully inside the camera view."
        if clamp is None or not clamp.locked:
            return "Introduce the clamp from the left side."
        if scalpel is None or not scalpel.locked:
            return "Introduce the scalpel from the right side."
        if self.runtime_state == RUNTIME_STATES[3]:
            return "Listening..."
        if self.runtime_state == RUNTIME_STATES[4]:
            return "Analyzing the scene."
        if self.runtime_state == RUNTIME_STATES[6]:
            return self.warning
        return None

    def _angle_guidance(
        self,
        scalpel: TrackSlot | None,
        red_rectangle: RedRectangle | None,
        frame_width: int,
        frame_height: int,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        if scalpel is None or not scalpel.visible or scalpel.box is None or red_rectangle is None:
            return {"approach_angle": 0, "status": "idle"}, None

        scalpel_angle = scalpel_angle_from_bbox(scalpel.box)
        difference = abs(scalpel_angle - red_rectangle.angle_degrees)
        if difference > 90:
            difference = 180 - difference

        if 30 <= difference <= 60:
            status = "Optimal"
        elif difference > 60:
            status = "Too Steep"
        else:
            status = "Too Shallow"

        scalpel_center = bbox_center(scalpel.box)
        distance = pt_distance(scalpel_center, (red_rectangle.center_x, red_rectangle.center_y))
        deviation = min(1.0, distance / max(180.0, frame_width * 0.18))

        return (
            {"approach_angle": int(round(difference)), "status": status},
            {
                "type": "line",
                "x1": scalpel_center[0] / frame_width,
                "y1": scalpel_center[1] / frame_height,
                "x2": red_rectangle.center_x / frame_width,
                "y2": red_rectangle.center_y / frame_height,
                "color": deviation_to_hex(deviation),
            },
        )

    def _is_track_reliable(self, slot: TrackSlot | None, now: float) -> bool:
        return bool(slot and slot.is_recent(now, self.settings.track_ttl_seconds))

    def _scalpel_near_target(
        self,
        scalpel: TrackSlot | None,
        banana: TrackSlot | None,
        red_rectangle: RedRectangle | None,
        frame_width: int,
        frame_height: int,
    ) -> bool:
        return self._tool_near_target(scalpel, banana, red_rectangle, frame_width, frame_height)

    def _clamp_near_target(
        self,
        clamp: TrackSlot | None,
        banana: TrackSlot | None,
        red_rectangle: RedRectangle | None,
        frame_width: int,
        frame_height: int,
    ) -> bool:
        return self._tool_near_target(clamp, banana, red_rectangle, frame_width, frame_height)

    def _tool_near_target(
        self,
        tool: TrackSlot | None,
        banana: TrackSlot | None,
        red_rectangle: RedRectangle | None,
        frame_width: int,
        frame_height: int,
    ) -> bool:
        if tool is None or banana is None or tool.box is None or banana.box is None:
            return False
        tool_center = bbox_center(tool.box)
        target_point = bbox_center(banana.box)
        if red_rectangle is not None:
            target_point = (red_rectangle.center_x, red_rectangle.center_y)

        banana_width = banana.box[2] - banana.box[0]
        banana_height = banana.box[3] - banana.box[1]
        max_distance = max(40.0, math.sqrt((banana_width ** 2) + (banana_height ** 2)) * 0.28)
        if pt_distance(tool_center, target_point) <= max_distance:
            return True

        x1, y1, x2, y2 = banana.box
        padding_x = max(12.0, banana_width * 0.1)
        padding_y = max(12.0, banana_height * 0.1)
        return (x1 - padding_x) <= tool_center[0] <= (x2 + padding_x) and (y1 - padding_y) <= tool_center[1] <= (y2 + padding_y)
