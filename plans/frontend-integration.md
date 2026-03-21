# Frontend Integration Guide (Loop A Backend)

This document is for the frontend teammate to integrate the HUD without mock data.

## Base URL

- `http://localhost:5000`
- Socket namespace: `/realtime` (configurable via `SOCKET_NAMESPACE`)

## HTTP Endpoints

- `GET /health`
  - Purpose: backend/dependency readiness
  - Example response:
    - `{ "ok": true, "dependencies": { "camera": true, "gemini": true, "snowflake": true, "groq": true, "elevenlabs": true, "mongo": true } }`
- `GET /session/state`
  - Purpose: initial HUD state hydration
  - Example response:
    - `{ "ok": true, "state": { "current_step": 1, "current_step_name": "Identify zone", "current_warning": null, "last_guidance": "", "last_scene_summary": "", "loop_a_alive": true, "last_updated": "..." } }`
- `GET /video`
  - Purpose: MJPEG background feed
  - Frontend usage: `<img src="http://localhost:5000/video" />`

## Socket.IO Events

Each event includes the envelope:
- `{ eventVersion, timestamp, type, payload }`

### `step_update`
- payload: `{ stepNumber, stepName, confidence }`

### `warning`
- payload: `{ severity, message, currentStep }`

### `clear`
- payload: `{ status: "nominal" }`

### `system_health`
- payload: `{ loopAAlive, fps, apiLatencyMs, degraded }`

### `qa_update`
- Reserved for Loop B teammate voice integration.

## CORS

- Allow origin from env `FRONTEND_ORIGIN` (default: `http://localhost:5173`).

## Frontend Boot Flow

1. Fetch `GET /session/state`.
2. Open Socket.IO connection to `/realtime`.
3. Bind event listeners for `step_update`, `warning`, `clear`, `system_health`.
4. Render MJPEG stream from `/video` as full-screen background layer.
