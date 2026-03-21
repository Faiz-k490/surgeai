# SurgeonAI Backend Quick Start (Windows)

This backend currently targets Python `3.11` for reliable dependency compatibility.

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
- `PORT` (default `5000`)

## 3) Run backend

From the repo root:

```powershell
.\.venv311\Scripts\python -m backend.app.main
```

## 4) Smoke-check endpoints

- Health: [http://localhost:5000/health](http://localhost:5000/health)
- Session state: [http://localhost:5000/session/state](http://localhost:5000/session/state)
- Video stream: [http://localhost:5000/video](http://localhost:5000/video)

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
