import { motion, AnimatePresence } from 'framer-motion';
import { useHudStore } from '../store/useHudStore';

export default function StatusBanner() {
  const warning = useHudStore((state) => state.activeWarning);

  return (
    <div className="absolute top-8 left-0 right-0 flex justify-center z-50 pointer-events-none">
      <AnimatePresence>
        {warning && (
          <motion.div
            initial={{ y: -100, opacity: 0, scale: 0.95 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: -50, opacity: 0, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 400, damping: 25 }}
            className="px-8 py-4 bg-red-900/60 backdrop-blur-md border border-red-500 rounded-2xl shadow-[0_0_40px_rgba(239,68,68,0.6)]"
          >
            <div className="flex items-center gap-4">
              <span className="text-3xl animate-pulse">⚠️</span>
              <h1 className="text-2xl font-bold text-red-100 uppercase tracking-widest">
                {warning}
              </h1>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
