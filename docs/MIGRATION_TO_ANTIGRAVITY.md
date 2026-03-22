# SurgeAI → Antigravity Migration Guide

> Complete knowledge transfer document for AI agents and developers picking up this project.
> Written March 2026. Updated March 22, 2026 with Hard Stabilization changes.
> Captures everything: architecture, data flow, every file, every convention, every gotcha, and current known issues.

---

## 1. What This Project IS

**SurgeAI** (also called **SurgeonAI**) is a **real-time surgical training assistant** that uses a live webcam feed, computer vision (YOLOv8 + OpenCV), and a React HUD to simulate an augmented-reality surgical experience.

It is a **demo/prototype** (v0.1.0) — not production medical software. It uses everyday household objects (banana, knife, scissors, fork) as stand-ins for surgical instruments and tissue.

**The core loop:**
1. A webcam captures live video
2. YOLOv8 detects objects in each frame (banana = tissue, knife = scalpel, scissors/fork = forceps)
3. OpenCV detects a red marker rectangle drawn on the banana (= incision zone)
4. A 6-phase state machine orchestrates the surgical demo flow
5. Results stream to a React HUD via Socket.IO (`frame_state` events) and the video streams via MJPEG
6. The HUD renders AR-style overlays (bounding boxes, incision zones, trace lines, angle readouts) on top of the live video

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    BACKEND (Python)                  │
│                  backend/server.py                   │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │  Webcam  │→ │ YOLOv8n  │→ │ DemoOrchestrator  │  │
│  │ (DSHOW)  │  │ Detector │  │  (State Machine)  │  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
│       │              │               │              │
│       │         ┌────┴────┐     ┌────┴────┐         │
│       │         │ OpenCV  │     │ Object  │         │
│       │         │Red Rect │     │ Tracker │         │
│       │         └─────────┘     └─────────┘         │
│       │                              │              │
│  /video (MJPEG)              Socket.IO /realtime    │
│       │                      (frame_state events)   │
└───────┼──────────────────────────────┼──────────────┘
        │                              │
        ▼                              ▼
┌─────────────────────────────────────────────────────┐
│                  FRONTEND (React HUD)                │
│                  surgeon-hud/                        │
│                                                     │
│  ┌────────────────┐  ┌────────────────────────────┐  │
│  │ VideoBackground │  │     SocketManager          │  │
│  │ <img src=MJPEG>│  │  (receives frame_state)    │  │
│  └────────────────┘  └────────────┬───────────────┘  │
│                                   │                  │
│                          ┌────────▼────────┐         │
│                          │  useHudStore    │         │
│                          │  (Zustand)      │         │
│                          └────────┬────────┘         │
│                                   │                  │
│         ┌─────────────────────────┼──────────┐       │
│         ▼            ▼            ▼          ▼       │
│    AROverlay    AngleHUD    VoicePill   WarningBanner │
│    BootScreen   SystemHealth   SurgeryComplete       │
│    ConnectionFallback                                │
└─────────────────────────────────────────────────────┘
```

### Ports
| Service | Port | URL |
|---------|------|-----|
| Backend (Flask) | 5000 | `http://localhost:5000` |
| Frontend (Vite dev) | 5173 | `http://localhost:5173` |

### Communication Channels
| Channel | Protocol | Purpose |
|---------|----------|---------|
| `/video` | HTTP MJPEG stream | Raw camera frames as continuous JPEG stream |
| `/realtime` namespace | Socket.IO (long-polling, NOT websocket) | `frame_state` and `system_health` events |
| `/health` | HTTP GET JSON | Health check (`{ok, camera, yolo}`) |

---

## 3. The 6-Phase State Machine

This is the heart of the demo. The `DemoOrchestrator` class in `server.py` drives everything.

| Phase | Name | How It's Triggered | What Happens on HUD |
|-------|------|--------------------|---------------------|
| **0** | Idle | Default/startup | Pulsing "Scanning" dot at bottom of screen. No AR overlays. Clean video. |
| **1** | Target Acquired | Banana detected for 6 consecutive frames | Voice: "Patient tissue detected. Please pick up your scalpel." AR boxes appear around detected objects. |
| **2** | Tool Tracking | Banana + knife both visible for 6 frames | Voice: "Scalpel acquired. Make your incision along the highlighted zone. Maintain a 30 to 60 degree angle." Zone debug overlay (left=CLAMP, right=SCALPEL labels). |
| **3** | Incision Mode | Scalpel near tissue (< 30% of frame diagonal) AND red zone visible | Angle HUD appears showing approach angle (0-90°). Status: "Optimal" (30-60°), "Too Steep" (>60°), "Too Shallow" (<30°). Trace line from scalpel to incision zone (green→yellow→red based on deviation). Red incision zone polygon overlay. WARNING banner if angle > 60°: "CRITICAL: Angle too steep! You are piercing crucial arteries!" |
| **4** | Clamping | 6 seconds of sustained incision mode | Voice: "Incision complete. Put down the scalpel and pick up your clamps." |
| **5** | Complete | Clamps brought near tissue (< 35% of diagonal) for 6 frames | Voice: "Excellent. Peel the skin back." After 3 seconds: full-screen "SURGERY SUCCESSFUL" overlay with animated checkmark. |

### Debouncing
All phase transitions require **6 consecutive frames** (`DEBOUNCE = 6`) where the condition is true. If the condition fails, the debounce counter decrements (doesn't reset to 0). This prevents flicker from momentary detection drops.

### Voice Prompts
Each phase's voice prompt fires **only once** (tracked in `_voices_sent` set). The backend sends the text string via `frame_state.voice_prompt`, and the frontend's `VoicePill` component speaks it using the Web Speech API and displays it in a Dynamic Island-style pill at the top of the screen for 6 seconds.

---

## 4. Object Detection & Classification

### YOLO Class Mapping
The system uses **YOLOv8n** (nano model, `yolov8n.pt`) which is the standard COCO-trained model. It repurposes these COCO classes:

| COCO Class | COCO ID | Surgical Label | Color |
|------------|---------|----------------|-------|
| Banana | 46 | Patient Tissue | `#22d3ee` (cyan) |
| Knife | 43 | Scalpel | `#22c55e` (green) |
| Scissors | 76 | Forceps | `#3b82f6` (blue) |
| Fork | 42 | Forceps | `#3b82f6` (blue) |

### Detection Filters (Head/Body Rejection)
Before spatial classification, two filters gate YOLO detections:
1. **Box area filter**: Any detection occupying **>30% of frame area** is rejected (prevents head/torso misclassification)
2. **Aspect ratio filter**: For instrument classes (knife/scissors/fork), if `min(w,h)/max(w,h) > 0.85` (near-square bounding box), the detection is rejected (tools are elongated, heads are not)

### Spatial Instrument Classification
Beyond YOLO's class prediction, there's a **per-object spatial override system**:
- If a tool's bounding box center is in the **right half** of the frame → labeled "Scalpel"
- If a tool's bounding box center is in the **left half** of the frame → labeled "Forceps"  
- A 5% margin (`SPATIAL_MARGIN`) around the center line uses raw YOLO classification
- Classification is applied **per bounding box**, not at the frame level

This is debounced via **majority voting** over the last 5 frames per region (left/right) to prevent label flicker.

### Object Tracking
The `ObjectTracker` class provides:
- **Smoothed positions**: Exponential moving average (`SMOOTH_ALPHA = 0.7`) blending new detections with previous positions
- **Velocity prediction**: When an object goes missing, its position is predicted using last-known velocity for up to 0.5 seconds (`TRACK_TTL`)
- **Persistent identity**: Tracks are keyed by role/label, not by YOLO detection ID

### Red Rectangle Detection (Incision Zone)
OpenCV processes the **cropped banana region** to find a red marker drawn on the banana:
1. Converts crop to HSV color space
2. Creates red mask (hue 0-12 and 160-180, saturation > 70, value > 50)
3. Morphological close + open to clean mask
4. Finds largest contour, gets `minAreaRect`
5. Returns center point, angle, and corner points (in absolute frame coordinates)

### Scalpel Angle Calculation
During Phase 3, the system computes the **approach angle** between the scalpel and incision zone:
- Scalpel angle: derived from bounding box aspect ratio via `atan2(height, width)`
- Compared against the red rectangle's angle
- Difference clamped to 0-90° range
- Optimal range: 30-60°

### Deviation Color
A **deviation metric** measures how far the scalpel center is from the incision zone center:
- `deviation = distance / max(200px, 15% of frame width)`
- Mapped to color: `0 = green (#00ff00)`, `0.5 = yellow (#ffff00)`, `1.0 = red (#ff0000)`

---

## 5. Backend Deep Dive (`backend/server.py`)

### Threading Model
The backend runs 3 threads:
1. **Main thread**: Flask/Socket.IO server (Werkzeug, threading async mode)
2. **Capture thread** (`capture_thread`): Reads webcam frames at native camera FPS (no sleep) into `latest_frame` buffer
3. **Vision thread** (`vision_loop`): Runs YOLO + OpenCV + state machine at ~15 FPS, emits Socket.IO events

Shared state between threads:
- `latest_frame` (protected by `latest_frame_lock`) — the most recent camera frame
- `camera` (protected by `camera_lock`) — the OpenCV VideoCapture object

### Camera Configuration
- Uses **DirectShow** (`cv2.CAP_DSHOW`) on Windows — required for external USB cameras
- Resolution: **640×480** at 30 FPS (changed from 1280×720 for faster YOLO inference and lower latency)
- **Buffer size**: `CAP_PROP_BUFFERSIZE = 1` — prevents frame accumulation lag
- Camera index configured via `CAMERA_INDEX` env var (default 1, because 0 is usually internal webcam)
- The system **never falls back** to internal camera — it raises a fatal error if the external camera isn't found
- Originally designed for a **Logitech BRIO 100** webcam attached to AR glasses
- Capture thread runs with **no sleep** — the camera's native frame rate governs timing

### MJPEG Stream
`/video` endpoint serves a multipart JPEG stream:
- JPEG quality: 80
- Frame rate: ~30 FPS (33ms sleep between frames)
- Format: `multipart/x-mixed-replace; boundary=frame`

### Socket.IO Events
All events use the `/realtime` namespace.

**Emitted by backend:**
| Event | Payload Shape | Frequency |
|-------|---------------|-----------|
| `frame_state` | `{payload: {current_phase, voice_prompt, warning, ar_elements, angle_data}}` | Every vision loop iteration (~15 FPS) |
| `system_health` | `{payload: {loopAAlive, fps, latency}}` | Every vision loop iteration |

**`frame_state.payload` fields:**
- `current_phase` (int 0-5): Current state machine phase
- `voice_prompt` (string or null): Text to speak (fires once per phase transition)
- `warning` (string or null): Warning text (only during Phase 3 when angle > 60°)
- `ar_elements` (array): List of AR overlay elements to render
- `angle_data` (object, always present): `{approach_angle: int, status: string}` — defaults to `{approach_angle: 0, status: "idle"}` when not in Phase 3; populated with real values during Phase 3

**`ar_elements` element types:**
| Type | Fields | When |
|------|--------|------|
| `box` | `{x, y, width, height, color, label, confidence}` — all normalized 0-1 | Always (for each detected object) |
| `polygon` | `{points: [[x,y]...], color, label}` — normalized | Phase ≥ 2, when red zone visible |
| `line` | `{x1, y1, x2, y2, color}` — normalized | Phase 3, scalpel-to-target trace |
| `zone_debug` | `{midpoint: 0.5}` | Always (shows left/right classification zones) |
| `success_overlay` | `{}` | Phase 5, after 3 second delay |

### FPS Tracking
FPS is computed as an exponential moving average: `fps_ema = 0.85 * fps_ema + 0.15 * (1/dt)`

### Vision Loop Timing
Target: ~15 FPS. If a frame processes in less than 66ms, the loop sleeps the remaining time.

---

## 6. Frontend Deep Dive (`surgeon-hud/`)

### Tech Stack
| Library | Version | Purpose |
|---------|---------|---------|
| React | 18.3.1 | UI framework |
| Vite | 5.4.10 | Build tool and dev server |
| Zustand | 5.0.12 | State management (ONLY state library — no Context API, no Redux) |
| Framer Motion | 12.38.0 | All animations (entrance, exit, continuous) |
| Socket.IO Client | 4.8.3 | Real-time backend communication |
| Tailwind CSS | 3.4.19 | Styling |
| @elevenlabs/react | 0.14.3 | Listed as dependency (voice synthesis, may not be actively used — VoicePill uses Web Speech API instead) |

### Design Language ("Anti-Gravity Aesthetic")
Defined in `.windsurfrules`:
- **Glassmorphism**: `bg-black/60 backdrop-blur-md` for floating panels
- **Sharp glowing borders** via Tailwind ring/border utilities
- **High contrast text**: `text-green-400`, `text-red-500`, `text-white` on dark backgrounds
- **Floating panels**: `absolute` positioning, never in document flow
- **All animations**: Must use `framer-motion`, never CSS transitions for entrance/exit

### Component Hierarchy & Z-Index Stack
```
<SocketManager>                    (no visual, just Socket.IO connection)
  <main>                           (fullscreen black)
    <BootScreen />                 z-[100]  — startup screen, hides after boot
    <VideoBackground />            z-0      — MJPEG <img> tag
    <ScanningDot />                z-10     — Phase 0 only, pulsing dot
    <AROverlay />                  z-10     — SVG bounding boxes, polygons, lines
    <SystemHealth />               z-[15]   — FPS/latency readout (bottom-right)
    <AngleHUD />                   z-20     — Always visible angle display (bottom-right)
    <WarningBanner />              z-30     — Red critical warning (top)
    <VoicePill />                  z-40     — Dynamic Island voice prompt (top-center)
    <SurgeryComplete />            z-50     — Phase 5 success overlay
    <ConnectionFallback />         z-[100]  — Amber banner when socket disconnected
```

### State Management (`useHudStore.js`)
Single Zustand store holds all HUD state:

```javascript
{
  isConnected: false,      // Socket.IO connection status
  isBooted: false,         // Has user clicked "Initialize System"?
  phase: 0,                // Current demo phase (0-5)
  voicePrompt: null,       // Text to speak (string or null)
  warning: null,           // Warning banner text (string or null)
  arElements: [],          // Array of AR overlay elements from backend
  angleData: null,         // {approach_angle, status} or null
  systemMetrics: {fps: 0, latency: 0}
}
```

Key method: `applyFrameState(state)` — batch-updates phase, voicePrompt, warning, arElements, and angleData from a single `frame_state` Socket.IO event.

### Socket.IO Connection (`SocketManager.jsx`)
- Transport: **Long polling ONLY** (`transports: ['polling'], upgrade: false`) — NOT WebSocket
- Reconnection: Infinite attempts, 500ms delay
- Events consumed: `frame_state` → `applyFrameState()`, `system_health` → `setMetrics()`
- Uses `unwrap()` helper to handle `{payload: ...}` wrapper

### Video Feed (`VideoBackground.jsx`)
- Renders as a plain `<img>` tag with `src={apiBase}/video`
- Completely isolated from React state — the MJPEG stream never causes re-renders
- Shows error UI if the stream fails to load

### AR Overlay (`AROverlay.jsx`)
Renders in an SVG with `viewBox="0 0 1 1"` (all coordinates are normalized 0-1):
- **BoxBracket**: Corner-style targeting brackets (4 corners × 2 lines each)
- **PolygonOutline**: Dashed red outline for incision zone
- **TraceLine**: Glowing line from scalpel to target with deviation color
- **ZoneDebug**: Faint center line showing left (CLAMP) / right (SCALPEL) zones
- **BoxLabel**: HTML labels floating above boxes (outside SVG for better text rendering)

Hides entirely during Phase 0 (clean video only).

### Boot Screen (`BootScreen.jsx`)
Full-screen startup UI with:
- Green grid background
- "SURGEON**AI**" title with pulsing glow
- Scanning line animation
- "Initialize System" button
- Loading bar on click
- Version tag "v0.1.0 — PROTOTYPE BUILD"
- Fades out after 600ms boot sequence

### Voice Pill (`VoicePill.jsx`)
Dynamic Island-style component:
- When no prompt: tiny pulsing dot at top center
- When prompt arrives: expands into pill with animated waveform bars + text
- Speaks text via **Web Speech API** (not ElevenLabs)
- Auto-hides after 6 seconds
- Won't repeat the same prompt (deduplication via `lastSpokenRef`)
- Voice preferences: Samantha, Google, or Daniel voices

### Warning Banner (`WarningBanner.jsx`)
- Slides down from top with spring animation
- Red pulsing dot + monospaced uppercase text
- Only shown when `warning` is non-null (Phase 3, angle too steep)

### Surgery Complete (`SurgeryComplete.jsx`)
- Full-screen frosted overlay
- Animated green checkmark ring with pulsing glow
- "SURGERY SUCCESSFUL" title
- "Procedure Complete — All Vitals Normal" subtitle
- Only shows in Phase 5 after the backend adds a `success_overlay` AR element (3 second delay)

### System Health (`SystemHealth.jsx`)
- Bottom-right corner
- Monospaced FPS and latency readout
- Glassmorphism background

### Connection Fallback (`ConnectionFallback.jsx`)
- Top amber banner shown when Socket.IO is disconnected
- Shows helpful debugging info (which URLs to check, which env vars to match)
- Spinning loader icon

---

## 7. Configuration Reference

### Backend Environment (`backend/.env`)
| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `5000` | Flask server port |
| `YOLO_MODEL` | `yolov8n.pt` | Path to YOLO weights file |
| `YOLO_CONFIDENCE` | `0.3` | Minimum detection confidence threshold |
| `CAMERA_INDEX` | `1` | OpenCV camera device index (1 = first external camera) |
| `CAMERA_NAME` | `BRIO` | Human-readable name (logging only) |
| `SOCKET_NAMESPACE` | `/realtime` | Socket.IO namespace path |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | CORS allowed origin |

### Frontend Environment (`surgeon-hud/.env`)
| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE` | `http://localhost:5000` | Backend origin URL |
| `VITE_SOCKET_NAMESPACE` | `/realtime` | Must match backend's `SOCKET_NAMESPACE` |

### Critical Coupling
The frontend and backend **must agree** on:
1. `PORT` ↔ `VITE_API_BASE` (same origin)
2. `SOCKET_NAMESPACE` ↔ `VITE_SOCKET_NAMESPACE` (same path, default `/realtime`)

---

## 8. Physical Setup

The demo requires real objects in front of a webcam:
- **Banana** with a **red marker line** drawn on it → detected as "Patient Tissue", red line → incision zone
- **Knife** → detected as "Scalpel"
- **Scissors or fork** → detected as "Forceps" / clamps

Camera: External USB webcam (tested with **Logitech BRIO**), configured via `CAMERA_INDEX`.

---

## 9. How to Run

### Backend (Option A: One-Click)
```
run_backend.bat
```

### Backend (Option B: Manual)
```powershell
.\.venv\Scripts\activate
pip install -r backend\requirements.txt
python backend\server.py
```

### Frontend
```powershell
cd surgeon-hud
npm install
npm run dev
```

Open `http://localhost:5173`.

---

## 10. Complete File Tree

```
surgeai/
├── .gitignore
├── README.md
├── MIGRATION_TO_ANTIGRAVITY.md          ← this file
├── run_backend.bat                      ← one-click backend startup (Windows)
├── surgeAI buildplan.pdf                ← original build plan doc
├── yolov8n.pt                           ← YOLO weights (gitignored, ~6MB)
│
├── backend/
│   ├── .env                             ← config (gitignored)
│   ├── requirements.txt                 ← Python deps (unpinned)
│   └── server.py                        ← entire backend (~635 lines)
│
└── surgeon-hud/
    ├── .env                             ← frontend config (gitignored)
    ├── .env.example                     ← template for .env
    ├── .gitignore
    ├── .windsurfrules                   ← AI generation conventions
    ├── eslint.config.js
    ├── index.html                       ← root HTML
    ├── package.json
    ├── package-lock.json
    ├── postcss.config.js
    ├── tailwind.config.js
    ├── vite.config.js
    ├── README.md
    ├── public/
    │   └── vite.svg
    └── src/
        ├── index.css                    ← Tailwind imports + body styles
        ├── main.jsx                     ← React entry point
        ├── App.jsx                      ← main layout + inline components
        ├── config.js                    ← API/socket URL helpers
        ├── components/
        │   ├── AROverlay.jsx            ← SVG AR rendering
        │   ├── BootScreen.jsx           ← startup UI
        │   ├── ConnectionFallback.jsx   ← disconnect warning
        │   ├── SystemHealth.jsx         ← FPS/latency readout
        │   ├── VideoBackground.jsx      ← MJPEG video feed
        │   └── VoicePill.jsx            ← Dynamic Island voice UI
        ├── lib/
        │   └── logger.js               ← color-coded console logger
        ├── providers/
        │   └── SocketManager.jsx        ← Socket.IO client
        └── store/
            └── useHudStore.js           ← Zustand global store
```

---

## 11. Dependencies

### Python (backend/requirements.txt) — no versions pinned
| Package | Purpose |
|---------|---------|
| `flask` | HTTP server |
| `flask-socketio` | Socket.IO server |
| `opencv-python` | Camera capture, image processing, red rectangle detection |
| `ultralytics` | YOLOv8 object detection |
| `numpy` | Array math for OpenCV |
| `python-dotenv` | Load `.env` files |

### Node (surgeon-hud/package.json)
**Runtime:**
| Package | Version | Purpose |
|---------|---------|---------|
| `react` | ^18.3.1 | UI framework |
| `react-dom` | ^18.3.1 | React DOM renderer |
| `zustand` | ^5.0.12 | State management |
| `framer-motion` | ^12.38.0 | Animations |
| `socket.io-client` | ^4.8.3 | Backend communication |
| `@elevenlabs/react` | ^0.14.3 | Voice (listed but VoicePill uses Web Speech API) |

**Dev:**
| Package | Version | Purpose |
|---------|---------|---------|
| `vite` | ^5.4.10 | Build tool |
| `@vitejs/plugin-react` | ^4.3.3 | React Vite plugin |
| `tailwindcss` | ^3.4.19 | Utility CSS |
| `postcss` | ^8.5.8 | CSS processing |
| `autoprefixer` | ^10.4.27 | CSS vendor prefixes |
| `eslint` | ^9.13.0 | Linting |
| `eslint-plugin-react` | ^7.37.2 | React lint rules |
| `eslint-plugin-react-hooks` | ^5.0.0 | Hooks lint rules |
| `eslint-plugin-react-refresh` | ^0.4.14 | HMR lint rules |
| `globals` | ^15.11.0 | ESLint globals |
| `@types/react` | ^18.3.12 | TypeScript types (for IDE) |
| `@types/react-dom` | ^18.3.1 | TypeScript types (for IDE) |

---

## 12. Key Algorithms & Constants

### Object Tracker Smoothing
```
smoothed_position = 0.7 * new_detection + 0.3 * previous_position
```

### Track Time-To-Live
Objects persist for **0.5 seconds** after YOLO stops detecting them, using velocity prediction to extrapolate position.

### Phase Transition Debounce
**6 frames** of sustained condition required. Counter decrements (not resets) on failure.

### Incision Duration
Phase 3 → 4 requires **6 seconds** of sustained incision mode.

### Complete Delay
Phase 5 shows success overlay after **3 seconds**.

### Red Detection HSV Ranges
- Low red: H=0-12, S=70-255, V=50-255
- High red: H=160-180, S=70-255, V=50-255
- Minimum pixel count: 80
- Minimum contour area: 40

### Proximity Thresholds
- Phase 2→3 (scalpel near tissue): distance < **30% of frame diagonal**
- Phase 4→5 (clamps near tissue): distance < **35% of frame diagonal**

### Angle Assessment
- **Optimal**: 30° – 60°
- **Too Steep**: > 60° (triggers warning)
- **Too Shallow**: < 30°

---

## 13. Data Flow (Frame-by-Frame)

```
1. capture_thread reads webcam frame → latest_frame buffer

2. vision_loop grabs latest_frame
   ├── YOLOv8.predict(frame, conf=0.3, classes=[42,43,46,76])
   │   └── For each detection:
   │       ├── REJECT if box_area > 30% of frame_area (head/body filter)
   │       ├── REJECT if instrument with near-square aspect ratio (>0.85)
   │       ├── Banana (46) → label "Patient Tissue"
   │       └── Knife/Scissors/Fork → classify_instrument() per-object spatial override
   │           └── stabilize_label() majority vote over 5 frames
   │
   ├── detect_red_rectangle(frame, banana_bbox)
   │   └── HSV red mask → morphology → contours → minAreaRect
   │
   ├── tracker.update(detections, now)
   │   └── Smooth positions, predict missing objects, expire old tracks
   │
   └── orchestrator.process(tracked, red_rect, fh, fw)
       ├── Build ar_elements (boxes, polygons, lines, zone_debug)
       ├── Check phase transitions (with debounce)
       ├── Compute angle_data (Phase 3)
       ├── Generate warning text (Phase 3, angle > 60°)
       ├── Queue voice prompt (once per phase)
       └── Return frame_state dict

3. Socket.IO emit("frame_state", {payload: state})
   Socket.IO emit("system_health", {payload: {loopAAlive, fps, latency}})

4. Frontend SocketManager receives events
   └── useHudStore.applyFrameState(state)
       ├── Updates phase, voicePrompt, warning, arElements, angleData
       └── React re-renders relevant components

5. AROverlay reads arElements → renders SVG overlays
   VoicePill reads voicePrompt → speaks via Web Speech API
   AngleHUD reads angleData → shows angle display
   WarningBanner reads warning → shows/hides banner
   VideoBackground renders MJPEG stream independently (no re-renders)
```

---

## 14. Conventions & Rules for New Agents

### Coding Conventions
1. **State management**: Zustand ONLY. No React Context, no Redux, no prop drilling for global state.
2. **Animations**: Framer Motion ONLY for entrance/exit/continuous animations.
3. **Styling**: Tailwind CSS. Custom color: `hud-black = rgba(0,0,0,0.6)`. Glassmorphism pattern: `bg-black/60 backdrop-blur-md`.
4. **Video isolation**: The MJPEG `<img>` tag must NEVER be affected by React state changes. It renders once and streams independently.
5. **Component architecture**: Each component reads directly from Zustand store (no prop drilling for HUD state).
6. **Coordinate system**: All AR element positions are **normalized 0-1** (fraction of frame width/height).
7. **Backend is single-file**: The entire backend is one Python file (`server.py`, ~635 lines). Flask + Socket.IO + YOLO + OpenCV + ObjectTracker + state machine.
8. **No TypeScript**: Project uses JSX (not TSX), though TypeScript types are installed for IDE support.
9. **Font**: Monospace (`font-mono`) throughout for the HUD aesthetic.
10. **Colors**: Green = good/primary (`#22c55e`, `text-green-400`), Red = danger/warning (`#ef4444`), Cyan = tissue (`#22d3ee`), Blue = forceps (`#3b82f6`).

### Gotchas
1. **Socket.IO uses polling, not WebSocket**: `transports: ['polling'], upgrade: false` — this is intentional, don't change it.
2. **Camera index 1, not 0**: Index 0 is usually the internal laptop camera. The system refuses to fall back to internal.
3. **DSHOW required on Windows**: `cv2.CAP_DSHOW` is needed for external USB cameras on Windows.
4. **No pinned Python deps**: `requirements.txt` has no version numbers. Could break if ultralytics/opencv releases a breaking change.
5. **`@elevenlabs/react` is installed but not used**: VoicePill uses Web Speech API instead. The package may have been planned for future use.
6. **The secret key is hardcoded**: `app.config["SECRET_KEY"] = "surgeai-demo"` — fine for demo, not for production.
7. **CORS is wide open**: `cors_allowed_origins="*"` on Socket.IO.
8. **Werkzeug unsafe mode**: `allow_unsafe_werkzeug=True` is required for threaded Socket.IO in dev.

---

## 15. What Was Working / Last Known State

As of March 22, 2026 (post Hard Stabilization):
- Backend runs and captures webcam frames via Logitech BRIO 100 at 640x480
- YOLOv8n detects objects with the COCO-trained model (conf=0.3)
- Detection filters (box area + aspect ratio) reject head/body misclassifications
- Spatial classification overrides YOLO labels per-object (right=scalpel, left=clamp)
- ObjectTracker provides smoothed, velocity-predicted persistent tracks
- The 6-phase state machine advances through all phases
- Socket.IO streams frame_state events (with always-present `angle_data`) to the frontend
- MJPEG video stream works at `/video` with no wobble (buffer size 1, no capture sleep)
- Frontend renders all AR overlays, voice prompts, warnings
- AngleHUD is always mounted in bottom-right corner
- The full demo flow (idle → detect tissue → pick up scalpel → incise → clamp → complete) works end-to-end
- One-click startup via `run_backend.bat`

### Changes applied in Hard Stabilization (March 22, 2026):
- Camera resolution reduced from 1280x720 to 640x480
- `CAP_PROP_BUFFERSIZE` set to 1 (prevents lag accumulation)
- `time.sleep(0.015)` removed from capture thread
- Box area filter added (>30% frame area = rejected)
- Aspect ratio filter added (near-square instruments rejected)
- `angle_data` now always present in `frame_state` (defaults to `{approach_angle: 0, status: "idle"}`)
- AngleHUD always visible with idle state ("Waiting for scalpel..."), repositioned to bottom-right
- YOLO confidence lowered from 0.35 to 0.3
- `run_backend.bat` created for one-click backend startup
- README simplified

---

## 15b. Current Known Issues (UNRESOLVED)

### ISSUE 1: Scalpel Not Reliably Detected on Right Side
**Severity:** HIGH — blocks core demo flow

**Symptom:** When a knife (scalpel) is placed on the right side of the frame, the system frequently fails to detect it. The scalpel bounding box does not appear, or appears inconsistently.

**Root cause analysis:**
- YOLOv8n (COCO-trained) does not reliably detect "knife" (class 43) at the demo's camera angle, lighting, and knife type. The pretrained model was trained on general kitchen knife images, not surgical instrument shapes or demo props.
- The system currently depends entirely on YOLO producing a detection before spatial classification can assign the "Scalpel" label. If YOLO sees nothing, there is no bounding box to classify.
- There is no fallback mechanism to inject a virtual scalpel detection when YOLO misses but something is clearly present on the right side.

**Potential fixes (not yet implemented):**
1. **Motion-based fallback**: If no scalpel is detected but there is motion/contour activity in the right half of the frame, inject a synthetic "Scalpel" detection with a bounding box derived from the motion region.
2. **Lower YOLO confidence further** (currently 0.3 — going lower risks more false positives elsewhere).
3. **Expand ALLOWED_CLASSES** to include more COCO classes that might match the physical knife being used (e.g., class 43 "knife" may not fire but class 76 "scissors" or others might).
4. **Fine-tune or retrain** a YOLO model on the actual demo props.
5. **Use a second detection method** (contour-based shape detection, edge detection) as a backup when YOLO fails.

**Impact on demo flow:** Phase 1→2 transition requires both banana AND knife to be detected. If the knife is not detected, the demo stalls at Phase 1 ("Please pick up your scalpel") indefinitely.

---

### ISSUE 2: Angle HUD Data Shows Intermittently
**Severity:** MEDIUM — cosmetic/UX issue

**Symptom:** The Angle HUD in the bottom-right corner sometimes shows the angle reading and sometimes shows "Waiting for scalpel..." even when the scalpel should be actively tracked in Phase 3.

**Root cause analysis:**
- The backend now always sends `angle_data` in every `frame_state` emission, but it only populates real angle values (approach_angle, Optimal/Too Steep/Too Shallow) during Phase 3 when BOTH a knife detection AND a red rectangle are present simultaneously.
- If the knife detection drops for even one frame (due to YOLO missing it — see Issue 1), `angle_data` reverts to `{approach_angle: 0, status: "idle"}` for that frame.
- The frontend AngleHUD reads this as idle and shows "Waiting for scalpel..." until the next frame where both conditions are met again.
- This creates a flickering effect where the angle readout pops between real values and the idle state.

**Potential fixes (not yet implemented):**
1. **Persist last-known angle data**: Instead of resetting to idle every frame, keep the previous `angle_data` values alive for a short TTL (e.g., 0.5-1 second) before reverting to idle. This mirrors the ObjectTracker's persistence logic but for angle state.
2. **Frontend-side smoothing**: The AngleHUD component could hold onto the last non-idle `angleData` for a brief period before falling back to idle, smoothing over momentary detection drops.
3. **Fix Issue 1 first**: If scalpel detection becomes reliable, the angle data will naturally be consistent since it depends on the scalpel being detected.

**Relationship to Issue 1:** This is a downstream consequence of Issue 1. If the scalpel were always detected on the right side, the angle data would always be populated during Phase 3.

---

### ISSUE 3: Scalpel Detection Depends Entirely on YOLO
**Severity:** ARCHITECTURAL — root cause of Issues 1 and 2

**Summary:** The entire pipeline from scalpel detection → spatial classification → tracking → angle calculation → AngleHUD display depends on YOLO successfully detecting a "knife" class object. If YOLO misses, the entire chain breaks for that frame. The spatial classification, object tracker, and angle computation are all downstream consumers that receive nothing to process.

**The architectural gap:** There is no YOLO-independent detection fallback. The system needs a secondary detection path (motion, contour, color, background subtraction) that can provide candidate bounding boxes for the right side of the frame when YOLO fails, so spatial classification and tracking can still operate.

---

## 16. Endpoints Quick Reference

| Method | URL | Response |
|--------|-----|----------|
| GET | `http://localhost:5000/video` | MJPEG stream (multipart/x-mixed-replace) |
| GET | `http://localhost:5000/health` | `{"ok": true, "camera": bool, "yolo": bool}` |
| Socket.IO | `http://localhost:5000/realtime` | Namespace for `frame_state` and `system_health` events |

---

## 17. For Rebuilding in Antigravity

If you're rebuilding this system in a new codebase, here's what matters most:

1. **The state machine is the core logic** — 6 phases, debounced transitions, voice prompts per phase
2. **Object detection can use any model** — the current one just repurposes COCO classes. A custom-trained model on actual surgical instruments would be better. **This is the single biggest improvement that could be made** (see Issue 3 above).
3. **The AR overlay system is coordinate-normalized** — everything is 0-1, which makes it resolution-independent
4. **The frontend and backend are completely decoupled** — backend emits JSON events, frontend renders them. You could swap either side independently.
5. **The MJPEG stream is separate from the data stream** — video goes over HTTP, telemetry goes over Socket.IO. This is intentional for performance.
6. **The HUD aesthetic is defined in `.windsurfrules`** — glassmorphism, monospace, green/cyan/red color scheme, floating panels
7. **Physical setup required** — this isn't a simulation, it uses real objects in front of a real camera
8. **Detection must not depend solely on YOLO** — a fallback detection method (contour, motion, background subtraction) is needed for demo reliability. YOLO alone is not consistent enough for the demo props at all angles and lighting conditions.
9. **Angle data should persist** — the AngleHUD should hold onto last-known angle values for a short TTL rather than reverting to idle every frame YOLO misses the scalpel.

---

## 18. Pipeline Diagram (Current State)

```
Camera (640x480, DSHOW, bufsize=1)
       │
       ▼
Capture Thread (no sleep, native FPS)
       │
       ▼
latest_frame buffer
       │
       ▼
Vision Loop (~15 Hz)
       │
       ├── YOLO predict (conf=0.3, classes=[42,43,46,76])
       │       │
       │       ├── Box Area Filter (>30% = reject)
       │       ├── Aspect Ratio Filter (near-square = reject)
       │       │
       │       ├── Banana → "Patient Tissue"
       │       └── Instruments → classify_instrument() per-object spatial override
       │                           └── stabilize_label() majority vote
       │
       ├── Red Rectangle Detection (OpenCV HSV on banana crop)
       │
       ├── ObjectTracker.update() (smoothing + velocity + TTL)
       │
       └── DemoOrchestrator.process() (6-phase state machine)
               │
               ├── ar_elements (boxes, polygons, lines, zone_debug)
               ├── angle_data (ALWAYS present, idle default)
               ├── warning (Phase 3, steep angle)
               └── voice_prompt (once per phase)
                       │
                       ▼
               Socket.IO emit (frame_state + system_health)
                       │
                       ▼
               React HUD (Zustand → components)
                       │
                       ├── VideoBackground (MJPEG, independent)
                       ├── AROverlay (SVG bounding boxes, zones)
                       ├── AngleHUD (ALWAYS visible, bottom-right)
                       ├── VoicePill (Web Speech API)
                       ├── WarningBanner (Phase 3)
                       └── SurgeryComplete (Phase 5)
```

---

*End of migration document. Last updated March 22, 2026. See Section 15b for current known issues that need resolution.*
