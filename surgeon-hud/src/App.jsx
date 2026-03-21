import { AnimatePresence, motion } from 'framer-motion';
import { useHudStore } from './store/useHudStore';
import SocketManager from './providers/SocketManager';
import BootScreen from './components/BootScreen';
import VideoBackground from './components/VideoBackground';
import StepTracker from './components/StepTracker';
import SystemHealth from './components/SystemHealth';
import StatusBanner from './components/StatusBanner';
import AROverlay from './components/AROverlay';
import QAPanel from './components/QAPanel';
import ConnectionFallback from './components/ConnectionFallback';

function App() {
  const isBooted = useHudStore((s) => s.isBooted);

  return (
    <SocketManager>
      <main className="relative w-screen h-screen overflow-hidden bg-black">
        {/* Z-100: Boot Sequence */}
        <BootScreen />

        {/* Main HUD — fades in after boot */}
        <AnimatePresence>
          {isBooted && (
            <motion.div
              key="hud"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              className="absolute inset-0"
            >
              {/* Z-0: Live Video Feed */}
              <VideoBackground />

              {/* Z-10: Telemetry Overlays */}
              <div className="relative z-10">
                <StepTracker />
                <SystemHealth />
              </div>

              {/* Z-20: AR Bounding Boxes (VLM) */}
              <AROverlay />

              {/* Z-30: Hazard Warnings */}
              <div className="relative z-30">
                <StatusBanner />
              </div>

              {/* Z-40: Voice Pill */}
              <QAPanel />

              {/* Z-100: Connection Fallback */}
              <ConnectionFallback />
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </SocketManager>
  );
}

export default App
