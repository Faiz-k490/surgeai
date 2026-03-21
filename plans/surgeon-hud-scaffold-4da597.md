# Surgeon HUD Frontend Scaffold

Create the full React frontend for the SurgeonAI HUD inside `/Users/faizan/surgeai/surgeon-hud`.

## Phase 0: Project Scaffold & Config
1. Run `npm create vite@latest surgeon-hud -- --template react` from `/Users/faizan/surgeai`
2. Install runtime deps: `socket.io-client zustand framer-motion @elevenlabs/react-ui`
3. Install dev deps: `tailwindcss postcss autoprefixer`
4. Run `npx tailwindcss init -p`
5. Update `tailwind.config.js` with `hud-black` color and content globs
6. Replace `src/index.css` with Tailwind directives + HUD body styles (no scroll, black bg)
7. Create `.windsurfrules` in project root with Anti-Gravity aesthetic rules

## Phase 1–2: Store, Video Feed & Socket Manager
8. Create `src/store/useHudStore.js` — Zustand store with `currentStep`, `activeWarning`, `latestQA`, `systemMetrics` + setters
9. Create `src/components/VideoBackground.jsx` — absolute-positioned `<img>` pointing to `http://localhost:5000/video`, z-index 0
10. Create `src/providers/SocketManager.jsx` — connects to `http://localhost:5000/realtime`, maps socket events to Zustand actions

## Phase 3: Anti-Gravity HUD Overlays
11. Create `src/components/StepTracker.jsx` — top-left, green text, glassmorphism panel
12. Create `src/components/SystemHealth.jsx` — bottom-right, monospace metrics display
13. Create `src/components/StatusBanner.jsx` — top-center, framer-motion AnimatePresence drop-down with red glow on warning
14. Create `src/components/QAPanel.jsx` — bottom-center, displays `latestQA`, includes ElevenLabs Waveform

## Phase 4: Assembly
15. Rewrite `src/App.jsx` — wrap in SocketManager, render VideoBackground at z-0, overlay all HUD components
16. Clean up default Vite files (`src/App.css`, `src/assets/react.svg`) if present
17. Verify with `npm run dev`
