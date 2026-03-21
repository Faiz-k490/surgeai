"""
audio_pipeline.py — Always-on, non-blocking audio listener for SurgeAI.

Continuously listens to the microphone, detects the wake word "Hey Surgeon",
then captures the resident's follow-up question and forwards it through a
callback so the FastAPI layer can push it over the WebSocket.
"""

import asyncio
import os
import logging
import time
from collections.abc import Coroutine
from typing import Any, Callable

import speech_recognition as sr

logger = logging.getLogger("surgeai.audio")

WAKE_PHRASE = "hey surgeon"


def _build_recognizer_and_mic() -> tuple[sr.Recognizer, sr.Microphone]:
    """Create a Recognizer and bind it to the configured mic device index."""
    mic_index_raw = os.getenv("BRIO_MIC_INDEX")
    mic_index = int(mic_index_raw) if mic_index_raw is not None else None

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True

    mic = sr.Microphone(device_index=mic_index)

    # Calibrate for ambient noise once at startup
    with mic as source:
        logger.info("Calibrating for ambient noise …")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        logger.info("Calibration complete.")

    return recognizer, mic


def _listen_for_wake_word(recognizer: sr.Recognizer, mic: sr.Microphone) -> bool:
    """
    Block until audio is captured, then check for the wake phrase.
    Returns True when 'Hey Surgeon' is detected, False otherwise.
    """
    with mic as source:
        logger.debug("Listening for wake word …")
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=4)
        except sr.WaitTimeoutError:
            return False

    try:
        transcript = recognizer.recognize_google(audio).lower()
        logger.debug("Heard: %s", transcript)
        if WAKE_PHRASE in transcript:
            logger.info("Wake word detected!")
            return True
    except sr.UnknownValueError:
        pass  # Unintelligible — keep listening
    except sr.RequestError as exc:
        logger.warning("Speech-to-text API error: %s", exc)

    return False


def _capture_question(recognizer: sr.Recognizer, mic: sr.Microphone) -> str | None:
    """
    After the wake word fires, capture the resident's actual question.
    Returns the transcript string, or None on failure.
    """
    with mic as source:
        logger.info("Listening for question …")
        try:
            audio = recognizer.listen(source, timeout=8, phrase_time_limit=15)
        except sr.WaitTimeoutError:
            logger.warning("Timed out waiting for question.")
            return None

    try:
        question = recognizer.recognize_google(audio)
        logger.info("Captured question: %s", question)
        return question
    except sr.UnknownValueError:
        logger.warning("Could not understand the question audio.")
    except sr.RequestError as exc:
        logger.warning("Speech-to-text API error during question capture: %s", exc)

    return None


def _blocking_listen_loop(on_question: Callable[[str], None]) -> None:
    """
    Synchronous loop that runs inside a thread executor.
    1. Waits for the 'Hey Surgeon' wake word.
    2. Captures the follow-up question.
    3. Calls `on_question(text)` with the result.
    4. Repeats indefinitely.

    If the microphone cannot be initialised the loop retries every 5 s
    so the FastAPI server is never blocked.
    """
    while True:
        try:
            recognizer, mic = _build_recognizer_and_mic()
            break
        except Exception as exc:
            logger.error(
                "Mic init failed (%s) — retrying in 5 s …", exc
            )
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


async def start_listening(
    on_question: Callable[[str], Coroutine[Any, Any, None]],
) -> None:
    """
    Launch the blocking listen loop on a background thread so it never
    blocks the asyncio event loop (and therefore the FastAPI WebSocket).

    Parameters
    ----------
    on_question :
        An *async* callback invoked with the captured question text.
        The callback is scheduled back onto the event loop automatically.
    """
    loop = asyncio.get_running_loop()

    def _sync_bridge(text: str) -> None:
        """Bridge from the sync thread back to the async world."""
        asyncio.run_coroutine_threadsafe(on_question(text), loop)

    await loop.run_in_executor(
        None,  # default ThreadPoolExecutor
        lambda: _blocking_listen_loop(_sync_bridge),
    )
