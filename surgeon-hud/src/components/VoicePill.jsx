import { useEffect, useRef, useCallback, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useHudStore } from '../store/useHudStore';

/**
 * Dynamic Island style Voice Pill — positioned at TOP CENTER.
 * Drops down when voice_prompt is received, speaks it via Web Speech API,
 * and auto-hides after 6 seconds.
 */

export default function VoicePill() {
  const voicePrompt = useHudStore((s) => s.voicePrompt);
  const [displayText, setDisplayText] = useState(null);
  const [waveData, setWaveData] = useState(Array(20).fill(0.1));
  const hideTimerRef = useRef(null);
  const lastSpokenRef = useRef('');

  // Speak via Web Speech API
  const speak = useCallback((text) => {
    if (!text || !window.speechSynthesis) return;
    // Cancel any ongoing speech
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.95;
    utterance.pitch = 0.9;
    utterance.volume = 1.0;
    // Try to pick a natural-sounding voice
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(
      (v) => v.name.includes('Samantha') || v.name.includes('Google') || v.name.includes('Daniel')
    );
    if (preferred) utterance.voice = preferred;
    window.speechSynthesis.speak(utterance);
  }, []);

  // When voicePrompt arrives, show pill and speak
  useEffect(() => {
    if (!voicePrompt || voicePrompt === lastSpokenRef.current) return;

    lastSpokenRef.current = voicePrompt;
    setDisplayText(voicePrompt);
    speak(voicePrompt);

    // Clear any existing hide timer
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    hideTimerRef.current = setTimeout(() => setDisplayText(null), 6000);

    return () => {
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    };
  }, [voicePrompt, speak]);

  // Animate waveform while visible
  useEffect(() => {
    if (!displayText) return;
    const interval = setInterval(() => {
      setWaveData(Array.from({ length: 20 }, () => Math.max(0.1, Math.random())));
    }, 80);
    return () => clearInterval(interval);
  }, [displayText]);

  return (
    <div className="absolute top-6 left-0 right-0 flex justify-center z-40 pointer-events-none">
      <AnimatePresence mode="wait">
        {displayText ? (
          <motion.div
            key="pill-expanded"
            initial={{ width: 12, height: 12, opacity: 0, borderRadius: 9999, y: -30 }}
            animate={{ width: 'auto', height: 'auto', opacity: 1, borderRadius: 24, y: 0 }}
            exit={{ width: 12, height: 12, opacity: 0, borderRadius: 9999, y: -30 }}
            transition={{ type: 'spring', stiffness: 260, damping: 25 }}
            className="max-w-lg bg-black/60 backdrop-blur-2xl border border-white/10 shadow-[0_8px_40px_rgba(0,0,0,0.6)] px-5 py-3 flex items-center gap-4 overflow-hidden"
          >
            {/* Waveform */}
            <div className="w-14 h-7 shrink-0 flex items-center gap-[2px]">
              {waveData.map((v, i) => (
                <motion.div
                  key={i}
                  animate={{ height: `${Math.max(15, v * 100)}%` }}
                  transition={{ duration: 0.08 }}
                  className="w-[2px] rounded-full bg-cyan-400"
                />
              ))}
            </div>

            {/* Divider */}
            <div className="w-[1px] h-5 bg-white/10 shrink-0" />

            {/* Text */}
            <p className="text-sm font-medium text-white/90 leading-snug line-clamp-2">
              {displayText}
            </p>
          </motion.div>
        ) : (
          <motion.div
            key="pill-dot"
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="w-2.5 h-2.5 rounded-full bg-white/20 border border-white/10"
          >
            <motion.div
              animate={{ scale: [1, 1.8, 1], opacity: [0.3, 0.05, 0.3] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              className="w-full h-full rounded-full bg-white/30"
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
