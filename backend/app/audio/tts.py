"""
Loop A guidance speech: ElevenLabs only. Deduplicates — won't repeat the same text.
"""

import logging
import threading

logger = logging.getLogger("surgeai.audio.guidance")


class GuidanceSpeaker:
    """Speaks guidance via ElevenLabs + PyAudio (see `backend.app.loop_b.tts_pipeline`)."""

    def __init__(self, settings):
        self.settings = settings
        self._last_spoken_text: str = ""
        self._speaking = False

    def ping(self) -> bool:
        return bool(self.settings.elevenlabs_api_key)

    def speak(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        if text == self._last_spoken_text:
            return
        if self._speaking:
            return
        self._last_spoken_text = text

        def _run() -> None:
            self._speaking = True
            try:
                try:
                    from backend.app.loop_b.tts_pipeline import speak as elevenlabs_speak
                except ModuleNotFoundError:
                    from app.loop_b.tts_pipeline import speak as elevenlabs_speak

                elevenlabs_speak(text)
            except Exception as exc:
                logger.error("Loop A ElevenLabs TTS failed: %s", exc)
            finally:
                self._speaking = False

        threading.Thread(target=_run, daemon=True).start()
