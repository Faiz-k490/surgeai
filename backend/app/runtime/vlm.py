from __future__ import annotations

import base64
import json
import logging
from typing import Any

from openai import OpenAI

from app.core.settings import Settings


logger = logging.getLogger("surgeai.vlm")


SYSTEM_PROMPT = """
You are SurgeonAI, a concise surgical training assistant for a banana surgery simulation.

You receive:
- the current surgical step
- scene events detected locally
- the user's transcript if present
- a 512x512 ROI image centered on the banana

Return strict JSON with these keys only:
{
  "current_state": "scene_setup|position_scalpel|make_incision|use_clamp|complete",
  "step_complete": true,
  "next_instruction": "short instruction",
  "speak_text": "short spoken reply",
  "ui_hint": "short hint",
  "confidence": 0.0,
  "should_advance_step": false
}

Rules:
- Keep replies under 25 words.
- If the user asks what to do next, answer directly.
- If the scene is unclear, say what is missing.
- Only mark complete when the banana procedure appears finished.
""".strip()


class VisionLanguageRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.last_error: str | None = None

    def health(self) -> dict[str, Any]:
        return {
            "openai_configured": self.client is not None,
            "vision_model": self.settings.openai_vision_model,
            "last_error": self.last_error,
        }

    def analyze_scene(
        self,
        *,
        crop_jpeg: bytes,
        surgical_step: str,
        scene_events: list[str],
        user_transcript: str | None,
        previous_reply: str | None,
        trigger_reason: str | None,
    ) -> dict[str, Any]:
        if self.client is None:
            self.last_error = "OpenAI VLM unavailable: OPENAI_API_KEY is missing"
            raise RuntimeError(self.last_error)

        payload_text = json.dumps(
            {
                "surgical_step": surgical_step,
                "scene_events": scene_events,
                "user_transcript": user_transcript,
                "previous_reply": previous_reply,
                "trigger_reason": trigger_reason,
            },
            ensure_ascii=True,
        )
        image_data = base64.b64encode(crop_jpeg).decode("utf-8")
        completion = self.client.chat.completions.create(
            model=self.settings.openai_vision_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": payload_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}",
                                "detail": "low",
                            },
                        },
                    ],
                },
            ],
            temperature=0.2,
            max_tokens=220,
        )
        content = completion.choices[0].message.content or "{}"
        parsed = self._parse_json_object(content)
        self.last_error = None
        return {
            "current_state": parsed.get("current_state", surgical_step),
            "step_complete": bool(parsed.get("step_complete", False)),
            "next_instruction": str(parsed.get("next_instruction", "")).strip(),
            "speak_text": str(parsed.get("speak_text", "")).strip(),
            "ui_hint": str(parsed.get("ui_hint", "")).strip(),
            "confidence": float(parsed.get("confidence", 0.0) or 0.0),
            "should_advance_step": bool(parsed.get("should_advance_step", False)),
        }

    def _parse_json_object(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = next((part for part in parts if "{" in part and "}" in part), text)
            text = text.replace("json", "", 1).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            self.last_error = "OpenAI VLM returned non-JSON content"
            raise RuntimeError(self.last_error)

        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            self.last_error = f"OpenAI VLM JSON parse failed: {exc}"
            logger.warning(self.last_error)
            raise RuntimeError(self.last_error) from exc
