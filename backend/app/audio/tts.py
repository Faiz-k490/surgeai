import io
import threading
import wave
from urllib import request

import pyttsx3


class GuidanceSpeaker:
    def __init__(self, settings):
        self.settings = settings
        self.engine = pyttsx3.init()
        self.voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel

    def ping(self) -> bool:
        return bool(self.settings.elevenlabs_api_key)

    def _speak_fallback(self, text: str) -> None:
        self.engine.say(text)
        self.engine.runAndWait()

    def _speak_elevenlabs(self, text: str) -> None:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        payload = (
            '{"text": "' + text.replace('"', '\\"') + '",'
            '"model_id": "eleven_turbo_v2_5",'
            '"voice_settings": {"stability": 0.35, "similarity_boost": 0.75}}'
        ).encode("utf-8")
        req = request.Request(
            url=url,
            data=payload,
            method="POST",
            headers={
                "xi-api-key": self.settings.elevenlabs_api_key,
                "Content-Type": "application/json",
                "Accept": "audio/wav",
            },
        )
        with request.urlopen(req, timeout=10) as resp:
            audio = resp.read()
        # Keep playback dependency-light: parse wav and feed pyttsx3 fallback if parse fails.
        try:
            with wave.open(io.BytesIO(audio), "rb"):
                pass
            # If WAV returns from API, pyttsx3 still used for actual playback in this scaffold.
            self._speak_fallback(text)
        except Exception:
            self._speak_fallback(text)

    def speak(self, text: str) -> None:
        def _run() -> None:
            try:
                self._speak_elevenlabs(text)
            except Exception:
                # Do not block Loop A if network TTS fails.
                self._speak_fallback(text)

        threading.Thread(target=_run, daemon=True).start()
