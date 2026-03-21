# SurgeonAI Backend Quick Start (Windows)

This backend currently targets Python `3.11` for reliable dependency compatibility.

**Full stack (Loop A + Loop B + HUD + VLM):** see [`../docs/RUN_FULL_STACK.md`](../docs/RUN_FULL_STACK.md).

## 1) Create and activate virtual environment

```powershell
py -3.11 -m venv .venv311
.\.venv311\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 2) Configure environment keys

```powershell
copy .env.example .env
```

Open `.env` and fill all `replace_me` values:
- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `ELEVENLABS_API_KEY`
- `SNOWFLAKE_*`
- `MONGODB_URI`

Frontend integration config:
- `FRONTEND_ORIGIN` (default `http://localhost:5173`)
- `SOCKET_NAMESPACE` (default `/realtime`)
- `PORT` (default `5000` — must match `VITE_API_BASE` in `surgeon-hud/.env`)
- `GEMINI_MODEL`, `VLM_MAX_HZ`, `CAPTURE_TARGET_FPS`, `LOOP_B_ENABLED` (see runbook)

## 3) Run backend

From the repo root:

```powershell
.\.venv311\Scripts\python -m backend.app.main
```

## Logging

Backend writes **`../logging/logs/surgeai-backend.log`** and prints colored lines to the terminal. Set **`LOG_LEVEL`** in `.env`. See **`../logging/README.md`**.

## 4) Smoke-check endpoints

(Default `PORT` is **5000** — match `surgeon-hud` `VITE_API_BASE`.)

- Health: `http://localhost:5000/health`
- Session state: `http://localhost:5000/session/state`
- Video stream: `http://localhost:5000/video`

## 5) Frontend teammate integration

- Socket namespace: `/realtime`
- Events:
  - `step_update`
  - `warning`
  - `clear`
  - `system_health`
  - `qa_update` (reserved for Loop B teammate)
- Full integration details: `backend/docs/frontend-integration.md`

## Notes

- Python `3.14+` is blocked in code because `snowflake-connector-python` setup is not reliable there in this project.
- If Cursor still shows unresolved imports, ensure Cursor interpreter is set to `.venv311\Scripts\python.exe`.
