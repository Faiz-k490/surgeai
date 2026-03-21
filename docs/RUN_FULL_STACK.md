# SurgeAI — Run the full stack (Loop A + Loop B + HUD + VLM)

This guide runs **one unified backend** (`python -m backend.app.main`) that merges:

| Loop | What it does |
|------|----------------|
| **Loop A** | Webcam capture → throttled **Gemini VLM** → step tracker → Snowflake RAG + Groq guidance → TTS → MJPEG `/video` + Socket.IO (`step_update`, `warning`, `clear`, `system_health`, `vlm_update`) |
| **Loop B** | Mic → “**Hey Surgeon**” wake phrase → Google STT → Snowflake Cortex RAG + Groq answer → ElevenLabs (PyAudio) → Socket.IO `qa_update` → MongoDB log |

The **Surgeon HUD** (`surgeon-hud/`) connects to the same host/port as the backend (default **5000**).

Configuration is defined in [`backend/app/core/settings.py`](../backend/app/core/settings.py) and loaded from **`backend/.env`**.

---

## VLM / glasses webcam only (no voice Q&A)

Use this when your **Brio or glasses USB camera** is connected and you only want to validate **video + Gemini VLM** without mic / Loop B noise.

1. In **`backend/.env`** set:

   ```env
   LOOP_B_ENABLED=false
   ```

2. Set **`BRIO_CAMERA_INDEX`** to the OpenCV index for your glasses camera. On Windows, `0` is often the laptop camera; the USB headset/glasses may be `1` or `2`. If `/video` shows the wrong feed, increment the index until you see the glasses view.

3. Ensure **`GEMINI_API_KEY`** and **`GEMINI_MODEL`** are set.

4. From the **repo root**:

   ```powershell
   python -m backend.app.main
   ```

5. Open **`http://localhost:<PORT>/video`** (default port **5000**) — you should see the live MJPEG stream from the selected camera.

6. Check **`http://localhost:<PORT>/health`** — `dependencies` should show `gemini`, `camera`, etc. Loop B may show `false` when disabled; that is expected.

7. Optionally run **`surgeon-hud`** to see FPS/latency and overlays (`vlm_update`) on the HUD.

---

## 1. Prerequisites

- **Python 3.11** (3.13 also OK; avoid 3.14 — backend blocks it for Snowflake wheels).
- **Node.js 18+** for the HUD.
- **API keys / cloud**: Gemini, Groq, ElevenLabs, MongoDB Atlas, Snowflake (see `backend/.env.example`).
- **Hardware**: USB webcam / Brio on glasses mount + microphone (for Loop B). Adjust indices if you have multiple devices.

---

## 2. Backend environment

1. From the **repo root** (`surgeai/`):

   ```powershell
   python -m venv .venv311
   .\.venv311\Scripts\Activate.ps1
   pip install -r backend\requirements.txt
   ```

2. Copy **[`backend/.env.example`](../backend/.env.example)** to **`backend/.env`** and fill in values.

   | Variable | Purpose |
   |----------|---------|
   | `GEMINI_API_KEY` | Gemini VLM |
   | `GEMINI_MODEL` | e.g. `gemini-2.5-flash` |
   | `GROQ_API_KEY` | Loop A + Loop B LLM |
   | `ELEVENLABS_API_KEY` | TTS |
   | `MONGODB_URI` | Event + Q&A logging |
   | `SNOWFLAKE_*` | RAG (Loop A table + Loop B Cortex search) |
   | `BRIO_CAMERA_INDEX` | OpenCV camera index (glasses / Brio) |
   | `BRIO_MIC_INDEX` | Match Windows sound settings (Loop B) |
   | `FRONTEND_ORIGIN` | e.g. `http://localhost:5173` |
   | `PORT` | **`5001`** to match HUD defaults |

   Optional tuning:

   | Variable | Default | Meaning |
   |----------|---------|---------|
   | `CAPTURE_TARGET_FPS` | `30` | Camera encode rate |
   | `VLM_MAX_HZ` | `0.2` | Max Gemini vision calls per second (default ≈ 1/5s) |
   | `VLM_JPEG_QUALITY` | `65` | JPEG quality (lower = smaller upload) |
   | `GUIDANCE_MIN_INTERVAL_SECONDS` | `10` | Min time between Loop A TTS prompts |
   | `GEMINI_RATE_LIMIT_BACKOFF_SECONDS` | `120` | Pause vision calls after quota/rate errors |
   | `GEMINI_ERROR_BACKOFF_SECONDS` | `30` | Pause vision calls after other Gemini errors |
   | `LOOP_A_INTERVAL_SECONDS` | `0` | If `>0`, also enforces minimum seconds between VLM ticks (legacy) |
   | `LOOP_B_ENABLED` | `true` | Set `false` for VLM-only testing |

3. **Loop B** code lives in **[`backend/app/loop_b/`](../backend/app/loop_b/)** (canonical). Repo-root `audio_pipeline.py`, `intelligence_pipeline.py`, etc. are **thin shims** for backward compatibility.

4. Run the backend **from the repo root**:

   ```powershell
   cd c:\path\to\surgeai
   .\.venv311\Scripts\Activate.ps1
   python -m backend.app.main
   ```

   Flask-SocketIO listens on `0.0.0.0` and **`PORT`** (default 5000).

---

## 3. Surgeon HUD (React)

```powershell
cd surgeon-hud; npm install; npm run dev
```

Defaults in `SocketManager.jsx` and `VideoBackground.jsx` point to **`http://localhost:5001`**. If you change `PORT`, update:

- `surgeon-hud/src/providers/SocketManager.jsx` → `io('http://localhost:<PORT>/realtime', ...)`
- `surgeon-hud/src/components/VideoBackground.jsx` → `http://localhost:<PORT>/video`

---

## 4. Quick verification

| Check | URL / action |
|-------|----------------|
| Health | `http://localhost:5000/health` — dependency flags |
| Video | Open `http://localhost:5000/video` — MJPEG stream |
| Loop A | HUD step banner + FPS/latency; VLM overlays if Gemini returns `ar_boxes` |
| Loop B | Say **“Hey Surgeon”**, then a question — Q&A panel + spoken answer |

---

## 5. Architecture notes

- **Production path:** `python -m backend.app.main` — see [`docs/ARCHITECTURE.md`](ARCHITECTURE.md).
- **Alternate demo:** `python merged_backend.py` (simulated Loop A + Loop B). Prefer **`python -m backend.app.main`** for real VLM + glasses.
- **Snowflake:** Loop B RAG uses `SNOWFLAKE.CORTEX.SEARCH` in `backend/app/loop_b/intelligence_pipeline.py` (`surgical_protocols_search`). Adjust SQL if your account differs.

---

## 6. Windows PowerShell (no `&&`)

Older PowerShell does not support `&&`. Chain commands with `;` or run them on separate lines:

```powershell
cd surgeon-hud; npm run dev
```

## 7. Troubleshooting

| Issue | What to try |
|-------|-------------|
| OpenCV spam: `MSMF can't grab frame` / error `-1072875772` | On Windows, set **`CAMERA_BACKEND=dshow`** in `backend/.env` (DirectShow). Default **`auto`** already tries DSHOW first; ensure **`BRIO_CAMERA_INDEX`** matches your glasses/Brio (often `1` or `2`). |
| Wrong or black camera | Adjust `BRIO_CAMERA_INDEX`; close other apps using the camera. |
| `ModuleNotFoundError` for `backend` | Run `python -m backend.app.main` from the **repo root** with the venv activated. |
| No mic / PyAudio | Install [PyAudio](https://pypi.org/project/PyAudio/) for your Python version; set `BRIO_MIC_INDEX`. |
| Gemini errors | Check `GEMINI_MODEL` and `GEMINI_API_KEY`. |
| HUD not connecting | Match `PORT` and firewall; Socket.IO uses `cors_allowed_origins='*'`. |
