"""
tts_pipeline.py — ElevenLabs WebSocket streaming TTS for SurgeAI.

Architecture:
  stream_tts(text_tokens, abort_event) accepts an AsyncIterator[str] of Groq
  text tokens and pipes them directly into the ElevenLabs stream-input
  WebSocket endpoint. Audio playback begins ~100–150 ms after the first token
  is received — without waiting for the full LLM response.

  Key configuration:
    model_id = eleven_flash_v2_5   — lowest latency ElevenLabs model
    auto_mode = true               — ElevenLabs-side latency optimisation
    chunk_length_schedule = [50]   — start generating audio after 50 chars
    output_format = pcm_16000      — raw PCM, no decoder needed

  Fallback: if ELEVENLABS_API_KEY is absent, pyttsx3 (offline) is used.
  The pyttsx3 path cannot stream — it collects all tokens first, then speaks.
"""

import asyncio
import base64
import json
import logging
import os
from functools import lru_cache
from typing import AsyncIterator

import pyaudio
import websockets
import websockets.exceptions

logger = logging.getLogger("surgeai.tts")

# ── Constants ────────────────────────────────────────────────────────────────

_DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel — calm, clinical
_MODEL_ID = "eleven_flash_v2_5"
_SAMPLE_RATE = 16000
_WS_OPEN_TIMEOUT = 5  # seconds before giving up on WS connection


# ── Singleton audio devices ──────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _get_pyaudio() -> pyaudio.PyAudio:
    """
    One PyAudio instance per process.
    pyaudio.PyAudio() enumerates every audio device on init (~50–200 ms).
    Caching eliminates this cost on every speak() call.
    """
    return pyaudio.PyAudio()


@lru_cache(maxsize=1)
def _get_pyttsx3_engine():
    import pyttsx3
    engine = pyttsx3.init()
    engine.setProperty("rate", 175)
    return engine


# ── pyttsx3 fallback (blocking, no streaming) ────────────────────────────────


def _speak_pyttsx3_blocking(text: str) -> None:
    engine = _get_pyttsx3_engine()
    engine.say(text)
    engine.runAndWait()


# ── ElevenLabs WebSocket streaming TTS ──────────────────────────────────────


async def stream_tts(
    text_tokens: AsyncIterator[str],
    abort_event: asyncio.Event,
) -> None:
    """
    Pipe an async stream of text tokens into ElevenLabs' stream-input WebSocket
    and play PCM audio as chunks arrive.

    The concurrent producer/consumer pattern means:
      1. _send_text  — forwards tokens to ElevenLabs as they arrive from Groq.
      2. _play_audio — plays PCM audio as ElevenLabs generates it.

    Both run via asyncio.gather, so audio playback can begin before all text
    tokens have even been produced.

    Falls back to blocking pyttsx3 if ELEVENLABS_API_KEY is not set.
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY")

    if not api_key:
        logger.warning("ELEVENLABS_API_KEY absent — using pyttsx3 fallback (non-streaming)")
        collected: list[str] = []
        async for token in text_tokens:
            collected.append(token)
        text = "".join(collected)
        if text:
            await asyncio.to_thread(_speak_pyttsx3_blocking, text)
        return

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", _DEFAULT_VOICE_ID)

    # auto_mode=true: ElevenLabs-side optimisation for real-time conversational use
    # chunk_length_schedule: start generating audio after only 50 chars
    uri = (
        f"wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input"
        f"?model_id={_MODEL_ID}"
        f"&output_format=pcm_{_SAMPLE_RATE}"
        f"&auto_mode=true"
        f"&xi-api-key={api_key}"
    )

    p = _get_pyaudio()
    audio_stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=_SAMPLE_RATE,
        output=True,
    )

    try:
        async with websockets.connect(uri, open_timeout=_WS_OPEN_TIMEOUT) as ws:
            logger.info("ElevenLabs WS stream-input connected")

            # BOS — voice settings and buffering config
            await ws.send(json.dumps({
                "text": " ",
                "voice_settings": {
                    "stability": 0.4,
                    "similarity_boost": 0.8,
                    "use_speaker_boost": False,
                },
                "generation_config": {
                    # Start generating audio after just 50 characters.
                    # Lower = lower latency; too low = less natural prosody.
                    "chunk_length_schedule": [50, 100, 150, 200],
                },
                "xi_api_key": api_key,
            }))

            async def _send_text() -> None:
                """Forward incoming tokens to ElevenLabs as they arrive."""
                async for token in text_tokens:
                    if abort_event.is_set():
                        logger.info("Abort: halting text send to ElevenLabs")
                        return
                    await ws.send(json.dumps({"text": token}))
                # EOS — signals ElevenLabs to flush remaining audio
                await ws.send(json.dumps({"text": ""}))
                logger.debug("EOS sent to ElevenLabs")

            async def _play_audio() -> None:
                """Receive PCM chunks from ElevenLabs and play immediately."""
                first_chunk = True
                async for raw in ws:
                    if abort_event.is_set():
                        logger.info("Abort: halting audio playback")
                        return
                    msg = json.loads(raw)
                    # Debug print the message if it's not simply an audio chunk
                    if "audio" not in msg:
                        logger.warning("ElevenLabs WS returned: %s", msg)
                    
                    audio_b64 = msg.get("audio")
                    if audio_b64:
                        if first_chunk:
                            logger.info("First audio chunk received — playback starting")
                            first_chunk = False
                        audio_stream.write(base64.b64decode(audio_b64))
                    if msg.get("isFinal"):
                        logger.info("ElevenLabs stream complete (isFinal)")
                        return

            # Run producer and consumer concurrently.
            # Audio playback begins as soon as ElevenLabs returns the first chunk
            # (~100–150 ms after it receives enough text), even while Groq is
            # still generating the rest of the answer.
            await asyncio.gather(
                _send_text(),
                _play_audio(),
                return_exceptions=True,
            )

    except websockets.exceptions.ConnectionClosed as exc:
        logger.warning("ElevenLabs WS closed unexpectedly: %s", exc)
    except OSError as exc:
        logger.error("ElevenLabs WS connection failed: %s — falling back to pyttsx3", exc)
        # If WS fails after tokens were consumed we can't replay them;
        # log the failure and continue silently.
    except Exception as exc:
        logger.error("ElevenLabs WS TTS error: %s", exc)
    finally:
        audio_stream.stop_stream()
        audio_stream.close()


# ── Legacy synchronous wrapper ───────────────────────────────────────────────


def speak(text: str) -> None:
    """
    Blocking TTS wrapper used by synchronous threads.
    If ELEVENLABS_API_KEY is defined, it starts an ephemeral event loop to stream
    the WebSocket audio. Otherwise, falls back to local pyttsx3.
    """
    if not text:
        return

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except ImportError:
            pass
        _speak_pyttsx3_blocking(text)
        return

    async def _single_string_source() -> AsyncIterator[str]:
        yield text

    abort_event = asyncio.Event()
    try:
        asyncio.run(stream_tts(_single_string_source(), abort_event))
    except Exception as exc:
        logger.error("Failed to run ElevenLabs WS from blocking call (%s) — using pyttsx3", exc)
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except ImportError:
            pass
        _speak_pyttsx3_blocking(text)
