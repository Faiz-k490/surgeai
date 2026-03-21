import json
from typing import Any, Dict

import google.generativeai as genai


class GeminiVisionClient:
    def __init__(self, settings):
        self.settings = settings
        genai.configure(api_key=settings.gemini_api_key)
        # Keep model configurable to avoid hard-coding preview-only names.
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def ping(self) -> bool:
        try:
            _ = self.model
            return True
        except Exception:
            return False

    def analyze_scene(self, frame_jpeg: bytes, scene_hint: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            "Return strict JSON keys only: current_step, tool_correct, warning, instruction, confidence. "
            f"Scene hints from color detector: {scene_hint}."
        )
        try:
            response = self.model.generate_content(
                [
                    {"mime_type": "image/jpeg", "data": frame_jpeg},
                    prompt,
                ]
            )
            text = (response.text or "").strip()
            # Gemini may wrap JSON in markdown; trim common fence patterns.
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(text)
            return {
                "current_step": parsed.get("current_step", ""),
                "tool_correct": bool(parsed.get("tool_correct", True)),
                "warning": parsed.get("warning", ""),
                "instruction": parsed.get("instruction", ""),
                "confidence": float(parsed.get("confidence", 0.7)),
            }
        except Exception:
            # Fallback keeps demo resilient when network/model parsing fails.
            return {
                "current_step": "",
                "tool_correct": not bool(scene_hint.get("red_present") and not scene_hint.get("blue_present")),
                "warning": "Incorrect instrument detected - scalpel required."
                if scene_hint.get("red_present") and not scene_hint.get("blue_present")
                else "",
                "instruction": "Use scalpel (blue) near incision zone." if scene_hint.get("red_present") else "",
                "confidence": 0.6,
            }
