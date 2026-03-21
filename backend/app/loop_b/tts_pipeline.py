"""
tts_pipeline.py — ElevenLabs text-to-speech for SurgeAI.

Streams speech via ElevenLabs + PyAudio. Voice ID is resolved once and cached.
"""

import logging
import os

import pyaudio
from elevenlabs import ElevenLabs

logger = logging.getLogger("surgeai.tts")

MODEL_ID = "eleven_flash_v2_5"

_cached_voice_id: str | None = None


def _voice_id() -> str:
    """Resolve voice ID once, then cache for the process lifetime."""
    global _cached_voice_id
    if _cached_voice_id:
        return _cached_voice_id

    from_env = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    if from_env:
        _cached_voice_id = from_env
        return _cached_voice_id

    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        return "21m00Tcm4TlvDq8ikWAM"
    try:
        client = ElevenLabs(api_key=api_key)
        voices = client.voices.get_all()
        voice_list = getattr(voices, "voices", voices) or []
        if voice_list:
            picked = voice_list[0]
            vid = getattr(picked, "voice_id", None) or str(picked)
            logger.info("Using ElevenLabs voice: %s (%s)", getattr(picked, "name", "?"), vid)
            _cached_voice_id = vid
            return vid
    except Exception as exc:
        logger.warning("Could not list ElevenLabs voices (%s), falling back to default", exc)
    return "21m00Tcm4TlvDq8ikWAM"


def speak(text: str) -> None:
    if not text:
        return

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        logger.error("ELEVENLABS_API_KEY not set — cannot synthesise speech.")
        return

    try:
        client = ElevenLabs(api_key=api_key)
        vid = _voice_id()
        audio_iter = client.text_to_speech.convert(
            text=text,
            voice_id=vid,
            model_id=MODEL_ID,
            output_format="pcm_16000",
        )

        logger.info("Streaming ElevenLabs TTS (%d chars)", len(text))
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            output=True,
        )

        for chunk in audio_iter:
            if chunk:
                stream.write(chunk)

        stream.stop_stream()
        stream.close()
        p.terminate()
        logger.info("TTS complete.")

    except Exception as exc:
        logger.error("ElevenLabs TTS failed: %s", exc)
