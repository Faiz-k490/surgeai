import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useHudStore } from '../store/useHudStore';

function stateCopy(runtimeState) {
  switch (runtimeState) {
    case 'LISTENING':
      return 'Listening...';
    case 'THINKING':
      return 'Analyzing the scene...';
    case 'SPEAKING':
      return 'Speaking';
    case 'DEGRADED':
      return 'Voice degraded';
    default:
      return "Say 'Hey Surgeon' or press Talk";
  }
}

export default function VoicePill() {
  const runtimeState = useHudStore((s) => s.runtimeState);
  const voicePrompt = useHudStore((s) => s.voicePrompt);
  const micPermission = useHudStore((s) => s.micPermission);
  const requestManualCapture = useHudStore((s) => s.requestManualCapture);
  const [waveData, setWaveData] = useState(Array(20).fill(0.12));

  useEffect(() => {
    if (runtimeState !== 'LISTENING' && runtimeState !== 'SPEAKING') return undefined;
    const interval = window.setInterval(() => {
      setWaveData(Array.from({ length: 20 }, () => Math.max(0.12, Math.random())));
    }, 80);
    return () => window.clearInterval(interval);
  }, [runtimeState]);

  return (
    <div className="absolute top-6 left-0 right-0 z-40 flex justify-center px-4">
      <motion.div
        initial={{ y: -24, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="pointer-events-auto flex w-full max-w-2xl items-center gap-4 rounded-[28px] border border-white/10 bg-black/65 px-5 py-3 shadow-[0_10px_40px_rgba(0,0,0,0.45)] backdrop-blur-2xl"
      >
        <div className="flex h-8 w-16 shrink-0 items-center gap-[2px]">
          {waveData.map((value, index) => (
            <motion.div
              key={index}
              animate={{ height: `${Math.max(18, value * 100)}%` }}
              transition={{ duration: 0.08 }}
              className={`w-[2px] rounded-full ${runtimeState === 'DEGRADED' ? 'bg-amber-400' : 'bg-cyan-400'}`}
            />
          ))}
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-mono uppercase tracking-[0.24em] text-white/45">
            {stateCopy(runtimeState)}
          </p>
          <AnimatePresence mode="wait">
            <motion.p
              key={voicePrompt || runtimeState}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="mt-1 line-clamp-2 text-sm text-white/90"
            >
              {voicePrompt || (micPermission === 'denied'
                ? 'Enable microphone access to use wake word or press-to-talk.'
                : "Wake phrase: 'Hey Surgeon, what do I do next?'")}
            </motion.p>
          </AnimatePresence>
        </div>

        <button
          type="button"
          onClick={() => requestManualCapture()}
          className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-[11px] font-mono uppercase tracking-[0.18em] text-cyan-200 transition hover:bg-cyan-400/20"
        >
          Talk
        </button>
      </motion.div>
    </div>
  );
}
