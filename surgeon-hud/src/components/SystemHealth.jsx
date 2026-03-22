import { useHudStore } from '../store/useHudStore';

export default function SystemHealth() {
  const {
    fps,
    latency,
    phase_name: healthPhaseName,
    runtime_state: healthRuntimeState,
    surgical_step: healthSurgicalStep,
    phaseName,
    session_id: healthSessionId,
    services,
  } = useHudStore((state) => state.systemMetrics);
  const fallbackPhaseName = useHudStore((state) => state.runtimeState);
  const fallbackSessionId = useHudStore((state) => state.sessionId);
  const fallbackSurgicalStep = useHudStore((state) => state.surgicalStep);
  const activePhase = healthRuntimeState || healthPhaseName || phaseName || fallbackPhaseName;
  const activeSessionId = healthSessionId || fallbackSessionId;
  const hasServiceWarning = Boolean(services?.last_error);
  const activeStep = healthSurgicalStep || fallbackSurgicalStep;

  return (
    <div className="absolute bottom-6 left-6 z-[15] flex flex-col items-start gap-1">
      <div className="px-3 py-1.5 rounded-lg bg-black/60 backdrop-blur-md border border-white/10">
        <p className="font-mono text-xs text-white/50 tracking-wider">
          SYS_FPS: <span className="text-white/80">{fps}</span> | LATENCY: <span className="text-white/80">{latency}ms</span>
        </p>
        <p className="mt-1 font-mono text-[10px] text-white/40 tracking-[0.2em] uppercase">
          {activePhase || 'IDLE'}
          {activeSessionId ? <span className="ml-2 text-white/25">SESSION {activeSessionId}</span> : null}
          {hasServiceWarning ? <span className="ml-2 text-amber-400/80">SERVICE DEGRADED</span> : null}
        </p>
        <p className="mt-1 font-mono text-[10px] text-white/25 tracking-[0.18em] uppercase">
          STEP {String(activeStep || 'scene_setup').replaceAll('_', ' ')}
        </p>
      </div>
    </div>
  );
}
