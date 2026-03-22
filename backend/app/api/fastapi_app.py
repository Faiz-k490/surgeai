"""
fastapi_app.py — FastAPI + WebSocket server for Loop B (voice Q&A).

Streaming pipeline:
  1. Audio pipeline detects wake word, transcribes question via Groq Whisper.
  2. Snowflake RAG runs in a thread (asyncio.to_thread) — never blocks event loop.
  3. Groq LLM streams tokens via stream_answer_tokens() async generator.
  4. Tokens are teed to two concurrent consumers:
       a. ElevenLabs WebSocket TTS (stream_tts) — audio begins ~150 ms after
          first token, without waiting for the full LLM response.
       b. FastAPI WebSocket broadcast — frontend receives tokens in real time
          for live text rendering on the HUD.
  5. On question completion: full answer is broadcast + logged to MongoDB.

Abort signal:
  Frontend sends {"event": "abort"} over the WebSocket to immediately stop
  both the Groq stream and ElevenLabs audio synthesis.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

_BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_BACKEND_ENV)
load_dotenv()

from audio_pipeline import start_listening
from intelligence_pipeline import retrieve_context, stream_answer_tokens
from tts_pipeline import stream_tts
from session_logger import log_qa

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("surgeai")

# ── Abort signal ─────────────────────────────────────────────────────────────

# One event per active synthesis. Reset at the start of each question.
# The WebSocket handler sets this when the frontend sends {"event": "abort"}.
_current_abort: Optional[asyncio.Event] = None


# ── Lifespan ─────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("Starting audio pipeline …")
    task = asyncio.create_task(start_listening(on_question_captured))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="SurgeAI",
    description="Real-time surgical training assistant — Loop B voice Q&A pipeline",
    version="0.2.0",
    lifespan=lifespan,
)


# ── WebSocket connection manager ─────────────────────────────────────────────


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self.active_connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


# ── Core pipeline callback ────────────────────────────────────────────────────


async def on_question_captured(question_text: str) -> None:
    """
    Full Loop B callback — invoked by the audio pipeline after wake-word + transcription.

    Streaming flow
    ──────────────
                      ┌─ tts_queue ─► stream_tts() ─► ElevenLabs WS ─► PyAudio
    stream_answer_tokens()
                      └─ broadcast  ─► WebSocket ─► React HUD (live tokens)

    The Groq stream and the ElevenLabs WebSocket run concurrently via
    asyncio.gather. Audio begins playing within ~150 ms of the first Groq token,
    without waiting for the complete LLM response.
    """
    global _current_abort

    # Fresh abort event for this question — clears any stale signal from previous
    _current_abort = asyncio.Event()
    abort = _current_abort

    logger.info("Question captured: %s", question_text)

    # Immediately tell the frontend we heard something — no waiting for RAG/LLM
    await manager.broadcast({
        "event": "question_received",
        "payload": {"question": question_text},
    })

    # ── RAG retrieval — offloaded to thread, never blocks event loop ──
    try:
        context_chunks = await asyncio.to_thread(retrieve_context, question_text)
    except Exception as exc:
        logger.error("Snowflake retrieval error: %s", exc)
        context_chunks = []

    if abort.is_set():
        logger.info("Abort before LLM generation — skipping")
        return

    # ── Token tee: Groq → ElevenLabs TTS  +  Groq → WebSocket broadcast ──

    # Thread-safe queue bridges the Groq stream thread to the TTS consumer
    tts_queue: asyncio.Queue[str | None] = asyncio.Queue()
    accumulated: list[str] = []

    async def _token_source() -> None:
        """
        Consume Groq tokens and simultaneously:
          1. Enqueue them for TTS (tts_queue)
          2. Accumulate them for final broadcast
          3. Push each token to the frontend WebSocket for live HUD rendering
        """
        try:
            async for token in stream_answer_tokens(question_text, context_chunks, abort):
                accumulated.append(token)
                await tts_queue.put(token)
                # Real-time token streaming to the HUD
                await manager.broadcast({
                    "event": "answer_token",
                    "payload": {"token": token},
                })
        finally:
            await tts_queue.put(None)  # sentinel — signals TTS that stream is done

    async def _tts_sink() -> None:
        """
        Consume from tts_queue and pipe into ElevenLabs WebSocket TTS.
        Audio playback starts ~100–150 ms after ElevenLabs receives the first
        50 characters — well before Groq finishes generating the answer.
        """
        async def _tts_tokens():
            while True:
                token = await tts_queue.get()
                if token is None:
                    return
                yield token

        await stream_tts(_tts_tokens(), abort)

    # Run token production and TTS consumption concurrently.
    # return_exceptions=True ensures one failure does not cancel the other.
    await asyncio.gather(_token_source(), _tts_sink(), return_exceptions=True)

    answer = "".join(accumulated)

    if not answer:
        logger.warning("Empty answer — pipeline may have been aborted or failed")

    # ── Final broadcast with complete answer ──
    await manager.broadcast({
        "event": "qa_update",
        "payload": {
            "question": question_text,
            "answer": answer,
            "aborted": abort.is_set(),
        },
    })

    # ── MongoDB log — fire-and-forget, never blocks the callback ──
    if answer:
        asyncio.create_task(log_qa(question_text, answer))


# ── HTTP endpoints ────────────────────────────────────────────────────────────


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# ── WebSocket endpoint ────────────────────────────────────────────────────────


@app.websocket("/ws/training")
async def training_ws(websocket: WebSocket):
    """
    Full-duplex WebSocket for the training session.

    Outbound events (server → client):
      question_received  {"question": str}           — question heard, RAG starting
      answer_token       {"token": str}               — live token stream for HUD
      qa_update          {"question", "answer", "aborted"} — complete answer

    Inbound events (client → server):
      {"event": "abort"}   — immediately stop current synthesis
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("event") == "abort":
                if _current_abort is not None and not _current_abort.is_set():
                    _current_abort.set()
                    logger.info("Abort signal received from frontend")
                    await websocket.send_json({"event": "aborted"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ── Dev entrypoint ────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.api.fastapi_app:app",
        host="0.0.0.0",
        port=5000,
        reload=False,  # reload=True causes executor shutdown on hot-reload
    )
