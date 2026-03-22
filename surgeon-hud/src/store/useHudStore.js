import { create } from 'zustand';

export const useHudStore = create((set) => ({
  // Connection
  isConnected: false,
  isBooted: false,
  activationRequested: false,
  micPermission: 'prompt',
  clientVoiceState: 'passive',

  // Backend-owned workflow state
  phase: 0,
  phaseName: 'IDLE',
  runtimeState: 'IDLE',
  surgicalStep: 'scene_setup',
  sessionId: null,
  voicePrompt: null,
  voiceEventId: null,
  voiceAudioUrl: null,
  warning: null,
  countdownSeconds: null,
  arElements: [],
  angleData: null,
  nextStepHint: 'Activate SurgeAI to begin.',
  listeningState: 'idle',
  transcriptPreview: null,
  sceneEvents: [],
  services: {},
  sessionTerminated: false,

  // Metrics
  systemMetrics: {
    fps: 0,
    latency: 0,
    phaseName: 'IDLE',
    runtimeState: 'IDLE',
    surgicalStep: 'scene_setup',
    sessionId: null,
    services: {},
    camera: null,
  },

  // Actions
  setIsConnected: (status) => set({ isConnected: status }),
  setBooted: (val) => set({ isBooted: val }),
  requestActivation: () => set({ activationRequested: true }),
  consumeActivationRequest: () => set({ activationRequested: false }),
  setMicPermission: (status) => set({ micPermission: status }),
  setClientVoiceState: (status) => set({ clientVoiceState: status }),
  setListeningState: (status) => set({ listeningState: status }),
  setTranscriptPreview: (text) => set({ transcriptPreview: text }),
  setPhase: (p) => set({ phase: p }),
  setVoicePrompt: (vp) => set({ voicePrompt: vp }),
  clearVoicePrompt: () => set({ voicePrompt: null }),
  setWarning: (w) => set({ warning: w }),
  setARElements: (els) => set({ arElements: els }),
  setAngleData: (a) => set({ angleData: a }),
  setMetrics: (m) => set((state) => ({
    systemMetrics: {
      ...state.systemMetrics,
      ...m,
    },
  })),

  // Batch update from frame_state
  applyFrameState: (state) => set({
    phase: state.current_phase ?? 0,
    phaseName: state.phase_name ?? 'IDLE',
    runtimeState: state.runtime_state ?? state.phase_name ?? 'IDLE',
    surgicalStep: state.surgical_step ?? 'scene_setup',
    sessionId: state.session_id ?? null,
    voicePrompt: state.voice_prompt || null,
    voiceEventId: state.voice_event_id || null,
    voiceAudioUrl: state.voice_audio_url || null,
    warning: state.warning || null,
    countdownSeconds: state.countdown_seconds ?? null,
    arElements: state.ar_elements || [],
    angleData: state.angle_data || null,
    nextStepHint: state.next_step_hint || 'Say "Hey Surgeon, what do I do next?"',
    listeningState: state.listening_state || 'idle',
    transcriptPreview: state.transcript_preview || null,
    sceneEvents: state.scene_events || [],
    services: state.services || {},
    sessionTerminated: Boolean(state.session_terminated),
  }),
}));
