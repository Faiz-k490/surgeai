from __future__ import annotations

import logging
import re
import time
from typing import Any

import requests

from app.core.settings import Settings


logger = logging.getLogger("surgeai.voice")


WAKE_WORD_PATTERN = re.compile(r"^\s*(hey[\s,-]*surgeon)\b[:,!\-\s]*", re.IGNORECASE)
NON_ALPHANUMERIC_PATTERN = re.compile(r"[^a-z0-9\s]")
COMPLETION_PHRASES = (
    "im done",
    "i am done",
    "done now",
    "im finished",
    "i am finished",
    "finished now",
    "we are done",
    "were done",
    "that is it",
    "thats it",
    "all done",
    "all finished",
    "procedure complete",
    "procedure is complete",
    "the procedure is complete",
    "session complete",
    "session is complete",
    "the session is complete",
)


class VoiceRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.audio_dir = settings.backend_root / "artifacts" / "audio"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.last_error: str | None = None
        self.last_transcript: str | None = None
        self.last_audio_file: str | None = None

    def health(self) -> dict[str, Any]:
        return {
            "elevenlabs_configured": bool(self.settings.elevenlabs_api_key),
            "stt_model": self.settings.elevenlabs_stt_model,
            "tts_model": self.settings.elevenlabs_tts_model,
            "voice_id": self.settings.elevenlabs_tts_voice_id,
            "last_audio_file": self.last_audio_file,
            "last_error": self.last_error,
        }

    def transcribe_audio(self, audio_bytes: bytes, mime_type: str) -> str:
        if not self.settings.elevenlabs_api_key:
            self.last_error = "ElevenLabs STT unavailable: ELEVENLABS_API_KEY is missing"
            raise RuntimeError(self.last_error)

        filename = self._mime_to_filename(mime_type)
        files = {
            "file": (filename, audio_bytes, mime_type or "application/octet-stream"),
        }
        data = {"model_id": self.settings.elevenlabs_stt_model}
        response = requests.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": self.settings.elevenlabs_api_key},
            data=data,
            files=files,
            timeout=25,
        )
        response.raise_for_status()
        body = response.json()
        transcript = (body.get("text") or body.get("transcript") or "").strip()
        if not transcript:
            self.last_error = "ElevenLabs STT returned an empty transcript"
            raise RuntimeError(self.last_error)
        self.last_transcript = transcript
        self.last_error = None
        return transcript

    def strip_wake_word(self, transcript: str) -> tuple[bool, str]:
        match = WAKE_WORD_PATTERN.match(transcript or "")
        if not match:
            return False, (transcript or "").strip()
        remainder = WAKE_WORD_PATTERN.sub("", transcript, count=1).strip()
        return True, remainder

    def is_completion_intent(self, transcript: str | None) -> bool:
        """Require an explicit completion statement for the whole session."""
        if "?" in (transcript or ""):
            return False
        _, command = self.strip_wake_word(transcript or "")
        normalized = self._normalize_text(command)
        if not normalized:
            return False

        # Match the whole utterance. A keyword bag also matches negations,
        # questions, and partial tasks such as "I am done with setup".
        normalized = re.sub(r"^(?:ok|okay|alright|yes)\s+", "", normalized)
        normalized = re.sub(r"\s+(?:thanks|thank you)$", "", normalized)
        return any(normalized in (phrase, f"{phrase} now") for phrase in COMPLETION_PHRASES)

    def _normalize_text(self, transcript: str | None) -> str:
        text = (transcript or "").lower()
        text = text.replace("i'm", "im").replace("we're", "were").replace("that's", "thats")
        text = NON_ALPHANUMERIC_PATTERN.sub(" ", text)
        return " ".join(text.split())

    def synthesize_audio(self, session_id: str, voice_event_id: str, text: str) -> str | None:
        if not self.settings.elevenlabs_api_key:
            self.last_error = "ElevenLabs TTS unavailable: ELEVENLABS_API_KEY is missing"
            raise RuntimeError(self.last_error)
        if not self.settings.elevenlabs_tts_voice_id:
            self.last_error = "ElevenLabs TTS unavailable: ELEVENLABS_TTS_VOICE_ID is missing"
            raise RuntimeError(self.last_error)

        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.settings.elevenlabs_tts_voice_id}",
            headers={
                "xi-api-key": self.settings.elevenlabs_api_key,
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": self.settings.elevenlabs_tts_model,
                "voice_settings": {"stability": 0.45, "similarity_boost": 0.75},
            },
            timeout=25,
        )
        response.raise_for_status()

        safe_event_id = voice_event_id.replace(":", "_")
        file_name = f"{session_id}_{safe_event_id}_{int(time.time() * 1000)}.mp3"
        file_path = self.audio_dir / file_name
        file_path.write_bytes(response.content)
        self.last_audio_file = file_name
        self.last_error = None
        return f"/artifacts/audio/{file_name}"

    def _mime_to_filename(self, mime_type: str) -> str:
        if "wav" in mime_type:
            return "voice-turn.wav"
        if "mp4" in mime_type or "m4a" in mime_type:
            return "voice-turn.m4a"
        if "webm" in mime_type:
            return "voice-turn.webm"
        return "voice-turn.bin"
