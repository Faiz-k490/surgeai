import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useHudStore } from '../store/useHudStore';

const glowPulse = {
  animate: {
    textShadow: [
      '0 0 20px rgba(74, 222, 128, 0.3)',
      '0 0 60px rgba(74, 222, 128, 0.6)',
      '0 0 20px rgba(74, 222, 128, 0.3)',
    ],
    transition: { duration: 3, repeat: Infinity, ease: 'easeInOut' },
  },
};

const scanLine = {
  animate: {
    y: ['0vh', '100vh'],
    transition: { duration: 4, repeat: Infinity, ease: 'linear' },
  },
};

export default function BootScreen() {
  const { isBooted, setBooted } = useHudStore();
  const [initializing, setInitializing] = useState(false);

  const handleBoot = () => {
    setInitializing(true);
    setTimeout(() => setBooted(true), 600);
  };

  return (
    <AnimatePresence>
      {!isBooted && (
        <motion.div
          key="boot"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3, ease: 'easeInOut' }}
          className="fixed inset-0 z-[100] bg-black flex flex-col items-center justify-center overflow-hidden"
        >
          {/* Scan line effect */}
          <motion.div
            {...scanLine}
            className="absolute left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-green-500/20 to-transparent"
          />

          {/* Grid background */}
          <div className="absolute inset-0 opacity-[0.03]"
            style={{
              backgroundImage: 'linear-gradient(rgba(74,222,128,1) 1px, transparent 1px), linear-gradient(90deg, rgba(74,222,128,1) 1px, transparent 1px)',
              backgroundSize: '60px 60px',
            }}
          />

          {/* Logo */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className="flex flex-col items-center gap-2"
          >
            <motion.h1
              {...glowPulse}
              className="text-6xl font-bold tracking-[0.3em] text-green-400 font-mono"
            >
              SURGEON<span className="text-white/90">AI</span>
            </motion.h1>
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.4 }}
              transition={{ delay: 0.3, duration: 0.4 }}
              className="text-xs tracking-[0.5em] text-green-500/60 font-mono uppercase"
            >
              Augmented Surgical Intelligence
            </motion.p>
          </motion.div>

          {/* Divider */}
          <motion.div
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ delay: 0.4, duration: 0.4, ease: 'easeInOut' }}
            className="w-64 h-[1px] bg-gradient-to-r from-transparent via-green-500/40 to-transparent mt-12 mb-12"
          />

          {/* Boot button or initializing state */}
          {!initializing ? (
            <motion.button
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5, duration: 0.3 }}
              onClick={handleBoot}
              className="relative px-10 py-3 border border-green-500/50 text-green-400 font-mono text-sm tracking-[0.25em] uppercase
                         hover:bg-green-500/10 hover:border-green-400/70 hover:shadow-[0_0_30px_rgba(74,222,128,0.15)]
                         transition-all duration-300 cursor-pointer group"
            >
              <span className="relative z-10">Initialize System</span>
              <motion.div
                className="absolute inset-0 bg-green-500/5"
                animate={{ opacity: [0, 0.1, 0] }}
                transition={{ duration: 2, repeat: Infinity }}
              />
            </motion.button>
          ) : (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center gap-4"
            >
              {/* Loading bar */}
              <div className="w-64 h-[2px] bg-white/5 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: '0%' }}
                  animate={{ width: '100%' }}
                  transition={{ duration: 0.5, ease: 'easeInOut' }}
                  className="h-full bg-gradient-to-r from-green-500 to-green-400 rounded-full shadow-[0_0_10px_rgba(74,222,128,0.5)]"
                />
              </div>
              <motion.p
                animate={{ opacity: [0.3, 0.8, 0.3] }}
                transition={{ duration: 1.5, repeat: Infinity }}
                className="text-xs font-mono text-green-500/60 tracking-[0.3em]"
              >
                CALIBRATING SYSTEMS
              </motion.p>
            </motion.div>
          )}

          {/* Version tag */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.2 }}
            transition={{ delay: 2, duration: 1 }}
            className="absolute bottom-8 text-[10px] font-mono text-green-500/40 tracking-widest"
          >
            v0.1.0 — PROTOTYPE BUILD
          </motion.p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
