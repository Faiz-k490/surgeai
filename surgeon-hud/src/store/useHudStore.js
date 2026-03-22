import { create } from 'zustand';

export const useHudStore = create((set) => ({
  // Connection
  isConnected: false,
  isBooted: false,

  // 6-phase state machine
  phase: 0,
  voicePrompt: null,
  warning: null,
  arElements: [],
  angleData: null,

  // Metrics
  systemMetrics: { fps: 0, latency: 0 },

  // Actions
  setIsConnected: (status) => set({ isConnected: status }),
  setBooted: (val) => set({ isBooted: val }),
  setPhase: (p) => set({ phase: p }),
  setVoicePrompt: (vp) => set({ voicePrompt: vp }),
  clearVoicePrompt: () => set({ voicePrompt: null }),
  setWarning: (w) => set({ warning: w }),
  setARElements: (els) => set({ arElements: els }),
  setAngleData: (a) => set({ angleData: a }),
  setMetrics: (m) => set({ systemMetrics: m }),

  // Batch update from frame_state
  applyFrameState: (state) => set({
    phase: state.current_phase ?? 0,
    voicePrompt: state.voice_prompt || null,
    warning: state.warning || null,
    arElements: state.ar_elements || [],
    angleData: state.angle_data || null,
  }),
}));
