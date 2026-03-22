"""
audio_pipeline.py — Always-on, non-blocking audio listener for SurgeAI.

Wake-word detection uses a two-stage local filter:
  Stage 1: RMS energy gate (audioop) — rejects silence without any network call.
  Stage 2: Google Web Speech — free, local-ish, no API quota used for idle listening.

Question transcription uses Groq Whisper Turbo for accuracy on medical terminology.
The Google fallback is used only if Groq Whisper fails.

The blocking mic loop runs in a ThreadPoolExecutor so the asyncio event loop
(and all WebSocket connections) are never blocked.
"""

import asyncio
import audioop
import io
import logging
import os
import time
from collections.abc import Coroutine
from functools import lru_cache
from typing import Any, Callable

import speech_recognition as sr
from groq import Groq

logger = logging.getLogger("surgeai.audio")

WAKE_PHRASE = "hey surgeon"

# RMS threshold below which audio is treated as silence.
# Tune this if you get too many false-negatives in a noisy OR.
WAKE_ENERGY_THRESHOLD = 400


# ── Singleton Groq client ────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _get_groq_client() -> Groq:
    """One Groq HTTP connection per process — reused for every transcription."""
    return Groq(api_key=os.environ.get("GROQ_API_KEY"))


# ── Microphone setup ─────────────────────────────────────────────────────────


def _build_recognizer_and_mic() -> tuple[sr.Recognizer, sr.Microphone]:
    mic_index_raw = os.getenv("BRIO_MIC_INDEX")
    mic_index = int(mic_index_raw) if mic_index_raw is not None else None

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True

    mic = sr.Microphone(device_index=mic_index)
    with mic as source:
        logger.info("Calibrating for ambient noise …")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        logger.info("Calibration complete.")

    return recognizer, mic


# ── Transcription ─────────────────────────────────────────────────────────────


def _transcribe_with_groq(audio: sr.AudioData) -> str:
    """
    Transcribe audio using Groq Whisper Turbo.

    Groq Whisper is significantly more accurate than Google Web Speech for
    medical terminology ('suture', 'anastomosis', 'hemostasis', etc.) and
    runs at ~150 ms RTT on Groq's infrastructure.

    Used only for the actual question — not for wake-word detection.
    """
    wav_data = audio.get_wav_data()
    wav_file = io.BytesIO(wav_data)
    wav_file.name = "audio.wav"  # Groq requires a filename hint
    transcription = _get_groq_client().audio.transcriptions.create(
        file=wav_file,
        model="whisper-large-v3-turbo",
        response_format="text",
    )
    return transcription.strip()


# ── Wake word detection ───────────────────────────────────────────────────────


def _listen_for_wake_word(recognizer: sr.Recognizer, mic: sr.Microphone) -> bool:
    """
    Two-stage local filter for wake-word detection.

    Stage 1 — energy gate:
      audioop.rms() on the raw frames.  If RMS < threshold, it's silence or
      background noise.  Return False immediately — zero network calls.

    Stage 2 — Google Web Speech:
      Free, no API key, no quota.  Used exclusively for wake-word string matching.
      Groq Whisper is NOT used here; it would consume API credits on every 3-second
      audio chunk (~20 calls/minute during idle listening = 1,200/hour).
    """
    with mic as source:
        try:
            audio = recognizer.listen(source, timeout=3, phrase_time_limit=3)
        except sr.WaitTimeoutError:
            return False

    # Stage 1: energy gate
    rms = audioop.rms(audio.get_raw_data(), audio.sample_width)
    if rms < WAKE_ENERGY_THRESHOLD:
        logger.debug("Energy gate: RMS=%d below threshold — skipping", rms)
        return False

    # Stage 2: free local transcription
    try:
        transcript = recognizer.recognize_google(audio).lower()
        logger.debug("Wake-word transcript: %s", transcript)
        if WAKE_PHRASE in transcript:
            logger.info("Wake word detected!")
            return True
    except sr.UnknownValueError:
        pass
    except sr.RequestError as exc:
        logger.warning("Google Speech API error: %s", exc)

    return False


# ── Question capture ──────────────────────────────────────────────────────────


def _capture_question(recognizer: sr.Recognizer, mic: sr.Microphone) -> str | None:
    """
    Capture the resident's question after wake-word detection.

    Transcription: Groq Whisper Turbo (primary) → Google Web Speech (fallback).
    Groq Whisper is used here because question accuracy is critical — medical
    terms like 'hepatic artery' or 'cholecystectomy' must not be misheard.
    """
    with mic as source:
        logger.info("Listening for question …")
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
        except sr.WaitTimeoutError:
            logger.warning("Timed out waiting for question.")
            return None

    # Primary: Groq Whisper Turbo — accurate on medical terminology
    try:
        question = _transcribe_with_groq(audio)
        if question:
            logger.info("Captured question (Groq Whisper): %s", question)
            return question
    except Exception as exc:
        logger.warning("Groq Whisper failed (%s) — falling back to Google", exc)

    # Fallback: Google Web Speech
    try:
        question = recognizer.recognize_google(audio)
        if question:
            logger.info("Captured question (Google fallback): %s", question)
            return question
    except (sr.UnknownValueError, sr.RequestError) as exc:
        logger.warning("Google fallback failed: %s", exc)

    return None


# ── Blocking listen loop ──────────────────────────────────────────────────────


def _blocking_listen_loop(on_question: Callable[[str], None]) -> None:
    """
    Runs in a ThreadPoolExecutor — never touches the asyncio event loop.
    Retries mic initialisation on failure so the server never crashes.
    """
    while True:
        try:
            recognizer, mic = _build_recognizer_and_mic()
            break
        except Exception as exc:
            logger.error("Mic init failed (%s) — retrying in 5 s …", exc)
            time.sleep(5)

    logger.info("Audio pipeline started — say 'Hey Surgeon' to begin.")

    while True:
        try:
            if _listen_for_wake_word(recognizer, mic):
                question = _capture_question(recognizer, mic)
                if question:
                    on_question(question)
        except Exception as exc:
            logger.error("Audio loop error: %s — continuing …", exc)
            time.sleep(1)


# ── Async entry point ─────────────────────────────────────────────────────────


async def start_listening(
    on_question: Callable[[str], Coroutine[Any, Any, None]],
) -> None:
    """
    Launch the blocking listen loop on a background thread.

    The _sync_bridge closure safely schedules the async on_question callback
    back onto the running event loop from the worker thread.
    """
    loop = asyncio.get_running_loop()

    def _sync_bridge(text: str) -> None:
        asyncio.run_coroutine_threadsafe(on_question(text), loop)

    await loop.run_in_executor(
        None,
        lambda: _blocking_listen_loop(_sync_bridge),
    )
