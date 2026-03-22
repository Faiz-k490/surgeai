import { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useHudStore } from '../store/useHudStore';

function statusLabel(clientVoiceState, runtimeState) {
  if (clientVoiceState === 'complete' || runtimeState === 'COMPLETE') return 'Session complete';
  if (clientVoiceState === 'wake') return 'Wake phrase detected';
  if (clientVoiceState === 'listening') return 'Listening for your command';
  if (clientVoiceState === 'thinking' || runtimeState === 'THINKING') return 'Analyzing the scene';
  if (clientVoiceState === 'speaking' || runtimeState === 'SPEAKING') return 'Responding';
  if (runtimeState === 'DEGRADED' || clientVoiceState === 'error') return 'Voice degraded';
  if (clientVoiceState === 'unsupported') return 'Speech recognition unavailable';
  return "Always listening for 'Hey Surgeon'";
}

function orbTone(clientVoiceState, runtimeState) {
  if (clientVoiceState === 'complete' || runtimeState === 'COMPLETE') {
    return {
      glow: 'rgba(74,222,128,0.55)',
      border: 'rgba(74,222,128,0.82)',
      fill: 'rgba(74,222,128,0.24)',
    };
  }
  if (runtimeState === 'DEGRADED' || clientVoiceState === 'error') {
    return {
      glow: 'rgba(245,158,11,0.55)',
      border: 'rgba(245,158,11,0.7)',
      fill: 'rgba(245,158,11,0.28)',
    };
  }
  if (clientVoiceState === 'wake' || clientVoiceState === 'listening') {
    return {
      glow: 'rgba(34,211,238,0.65)',
      border: 'rgba(34,211,238,0.9)',
      fill: 'rgba(34,211,238,0.32)',
    };
  }
  if (clientVoiceState === 'thinking' || runtimeState === 'THINKING') {
    return {
      glow: 'rgba(96,165,250,0.55)',
      border: 'rgba(96,165,250,0.8)',
      fill: 'rgba(96,165,250,0.26)',
    };
  }
  if (clientVoiceState === 'speaking' || runtimeState === 'SPEAKING') {
    return {
      glow: 'rgba(74,222,128,0.55)',
      border: 'rgba(74,222,128,0.8)',
      fill: 'rgba(74,222,128,0.26)',
    };
  }
  return {
    glow: 'rgba(255,255,255,0.28)',
    border: 'rgba(255,255,255,0.42)',
    fill: 'rgba(255,255,255,0.14)',
  };
}

export default function VoicePill() {
  const runtimeState = useHudStore((s) => s.runtimeState);
  const clientVoiceState = useHudStore((s) => s.clientVoiceState);
  const voicePrompt = useHudStore((s) => s.voicePrompt);
  const micPermission = useHudStore((s) => s.micPermission);
  const transcriptPreview = useHudStore((s) => s.transcriptPreview);
  const sessionTerminated = useHudStore((s) => s.sessionTerminated);
  const [waveData, setWaveData] = useState(Array(16).fill(0.12));

  const tone = useMemo(() => orbTone(clientVoiceState, runtimeState), [clientVoiceState, runtimeState]);
  const label = statusLabel(clientVoiceState, runtimeState);

  useEffect(() => {
    const activeStates = new Set(['wake', 'listening', 'thinking', 'speaking']);
    const isActive = activeStates.has(clientVoiceState) || runtimeState === 'SPEAKING' || runtimeState === 'THINKING';
    if (!isActive) return undefined;

    const interval = window.setInterval(() => {
      setWaveData(Array.from({ length: 16 }, () => Math.max(0.12, Math.random())));
    }, 90);
    return () => window.clearInterval(interval);
  }, [clientVoiceState, runtimeState]);

  return (
    <>
      <div className="absolute top-6 left-0 right-0 z-40 flex justify-center px-4 pointer-events-none">
        <motion.div
          initial={{ y: -18, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="w-full max-w-xl rounded-[24px] border border-white/10 bg-black/65 px-5 py-3 shadow-[0_10px_40px_rgba(0,0,0,0.45)] backdrop-blur-2xl"
        >
          <p className="text-[10px] font-mono uppercase tracking-[0.24em] text-white/45">{label}</p>
          <AnimatePresence mode="wait">
            <motion.p
              key={`${voicePrompt || transcriptPreview || micPermission || label}`}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="mt-1 line-clamp-2 text-sm text-white/90"
            >
              {voicePrompt
                || (sessionTerminated ? 'Great job! Session complete.' : null)
                || transcriptPreview
                || (micPermission === 'denied'
                  ? 'Microphone permission was denied. Browser TTS fallback will still work.'
                  : "Say 'Hey Surgeon' to ask for guidance.")}
            </motion.p>
          </AnimatePresence>
        </motion.div>
      </div>

      <div className="absolute bottom-8 left-[58%] z-40 flex -translate-x-1/2 justify-center pointer-events-none md:left-[60%]">
        <div className="relative flex flex-col items-center gap-3">
          <motion.div
            animate={{
              scale: clientVoiceState === 'wake' || clientVoiceState === 'listening' ? [1, 1.08, 1] : [1, 1.03, 1],
              boxShadow: [
                `0 0 24px ${tone.glow}`,
                `0 0 40px ${tone.glow}`,
                `0 0 24px ${tone.glow}`,
              ],
            }}
            transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
            className="flex h-20 w-20 items-center justify-center rounded-full border backdrop-blur-xl"
            style={{
              borderColor: tone.border,
              backgroundColor: tone.fill,
            }}
          >
            <div className="flex h-8 items-end gap-[3px]">
              {waveData.map((value, index) => (
                <motion.div
                  key={index}
                  animate={{ height: `${Math.max(20, value * 100)}%` }}
                  transition={{ duration: 0.1 }}
                  className="w-[3px] rounded-full bg-white/90"
                />
              ))}
            </div>
          </motion.div>

          <p className="rounded-full border border-white/10 bg-black/55 px-4 py-1 text-[10px] font-mono uppercase tracking-[0.2em] text-white/65 backdrop-blur-xl">
            Hey Surgeon
          </p>
        </div>
      </div>
    </>
  );
}
