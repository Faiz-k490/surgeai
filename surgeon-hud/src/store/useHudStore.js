import { create } from 'zustand';

export const useHudStore = create((set) => ({
  isConnected: false,
  isBooted: false,
  currentStep: "Initializing...",
  activeWarning: null,
  latestQA: null,
  systemMetrics: { fps: 0, latency: 0 },
  arBoxes: [],
  
  setIsConnected: (status) => set({ isConnected: status }),
  setBooted: (val) => set({ isBooted: val }),
  setStep: (step) => set({ currentStep: step }),
  setWarning: (warning) => set({ activeWarning: warning }),
  clearWarning: () => set({ activeWarning: null }),
  setQA: (qa) => set({ latestQA: qa }),
  setMetrics: (metrics) => set({ systemMetrics: metrics }),
  setARBoxes: (boxes) => set({ arBoxes: boxes }),
}));
