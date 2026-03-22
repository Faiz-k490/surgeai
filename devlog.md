# Development Log: Gemini Narrator & SmartCropper Stability 🚀

This log documents the major changes, fixes, and features added to `simulate_demo.py` and the vision pipeline during this branch. These notes are structured to serve as context for the eventual merge back to `main`.

## 1. Real-Time Gemini Narrator Thread
- **Feature:** Added a dedicated `--narrate` background thread in `simulate_demo.py` to stream real-time surgical scene awareness.
- **Implementation:** Grabs the current 512x512 cropped frame from `SmartCropper` every 10 seconds and sends it to the `GeminiVisionClient`.
- **Mitigating Restrictions:** Initially built for 1 FPS, but encountered Google API Free Tier `429 RESOURCE_EXHAUSTED` quotas. Backed off to a 10-second request interval (6 RPM) to reliably stay within standard free tier quotas. 
- **Model Flexibility:** Updated the Gemini client to respect `settings.gemini_model` instead of hardcoding `gemini-2.0-flash`. Added a `--model` CLI override to allow developers to hot-swap to different models (e.g. `gemini-1.5-flash`) dynamically if they run out of AI Studio credits.

## 2. Audio Text-to-Speech (TTS) Pipeline Fixes
- **Feature:** Hooked the VLM text output into the `tts_pipeline.speak()` function to stream auditory feedback.
- **Bug Fix (Windows COM Deadlocks):** We discovered that running `pyttsx3` inside a Flask daemon thread would completely silently freeze the entire Python GIL due to an uninitialized Windows SAPI5 COM object. 
- **Resolution:** Manually added Windows interop initialization (`import pythoncom; pythoncom.CoInitialize()`) at the start of the narrator thread, allowing the background thread to interface safely with system audio without locking up the MJPEG server.

## 3. MJPEG Feed Thread-Safety
- **Bug:** The visual `/video` stream was hanging inside the Flask WSGI server whenever `--narrate` was active.
- **Root Cause:** A heavy race condition. Both the `generate_mjpeg` loop and the new `narrator_thread` were calling `cropper.detect_and_crop()` concurrently. Since the `SmartCropper` is stateful (maintains internal Exponential Moving Averages), concurrent math operations corrupted the crop variables and crashed OpenCV.
- **Resolution:** Introduced a generic `cropper_lock = threading.Lock()` around all `detect_and_crop()` operations inside `simulate_demo.py`.

## 4. SmartCropper "Lock-In" Hysteresis
- **Bug:** The "banana zoom" feature suffered from a severe "bobbing in and out" effect due to YOLO jitter and randomly dropped frames.
- **Resolution - 2-Second Hold:** Rewrote the state logic inside `smart_crop.py` to include a missed-frame counter (`_missed_frames`). If the YOLO threshold fails, the cropper enters a "patience" hold, remembering the exact target coordinates for up to 60 frames (2 seconds) before throwing in the towel and zooming out.
- **Resolution - Smoothing:** Tweaked `ema_alpha` from an aggressive `0.30` down to `0.08`. The bounding box tracking now gracefully glides to new positions, feeling much more cinematic, stable, and forgiving instead of rigidly bouncing inside the frame. 

## 5. Multiple Camera Configuration
- **Feature:** Realized that developer setups often mount multiple cameras. Added a robust `--list-cameras` argument to scan indices `0-9` via OpenCV and print their availability.
- **Feature:** Added a `--camera <idx>` argument to securely force the backend to bind to a specific internal/external webcam.

## 6. ElevenLabs Conversational Audio Q&A
- **Feature (Strict Medical Persona):** Extracted the generic conversational prompt in `intelligence_pipeline.py` and replaced it with a highly detailed, clinical mentor persona that forces the audio loop to treat the tracking UI ("banana", "red marker line") with absolute medical seriousness and rapid brevity.
- **Bug Fix (Missing Audio):** Discovered that the synchronous Q&A loop in `loop_a_service` was hooked into the legacy `speak()` function, which completely bypassed ElevenLabs and defaulted to robotic `pyttsx3`. Rewrote `speak()` within `tts_pipeline.py` to gracefully spawn an ephemeral `asyncio` event loop so it can harness the high-performance WebSocket streaming pipeline inside synchronous threads.
- **Bug Fix (Authentication 1008):** Fixed a silent authentication failure preventing ElevenLabs from returning the audio payload. Updated the WebSocket BOS (beginning of stream) message to properly inject the `xi_api_key` directly into the JSON.
- **Development Tool:** Created the `test_elevenlabs.py` standalone sandbox to allow for isolated audio subsystem debugging without bleeding Gemini or Groq API quotas.
