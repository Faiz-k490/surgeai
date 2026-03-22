import { AnimatePresence, motion } from 'framer-motion';
import { useState } from 'react';
import { useHudStore } from './store/useHudStore';
import SocketManager from './providers/SocketManager';
import VideoBackground from './components/VideoBackground';
import SystemHealth from './components/SystemHealth';
import AROverlay from './components/AROverlay';
import VoicePill from './components/VoicePill';
import ConnectionFallback from './components/ConnectionFallback';
import LandingPage from './components/LandingPage';


// ── Phase 0: Scanning Dot ──────────────────────────────────────────────────
function ScanningDot() {
  const phase = useHudStore((s) => s.phase);
  if (phase !== 0) return null;
  return (
    <div className="absolute bottom-10 left-0 right-0 flex justify-center z-10 pointer-events-none">
      <div className="flex items-center gap-2">
        <motion.div
          animate={{ scale: [1, 1.4, 1], opacity: [0.5, 0.15, 0.5] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          className="w-2 h-2 rounded-full bg-white/40"
        />
        <span className="text-[11px] font-mono tracking-[0.25em] text-white/30 uppercase">
          Scanning
        </span>
      </div>
    </div>
  );
}


// ── Angle HUD (Always Visible) ────────────────────────────────────────────
function AngleHUD() {
  const angleData = useHudStore((s) => s.angleData);

  const isIdle = !angleData || angleData.status === 'idle';
  const isOptimal = !isIdle && angleData.status === 'Optimal';
  const glow = isIdle ? '#ffffff' : isOptimal ? '#22c55e' : '#ef4444';

  return (
    <div
      className="absolute bottom-5 right-5 z-20 pointer-events-none"
    >
      <div
        className="px-6 py-3 rounded-2xl border backdrop-blur-xl flex items-center gap-4"
        style={{
          backgroundColor: 'rgba(0,0,0,0.5)',
          borderColor: isIdle ? 'rgba(255,255,255,0.1)' : `${glow}33`,
          boxShadow: isIdle ? 'none' : `0 0 30px ${glow}22`,
        }}
      >
        <span className="text-[10px] font-mono tracking-[0.2em] text-white/40 uppercase">
          Approach
        </span>
        {isIdle ? (
          <span className="text-sm font-mono tracking-wider text-white/30">
            Waiting for scalpel…
          </span>
        ) : (
          <>
            <span
              className="text-3xl font-mono font-bold tabular-nums"
              style={{ color: glow, textShadow: `0 0 14px ${glow}88` }}
            >
              {angleData.approach_angle}°
            </span>
            <span
              className="text-[10px] font-mono tracking-wider uppercase px-2 py-0.5 rounded-full border"
              style={{
                color: glow,
                borderColor: `${glow}44`,
                backgroundColor: `${glow}11`,
              }}
            >
              {angleData.status}
            </span>
          </>
        )}
      </div>
    </div>
  );
}


// ── Warning Banner ─────────────────────────────────────────────────────────
function WarningBanner() {
  const warning = useHudStore((s) => s.warning);
  return (
    <AnimatePresence>
      {warning && (
        <motion.div
          key="warning"
          initial={{ y: -100, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -100, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 25 }}
          className="absolute top-0 left-0 right-0 z-30 pointer-events-none"
        >
          <div className="mx-auto max-w-2xl mt-20 px-6 py-4 rounded-2xl border border-red-500/30 bg-red-950/60 backdrop-blur-xl shadow-[0_0_60px_rgba(239,68,68,0.25)]">
            <div className="flex items-center gap-3">
              {/* Pulsing red dot */}
              <motion.div
                animate={{ scale: [1, 1.3, 1], opacity: [1, 0.5, 1] }}
                transition={{ duration: 0.6, repeat: Infinity }}
                className="w-3 h-3 rounded-full bg-red-500 shrink-0"
              />
              <p className="text-red-300 font-mono text-sm font-bold tracking-wide uppercase">
                {warning}
              </p>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}


// ── Phase 5: Surgery Complete ──────────────────────────────────────────────
function SurgeryComplete() {
  const surgicalStep = useHudStore((s) => s.surgicalStep);
  const arElements = useHudStore((s) => s.arElements);

  const showOverlay = surgicalStep === 'complete' || arElements.some((el) => el.type === 'success_overlay');
  if (!showOverlay) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 1, ease: 'easeOut' }}
      className="absolute inset-0 z-50 flex items-center justify-center pointer-events-none"
    >
      {/* Frosted overlay */}
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />

      <motion.div
        initial={{ scale: 0.7, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 0.3, type: 'spring', stiffness: 200, damping: 20 }}
        className="relative flex flex-col items-center gap-6"
      >
        {/* Success ring */}
        <motion.div
          animate={{
            boxShadow: [
              '0 0 30px rgba(34,197,94,0.2)',
              '0 0 80px rgba(34,197,94,0.5)',
              '0 0 30px rgba(34,197,94,0.2)',
            ],
          }}
          transition={{ duration: 2, repeat: Infinity }}
          className="w-24 h-24 rounded-full border-2 border-green-400/60 flex items-center justify-center"
        >
          <svg className="w-12 h-12 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <motion.path
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ delay: 0.5, duration: 0.6, ease: 'easeOut' }}
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M5 13l4 4L19 7"
            />
          </svg>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8 }}
          className="text-4xl font-bold font-mono tracking-[0.3em] text-green-400"
          style={{ textShadow: '0 0 40px rgba(34,197,94,0.5)' }}
        >
          SURGERY SUCCESSFUL
        </motion.h1>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.5 }}
          transition={{ delay: 1.2 }}
          className="text-sm font-mono tracking-[0.2em] text-white/40 uppercase"
        >
          Procedure Complete — All Vitals Normal
        </motion.p>
      </motion.div>
    </motion.div>
  );
}

function GuidanceRibbon() {
  const nextStepHint = useHudStore((s) => s.nextStepHint);
  const surgicalStep = useHudStore((s) => s.surgicalStep);
  const transcriptPreview = useHudStore((s) => s.transcriptPreview);

  return (
    <div className="absolute left-0 right-0 bottom-28 z-20 flex justify-center px-4 pointer-events-none md:bottom-32">
      <div className="w-full max-w-3xl rounded-2xl border border-white/10 bg-black/55 px-5 py-3 backdrop-blur-xl">
        <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-300/75">
          {surgicalStep.replaceAll('_', ' ')}
        </p>
        <p className="mt-1 text-sm text-white/85">{nextStepHint}</p>
        {transcriptPreview ? (
          <p className="mt-2 text-xs font-mono text-white/35">Last heard: {transcriptPreview}</p>
        ) : null}
      </div>
    </div>
  );
}


// ── App ────────────────────────────────────────────────────────────────────
function App() {
  const isBooted = useHudStore((s) => s.isBooted);
  const setBooted = useHudStore((s) => s.setBooted);
  const requestActivation = useHudStore((s) => s.requestActivation);
  const [showLanding, setShowLanding] = useState(true);

  return (
    <>
      {/* Landing page — full-screen, shown until user clicks CTA */}
      <AnimatePresence>
        {showLanding && (
          <LandingPage onEnter={() => {
            setShowLanding(false);
            setBooted(true);
            requestActivation();
          }} />
        )}
      </AnimatePresence>

      {/* HUD system — mounted once landing exits */}
      {!showLanding && (
        <SocketManager>
          <main className="relative w-screen h-screen overflow-hidden bg-black">
            <AnimatePresence>
              {isBooted && (
                <motion.div
                  key="hud"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.2, ease: 'easeOut' }}
                  className="absolute inset-0"
                >
                  {/* Z-0: Live Video Feed (MJPEG from backend) */}
                  <VideoBackground />

                  {/* Z-5: Scanning dot (Phase 0 only) */}
                  <ScanningDot />

                  {/* Z-10: AR Overlay (SVG boxes/polygons/lines) */}
                  <AROverlay />

                  {/* Z-15: FPS / Latency readout */}
                  <div className="relative z-[15]">
                    <SystemHealth />
                  </div>

                  {/* Z-20: Angle HUD (ALWAYS visible — shows idle state outside Phase 3) */}
                  <AngleHUD />

                  {/* Z-30: Warning Banner */}
                  <WarningBanner />

                  {/* Z-40: Voice Pill (Dynamic Island, TOP) */}
                  <VoicePill />

                  {/* Z-45: Guidance Ribbon */}
                  <GuidanceRibbon />

                  {/* Z-50: Surgery Complete */}
                  <SurgeryComplete />

                  {/* Z-100: Connection Fallback */}
                  <ConnectionFallback />
                </motion.div>
              )}
            </AnimatePresence>
          </main>
        </SocketManager>
      )}
    </>
  );
}

export default App;

