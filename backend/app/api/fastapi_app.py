"""
Experimental FastAPI + WebSocket server for Loop B (voice Q&A).

Production stack uses Flask + Socket.IO via `python -m backend.app.main`.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

_BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_BACKEND_ENV)
load_dotenv()

from audio_pipeline import start_listening
from intelligence_pipeline import run_pipeline
from tts_pipeline import speak
from session_logger import log_qa

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("surgeai")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Start the audio listener as a background task on application startup."""
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
    version="0.1.0",
    lifespan=lifespan,
)


class ConnectionManager:
    """Manages active WebSocket connections for the training session."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_json(self, websocket: WebSocket, data: dict):
        await websocket.send_json(data)

    async def broadcast(self, data: dict):
        for connection in self.active_connections:
            await connection.send_json(data)


manager = ConnectionManager()


async def on_question_captured(question_text: str) -> None:
    """
    Full Loop B callback — triggered by the audio pipeline once a question
    is captured after wake-word detection.

    1. Runs the RAG + LLM intelligence pipeline.
    2. Broadcasts a qa_update event (question + answer) over the WebSocket.
    3. Speaks the answer aloud via ElevenLabs (in a background thread).
    4. Logs the Q&A exchange to MongoDB (non-blocking).
    """
    logger.info("Question captured: %s", question_text)

    result = await run_pipeline(question_text)

    if result.error:
        logger.error("Pipeline error: %s", result.error)
        await manager.broadcast(
            {
                "event": "qa_update",
                "payload": {
                    "question": question_text,
                    "answer": "",
                    "error": result.error,
                },
            }
        )
        return

    await manager.broadcast(
        {
            "event": "qa_update",
            "payload": {
                "question": result.question,
                "answer": result.answer,
            },
        }
    )

    loop = asyncio.get_running_loop()
    tts_future = loop.run_in_executor(None, speak, result.answer)
    log_future = log_qa(result.question, result.answer)

    await asyncio.gather(tts_future, log_future, return_exceptions=True)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.websocket("/ws/training")
async def training_ws(websocket: WebSocket):
    """
    Full-duplex WebSocket for the training session.
    Sends 'qa_update' events to the React frontend.
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.send_json(
                websocket,
                {"event": "qa_update", "payload": data},
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.api.fastapi_app:app", host="0.0.0.0", port=5000, reload=True)
