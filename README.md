# SurgeAI

Real-time surgical training assistant: **Loop A** (camera + Gemini VLM + guidance) and **Loop B** (wake-word voice Q&A with RAG + Groq), plus a **React HUD** for demos.

## Repository layout

| Path | Purpose |
|------|---------|
| [`backend/`](backend/) | Python backend (Flask + Socket.IO), VLM, integrations |
| [`surgeon-hud/`](surgeon-hud/) | Vite + React HUD (video, Socket.IO, Q&A panel) |
| [`docs/`](docs/) | Runbooks and architecture |

## Tech stack

- **Backend:** Python 3.11+, Flask, Flask-SocketIO, OpenCV, Google GenAI (Gemini), Groq, Snowflake, MongoDB, ElevenLabs + PyAudio
- **Loop B:** SpeechRecognition (Google STT), optional FastAPI + WebSocket experiment ([`backend/app/api/fastapi_app.py`](backend/app/api/fastapi_app.py))
- **Frontend:** React, Vite, Socket.IO client

## Quick start (production path)

1. Create a venv and install dependencies:

   ```powershell
   cd surgeai
   python -m venv .venv311
   .\.venv311\Scripts\Activate.ps1
   pip install -r backend\requirements.txt
   ```

2. Configure environment:

   ```powershell
   copy backend\.env.example backend\.env
   ```

   Edit `backend/.env` with your keys (see table in [`docs/RUN_FULL_STACK.md`](docs/RUN_FULL_STACK.md)).

3. Run the unified backend **from the repo root**:

   ```powershell
   python -m backend.app.main
   ```

4. (Optional) Run the HUD (use `;` in **Windows PowerShell 5.x**, not `&&`):

   ```powershell
   copy surgeon-hud\.env.example surgeon-hud\.env
   ```

   Edit `surgeon-hud/.env`: **`VITE_API_BASE`** must match **`PORT`** in `backend/.env` (e.g. `http://localhost:5000`), and **`VITE_SOCKET_NAMESPACE`** must match **`SOCKET_NAMESPACE`** (default `/realtime`). Mismatch causes `ERR_CONNECTION_REFUSED` or Socket.IO `400` / stuck HUD.

   ```powershell
   cd surgeon-hud; npm install; npm run dev
   ```

5. Stop all dev servers (backend + Vite on common ports):

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\stop-dev.ps1
   ```

## Logging (backend + HUD + scripts)

- **Files:** `logging/logs/surgeai-backend.log` (rotating) — see [`logging/README.md`](logging/README.md).
- **Backend terminal:** colored levels (green INFO, red ERROR) via `colorlog`; configure **`LOG_LEVEL`** in `backend/.env`.
- **HUD:** open browser **DevTools → Console** — messages use green/red via `surgeon-hud/src/lib/logger.js`.
- **Scripts:** [`scripts/_log-colors.ps1`](scripts/_log-colors.ps1) — `Write-SurgeLogGood` / `Write-SurgeLogBad` (used by `stop-dev.ps1`).
- **Tail backend log:** `powershell -ExecutionPolicy Bypass -File scripts\tail-backend-log.ps1`
- **HUD with log file:** `powershell -ExecutionPolicy Bypass -File scripts\dev-hud.ps1` (also writes `logging/logs/hud-dev.log`).

## Documentation

- **[Full stack + VLM / glasses testing](docs/RUN_FULL_STACK.md)** — ports, env vars, HUD, **VLM-only** mode
- **[Gemini VLM — free tier & models](docs/GEMINI_VLM.md)** — `GEMINI_MODEL`, throttling, quotas
- **[Architecture](docs/ARCHITECTURE.md)** — layers, entrypoints, data flow
- **[Backend README](backend/README.md)** — Windows-focused notes

## Entrypoints

| Command | Description |
|---------|-------------|
| `python -m backend.app.main` | **Main** — Flask + Socket.IO + Loop A + Loop B |
| `python merged_backend.py` | Demo server (simulated Loop A + Loop B) |
| `python main.py` | FastAPI + WebSocket Loop B experiment (port 5000) |

Root files `audio_pipeline.py`, `intelligence_pipeline.py`, `tts_pipeline.py`, `session_logger.py` are **thin shims**; canonical code lives under [`backend/app/loop_b/`](backend/app/loop_b/).

**TTS:** Loop A and Loop B use **ElevenLabs + PyAudio** only ([`backend/app/audio/tts.py`](backend/app/audio/tts.py) delegates to [`backend/app/loop_b/tts_pipeline.py`](backend/app/loop_b/tts_pipeline.py)). Set **`ELEVENLABS_API_KEY`** and install **`pyaudio`**.

### Google Gemini “rate limit” / “set up billing”

There is **no legitimate bypass**: free tiers have low daily caps. Options:

1. **Google AI Studio** (aistudio.google.com) → your API key → **Billing** / upgrade plan so the key can use paid quota.
2. **Defaults are conservative** (`VLM_MAX_HZ=0.2`, `GEMINI_MODEL=gemini-2.5-flash`). Raise `VLM_MAX_HZ` only if you need faster VLM (uses more quota).
3. **`GEMINI_MODEL`**: default **`gemini-2.5-flash`** — confirm in [Gemini API models](https://ai.google.dev/gemini-api/docs/models).

The backend **falls back** to color-based heuristics when Gemini errors (including 429), so the HUD can still run with degraded “VLM” — check backend logs for `Gemini rate limit`.

**Groq 429:** reduce guidance frequency (`GUIDANCE_MIN_INTERVAL_SECONDS`, `VLM_MAX_HZ`) or raise quota on the Groq dashboard.

**HUD Socket.IO “Invalid frame header” on WebSocket:** the client uses **long-polling only** (`SocketManager.jsx`) because Werkzeug’s dev server + Flask-SocketIO in threading mode often breaks WebSocket upgrades. Events still work in real time over polling.

**Chrome `A listener indicated an asynchronous response…`:** almost always a **browser extension** (password managers, ad blockers) mishandling `chrome.runtime` messages — not from this app. Reproduce in a **Guest** window or with extensions disabled.

**Socket.IO `400` on `/socket.io/...&sid=...`:** ensure **`SOCKET_NAMESPACE`** in `backend/.env` matches the HUD URL (default `/realtime`; server registers `connect` on that namespace). Keep **`VITE_API_BASE`** aligned with **`PORT`**. After a backend restart, refresh the HUD so polling doesn’t reuse a stale `sid`.

## Testing

```powershell
pip install -r backend/requirements-dev.txt
python -m pytest backend/tests/ -v
```

## License / team

See project docs and hackathon READMEs in `endeavors/` and `plans/` as applicable.
