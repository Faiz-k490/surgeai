# Development Log & Integration Guide

## Current State: Loop B (Audio/Q&A Pipeline)
The backend is currently running **Loop B**, which handles real-time surgical Q&A:
1. Listens for the wake word (`Hey Surgeon`).
2. Captures the resident's medical question.
3. Retrieves relevant surgical protocols via **Snowflake Cortex Search RAG**.
4. Generates a clinical answer via **Groq (Llama 3.3 70B)**.
5. Synthesizes and plays the answer via **ElevenLabs TTS** directly through system speakers.
6. Broadcasts the Q&A exchange to the React frontend via WebSocket (`ws://localhost:5000/ws/training`).
7. Logs the session to **MongoDB Atlas**.

## Future State: Integrating Loop A (Video/CV Pipeline)

Loop A will run concurrently to track surgical tools and workflow steps via the camera feed. Here is how Loop A should integrate with the existing Loop B infrastructure:

### 1. State Sharing via MongoDB
Loop A will continuously log the current surgical step (e.g., "Step 3: Cystic Duct Dissection") and visible tools to MongoDB. 
**Integration point:** Modify `intelligence_pipeline.py` to fetch the *latest* Loop A state from MongoDB right before querying Snowflake. This allows the LLM to have context about exactly what the resident is currently looking at or doing.

### 2. Unified WebSocket Broadcasts
All frontend communication flows through the existing `ConnectionManager` in `main.py`.
**Integration point:** Loop A should trigger a new FastAPI background task or inject events into the event loop to broadcast `cv_update` events (e.g., bounding boxes, tool names) over the same `/ws/training` socket.

### 3. Hardware Concurrency
Both loops will run in the same FastAPI Python process but demand different hardware:
- Loop A: GPU-heavy (YOLO/CV models), blocking inference.
- Loop B: I/O-bound (async API calls), thread-executor audio blocking.
**Integration point:** Loop A inference **must** be run in a separate `ProcessPoolExecutor` or dedicated child process so the Global Interpreter Lock (GIL) does not cause audio stuttering or WebSocket timeouts in Loop B.

### Next Steps for Implementation
1. Add a `loop_a.py` module to handle OpenCV camera capture (`BRIO_CAMERA_INDEX`) and model inference.
2. Wire `loop_a.py` into the `lifespan` context manager in `main.py` using `asyncio.to_thread` or a `ProcessPoolExecutor`.
3. Update the `SYSTEM_PROMPT` in `intelligence_pipeline.py` to dynamically include the latest CV state.
