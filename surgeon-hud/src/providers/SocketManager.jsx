import { useEffect } from 'react';
import { io } from 'socket.io-client';
import { getSocketUrl } from '../config';
import { log } from '../lib/logger';
import { useHudStore } from '../store/useHudStore';

function unwrap(data) {
  return data?.payload ?? data;
}

export default function SocketManager({ children }) {
  const setIsConnected = useHudStore((s) => s.setIsConnected);
  const setMetrics = useHudStore((s) => s.setMetrics);
  const applyFrameState = useHudStore((s) => s.applyFrameState);

  useEffect(() => {
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
      log.bad(`Socket.IO connect_error: ${err?.message || err}`);
    });

    // Unified frame_state from DemoOrchestrator
    socket.on('frame_state', (raw) => {
      applyFrameState(unwrap(raw));
    });

    socket.on('system_health', (raw) => {
      setMetrics(unwrap(raw));
    });

    return () => socket.disconnect();
  }, [setIsConnected, setMetrics, applyFrameState]);

  return <>{children}</>;
}
