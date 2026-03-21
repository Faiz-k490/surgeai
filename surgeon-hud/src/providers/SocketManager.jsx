import { useEffect } from 'react';
import { io } from 'socket.io-client';
import { getSocketUrl } from '../config';
import { log } from '../lib/logger';
import { useHudStore } from '../store/useHudStore';

function unwrap(data) {
  return data?.payload ?? data;
}

export default function SocketManager({ children }) {
  const setStep = useHudStore((state) => state.setStep);
  const setWarning = useHudStore((state) => state.setWarning);
  const clearWarning = useHudStore((state) => state.clearWarning);
  const setQA = useHudStore((state) => state.setQA);
  const setMetrics = useHudStore((state) => state.setMetrics);
  const setIsConnected = useHudStore((state) => state.setIsConnected);
  const setARBoxes = useHudStore((state) => state.setARBoxes);

  useEffect(() => {
    // Polling only: Werkzeug + Flask-SocketIO (threading) often breaks WebSocket upgrade
    // with "Invalid frame header". Long-polling is reliable for this HUD. For native WS,
    // run behind an ASGI server or use async_mode=eventlet/gevent on the backend.
    const socket = io(getSocketUrl(), {
      path: '/socket.io',
      transports: ['polling'],
      upgrade: false,
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 500,
    });

    socket.on('connect', () => {
      setIsConnected(true);
      log.ok(`Socket.IO connected — ${getSocketUrl()}`);
    });
    socket.on('disconnect', (reason) => {
      setIsConnected(false);
      log.warn(`Socket.IO disconnected — ${reason}`);
    });
    socket.on('connect_error', (err) => {
      log.bad(
        `Socket.IO connect_error — match VITE_API_BASE to backend PORT & check backend is running: ${err?.message || err}`,
      );
    });

    socket.on('step_update', (raw) => {
      const data = unwrap(raw);
      setStep(`Step ${data.stepNumber}: ${data.stepName}`);
    });
    socket.on('warning', (raw) => {
      const data = unwrap(raw);
      setWarning(data.message);
    });
    socket.on('clear', () => clearWarning());
    socket.on('qa_update', (raw) => {
      const data = unwrap(raw);
      setQA(data);
      // Auto-clear QA after 10 seconds
      setTimeout(() => setQA(null), 10000);
    });
    socket.on('system_health', (raw) => {
      const data = unwrap(raw);
      setMetrics(data);
    });
    socket.on('vlm_update', (raw) => {
      const data = unwrap(raw);
      setARBoxes(data.boxes || []);
    });

    return () => socket.disconnect();
  }, [setStep, setWarning, clearWarning, setQA, setMetrics, setIsConnected, setARBoxes]);

  return <>{children}</>;
}
