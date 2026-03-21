import { useHudStore } from '../store/useHudStore';

export default function SystemHealth() {
  const { fps, latency } = useHudStore((state) => state.systemMetrics);

  return (
    <div className="absolute bottom-6 right-6 z-10 flex flex-col items-end gap-1">
      <div className="px-3 py-1.5 rounded-lg bg-black/60 backdrop-blur-md border border-white/10">
        <p className="font-mono text-xs text-white/50 tracking-wider">
          SYS_FPS: <span className="text-white/80">{fps}</span> | LATENCY: <span className="text-white/80">{latency}ms</span>
        </p>
      </div>
    </div>
  );
}
