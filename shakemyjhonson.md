# Developer Log: SurgeonAI AR & Vision System

This document outlines the end-to-end implementation of the SurgeonAI 6-Phase State Machine, Backend Vision processing, and Frontend AR overlay mapping.

## Overview

The goal was to replace a barebones mock-backend structure with a production-ready spatial computing POC. The resulting system uses YOLOv8 for coarse objection detection mixed with bespoke OpenCV mathematical processing for precise feature extraction (scalpel blade orientation, target incision zones). This data is pipelined directly into a web-based React/Vite HUD overlaid on top of a low-latency MJPEG video stream.

---

## Part 1: Python/Flask Backend Vision Pipeline (`simulate_demo.py`)

### 1. Hybrid ML + CV Object Detection Pipeline
We initially attempted to just use the `yolov8n` base model. While brilliant at identifying the `banana`, `scissors` (for clamping), and `knife`, it lacked the spatial awareness to determine exactly *how* the scalpel was oriented or *where* to uniquely draw surgical incisions on the tissue. 

To create high-fidelity bounding models, we layered OpenCV `minAreaRect` logic on top of YOLO detections:
*   **The Scalpel Handle (Color-Banding):** We implemented HSV thresholding over the banana to find the scalpel handle. By defining high-saturation color masks (`color_mask` finding the vibrant purple, yellow, and cyan tape bands) and a low-saturation metallic mask (`silver_mask` finding the blade tip), we can perfectly segment the scalpel out of the frame regardless of its bounding box.
*   **Contour Elongation Filter:** To prevent false positives from background objects or hands, the mask output is filtered to only approve contours where the `minAreaRect` aspect ratio is $\ge 2.5:1$ (i.e. shaped like a scalpel).

### 2. Surgical Incision Tracing (`detect_red_rectangle`)
A red marker drawn directly onto the physical banana serves as the designated surgical zone.
*   We constrain the search space specifically to the bounding box produced by the YOLO `banana` detection for massive performance gains.
*   Using multi-range HSV masks, we extract red pixels (accounting for the red hue wrap-around at 0/180).
*   By calculating the `minAreaRect` center and projecting the absolute `boxPoints()`, the backend is able to send an exact topological rectangle (`ar_element` type: `polygon`) back to the frontend.

### 3. State Machine Orchestration (`DemoOrchestrator`)
The demo flow is rigidly enforced by a Python state machine to prevent UI jitter when a hand briefly occludes the camera. 
We implemented a 6-phase flow with debouncing:
*   **Phase 0 (Idle):** No UI elements except scanning.
*   **Phase 1 (Target Acquired):** Banana detected successfully. TTS prompt issued.
*   **Phase 2 (Tool Tracking):** Waiting for YOLO to acquire the `knife`.
*   **Phase 3 (Incision Mode):** The core interactive phase. As the scalpel nears the red incision zone, OpenCV computes the euclidean distance and relative approach angles. This emits a normalized `deviation` score.
*   **Phase 4 (Clamping):** After tracing completes, requesting that the scalpel be replaced by the clamps (`scissors`).
*   **Phase 5 (Complete):** Surgery finishes with a success HUD.

### 4. Zero-Latency Socket.IO 
Every processed frame `t` evaluates the state machine and broadcasts a high-frequency `frame_state` payload across WebSockets containing:
```json
{
  "phase": 3,
  "detections": [...],
  "ar_elements": [...],
  "voice_prompt": null,
  "warning": {"text": "Angle too steep", "status": -1} 
}
```

---

## Part 2: React Frontend AR Overlay (`surgeon-hud`)

### 1. Global State Management (`useHudStore.js`)
We constructed a Zustand store to handle incoming `frame_state` WebSocket packets from the Python backend. This removes UI computation lag entirely.

### 2. Progressive Declarative UI (`App.jsx`)
The frontend is built to be a totally transparent surgical viewfinder until the backend commands it otherwise. 
*   **`VoicePill.jsx`:** A "Dynamic Island" style drop-down pill that smoothly animates in sequentially to issue TTS (via ElevenLabs) voice prompts like *"Patient tissue detected."*
*   **`WarningBanner.jsx`:** High-contrast banners rendering red/amber warnings if the scalpel angle approaches occlusion limits.
*   **`AngleHUD.jsx`:** A Phase 3 dedicated UI that displays numeric approach angles based on backend CV deviation metrics.

### 3. SVG-Based AR Hardware Rendering (`AROverlay.jsx`)
To trace tracking lines between the scalpel and the target tissue with minimum render cost, we utilized `<svg>` DOM layers on top of the backend HTTP MJPEG video feed.
*   The SVG `viewBox="0 0 1 1"` allows plotting backend `ar_elements` (boxes, polygons, and point-to-point lines) using simple normalized `[0, 1]` coordinates, entirely bypassing CSS absolute positioning artifacts on viewport resize.
*   **Dynamic Hex Styling:** Trace line paths and surgical boxes calculate bounding colors dynamically. The backend outputs hex strings generated via `deviation_to_hex(t)` that shift the `stroke` rendering from solid green $\to$ neon yellow $\to$ red as the scalpel deviates from the ideal angle.
*   SVG `<filter>` tags were implemented to add a neon glow (blur+merge) to all overlay renders mimicking physical spatial headset software.
