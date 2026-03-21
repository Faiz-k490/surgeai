# Chunk 3 and 4 HUD Alignment

Align the current `surgeon-hud` implementation to the requested Chunk 3 (video base layer) and Chunk 4 (static anti-gravity overlays) outputs with minimal, targeted edits.

## Current State (from review)
- `VideoBackground.jsx` already avoids Zustand but uses `memo`, `inset-0`, and alt text differs from requested snippet.
- `StepTracker.jsx` and `SystemHealth.jsx` currently include `framer-motion`; requested Chunk 4 versions are static (non-animated).
- `App.jsx` currently includes `StatusBanner` and `QAPanel`; requested mid-point assembly excludes those and keeps only `VideoBackground`, `StepTracker`, and `SystemHealth`.

## Planned Implementation Steps
1. Update `src/components/VideoBackground.jsx` to the requested static full-screen image markup (`top-0 left-0 w-screen h-screen object-cover z-0`) with no Zustand subscription.
2. Update `src/components/StepTracker.jsx` to the requested static top-left glassmorphism block subscribed only to `currentStep`.
3. Update `src/components/SystemHealth.jsx` to the requested static bottom-right monospace metrics block subscribed to `systemMetrics`.
4. Update `src/App.jsx` to the requested mid-point assembly with `SocketManager`, `VideoBackground`, `StepTracker`, and `SystemHealth` only.
5. Run a quick `npm run build` verification and report results.

## Clarification To Confirm During Execution
- Treat this as a strict rollback to Chunk 3/4 midpoint (remove `StatusBanner` and `QAPanel` from `App.jsx`) as shown in the provided target snippet.
