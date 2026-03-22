import json
import logging
from typing import Any, Dict

from google import genai
from google.genai import types

logger = logging.getLogger("surgeai.backend")

# Internal keys stripped before HUD / Mongo (see loop_a_service).
SURGEAI_GEMINI_BACKOFF_KEY = "_surgeai_gemini_backoff_sec"
SURGEAI_SKIP_LLM_RAG_KEY = "_surgeai_skip_llm_rag"


def _response_text(response: Any) -> str:
    """Extract plain text from google-genai responses (handles multiple shapes)."""
    text = getattr(response, "text", None)
    if text:
        return str(text).strip()
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", None) or []:
            t = getattr(part, "text", None)
            if t:
                return str(t).strip()
    return ""


def strip_internal_gemini_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove SurgeAI-only keys from Gemini payloads before logging or UI."""
    return {k: v for k, v in data.items() if not str(k).startswith("_surgeai")}


class GeminiVisionClient:
    """Vision-language scene analysis using the `google-genai` SDK."""

    def __init__(self, settings: Any) -> None:
        self.settings = settings
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.gemini_model

    def ping(self) -> bool:
        try:
            _ = self._client
            return bool(self.model)
        except Exception:
            return False

    def analyze_scene(self, frame_jpeg: bytes, scene_hint: Dict[str, Any]) -> Dict[str, Any]:
        # Short prompt = fewer tokens billed on multimodal calls.
        prompt = (
            "Return JSON only: current_step, tool_correct, warning, instruction, confidence, ar_boxes. "
            "ar_boxes: optional [{x,y,w,h,label}] normalized 0-1. "
            f"Color hints: {scene_hint}."
        )
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=frame_jpeg, mime_type="image/jpeg"),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                ),
            )
            text = _response_text(response)
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(text)
            boxes = parsed.get("ar_boxes") or []
            if not isinstance(boxes, list):
                boxes = []
            return {
                "current_step": parsed.get("current_step", ""),
                "tool_correct": bool(parsed.get("tool_correct", True)),
                "warning": parsed.get("warning", ""),
                "instruction": parsed.get("instruction", ""),
                "confidence": float(parsed.get("confidence", 0.7)),
                "ar_boxes": boxes,
            }
        except Exception as exc:
            err = str(exc).lower()
            rate_limited = (
                "429" in err
                or "resource exhausted" in err
                or "rate" in err
                or "quota" in err
                or "too many requests" in err
            )
            backoff = (
                float(self.settings.gemini_rate_limit_backoff_seconds)
                if rate_limited
                else float(self.settings.gemini_error_backoff_seconds)
            )
            if rate_limited:
                logger.warning(
                    "Gemini rate limit / quota — color fallback + backoff %.0fs. "
                    "Tune VLM_MAX_HZ or billing. %s",
                    backoff,
                    exc,
                )
            else:
                logger.warning("Gemini analyze_scene failed — color fallback + backoff %.0fs: %s", backoff, exc)
            return {
                "current_step": "",
                "tool_correct": not bool(
                    scene_hint.get("red_present") and not scene_hint.get("blue_present")
                ),
                "warning": "Incorrect instrument detected - scalpel required."
                if scene_hint.get("red_present") and not scene_hint.get("blue_present")
                else "",
                "instruction": "Use scalpel (blue) near incision zone."
                if scene_hint.get("red_present")
                else "",
                "confidence": 0.6,
                "ar_boxes": [],
                SURGEAI_GEMINI_BACKOFF_KEY: backoff,
                SURGEAI_SKIP_LLM_RAG_KEY: True,
            }

    def narrate_scene(self, frame_jpeg: bytes) -> str:
        prompt = "You are a surgical assistant observing a video feed. Narrate what is happening in a short, concise sentence."
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=frame_jpeg, mime_type="image/jpeg"),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    temperature=0.4,
                ),
            )
            return _response_text(response)
        except Exception as exc:
            logger.warning("Gemini narrate_scene failed: %s", exc)
            return f"Error narrating scene: {exc}"
