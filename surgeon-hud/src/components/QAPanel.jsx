import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useHudStore } from '../store/useHudStore';

function MiniWaveform({ data }) {
  return (
    <div className="flex items-center h-full gap-[2px]">
      {data.map((value, i) => (
        <motion.div
          key={i}
          animate={{ height: `${Math.max(15, value * 100)}%` }}
          transition={{ duration: 0.1, ease: 'linear' }}
          className="w-[2px] rounded-full bg-cyan-400"
        />
      ))}
    </div>
  );
}

export default function QAPanel() {
  const { latestQA, setQA } = useHudStore();
  const [waveData, setWaveData] = useState(Array(24).fill(0.1));

  useEffect(() => {
    if (latestQA) {
      const timer = setTimeout(() => setQA(null), 10000);
      return () => clearTimeout(timer);
    }
  }, [latestQA, setQA]);

  useEffect(() => {
    if (!latestQA) return;
    const interval = setInterval(() => {
      setWaveData(Array.from({ length: 24 }, () => Math.max(0.1, Math.random())));
    }, 80);
    return () => clearInterval(interval);
  }, [latestQA]);

  return (
    <div className="absolute bottom-8 left-0 right-0 flex justify-center z-40 pointer-events-none">
      <AnimatePresence mode="wait">
        {latestQA ? (
          <motion.div
            key="pill-expanded"
            initial={{ width: 48, height: 48, opacity: 0, borderRadius: 9999 }}
            animate={{ width: 'auto', height: 'auto', opacity: 1, borderRadius: 28 }}
            exit={{ width: 48, height: 48, opacity: 0, borderRadius: 9999 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="max-w-xl bg-black/50 backdrop-blur-2xl border border-white/10 shadow-[0_8px_40px_rgba(0,0,0,0.5)] px-5 py-3 flex items-center gap-4 overflow-hidden"
          >
            {/* Waveform */}
            <div className="w-16 h-8 shrink-0">
              <MiniWaveform data={waveData} />
            </div>

            {/* Divider */}
            <div className="w-[1px] h-6 bg-white/10 shrink-0" />

            {/* Answer text */}
            <div className="flex flex-col gap-1 min-w-0">
              <p className="text-sm font-medium text-white/90 leading-snug line-clamp-3">
                {latestQA.answer}
              </p>
              {latestQA.question && (
                <p className="text-[11px] text-white/40 truncate">
                  "{latestQA.question}"
                </p>
              )}
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="pill-dot"
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="w-3 h-3 rounded-full bg-cyan-400/30 border border-cyan-400/20"
          >
            <motion.div
              animate={{ scale: [1, 1.5, 1], opacity: [0.4, 0.1, 0.4] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              className="w-full h-full rounded-full bg-cyan-400/40"
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
