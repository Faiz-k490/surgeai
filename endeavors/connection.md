# Connection Guide (Teammate Agents)

This is the handoff contract for teammates integrating against your Loop A backend during hackathon crunch.

## Backend Owner Status

- Loop A backend is live-ready with:
  - `/health`
  - `/session/state`
  - `/video` (MJPEG)
  - Socket.IO realtime events
- Snowflake grounding table is seeded:
  - `SURGICAL_PROTOCOLS`
- Mongo event logging is enabled.

## Start Backend (Owner)

From repo root:

```powershell
.\.venv311\Scripts\python -m backend.app.main
```

If module path fails in your shell context, run from `backend/`:

```powershell
..\ .venv311\Scripts\python -m app.main
```

Use without the space if copied manually:

```powershell
..\.venv311\Scripts\python -m app.main
```

## Frontend Teammate Agent Contract

### Base URL
- `http://localhost:5000`

### Read model/state
- `GET /health`
- `GET /session/state`

### Video layer
- `GET /video`
- Render as full-screen image background.

### Realtime stream
- Socket namespace: `/realtime`
- Subscribe to:
  - `step_update`
  - `warning`
  - `clear`
  - `system_health`
  - `qa_update` (will be emitted by Loop B teammate)

### Event envelope format
- Every event payload wrapper:
  - `{ eventVersion, timestamp, type, payload }`

## Loop B Teammate Agent Contract

- Reuse existing socket namespace `/realtime`.
- Emit `qa_update` with shared event envelope.
- Keep payload shape:
  - `{ question, answer }`
- Read current step context from `/session/state` before answering.

## Frontend Smoke Checklist

1. Open backend health endpoint and confirm `ok: true`.
2. Open video stream endpoint and confirm live camera feed appears.
3. Confirm `step_update` and `warning` render in HUD without mock data.
4. Confirm banner returns to nominal after `clear`.

## Loop A Verification Commands

From repo root:

```powershell
python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=5).read().decode())"
```

Mongo check:

```powershell
.\.venv311\Scripts\python backend\scripts\mongodb_ping.py
```

Snowflake protocol seed (re-runnable):

```powershell
.\.venv311\Scripts\python backend\scripts\seed_surgical_protocols.py
```

## Expected Demo Behavior

- Red near incision zone without blue tool -> warning.
- Blue tool near zone -> step progresses and warning clears.
- Green tool in step 3 -> closure step progression.
- Guidance speaks every cycle (ElevenLabs path with fallback).
