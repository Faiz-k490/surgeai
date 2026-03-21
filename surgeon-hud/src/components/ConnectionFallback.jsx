import { getApiBase, getSocketNamespace } from '../config';
import { useHudStore } from '../store/useHudStore';

/**
 * Socket.IO uses long-polling in dev (see SocketManager) — not a raw WebSocket.
 * Banner-only so the MJPEG `/video` feed stays visible for debugging (wrong port vs camera).
 */
export default function ConnectionFallback() {
  const isConnected = useHudStore((state) => state.isConnected);

  if (isConnected) return null;

  const base = getApiBase();
  const ns = getSocketNamespace();

  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 z-[100] flex justify-center p-4">
      <div className="pointer-events-auto max-w-2xl rounded border border-amber-500/40 bg-black/85 px-4 py-3 shadow-[0_0_24px_rgba(245,158,11,0.15)] backdrop-blur-sm">
        <div className="flex items-start gap-3">
          <div
            className="mt-0.5 h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-amber-400/30 border-t-amber-400"
            aria-hidden
          />
          <div className="min-w-0">
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-amber-400/90">
              Connecting to backend (Socket.IO)…
            </p>
            <p className="mt-1 font-mono text-[11px] leading-relaxed text-gray-400">
              Telemetry overlays wait for <code className="text-gray-300">{base}</code>. Match{' '}
              <code className="text-gray-300">VITE_API_BASE</code> to <code className="text-gray-300">PORT</code>{' '}
              in               <code className="text-gray-300">backend/.env</code>. Socket namespace{' '}
              <code className="text-gray-300">{ns}</code> must match{' '}
              <code className="text-gray-300">VITE_SOCKET_NAMESPACE</code>. Live video uses{' '}
              <code className="text-gray-300">{base}/video</code> — if the feed is blank, the camera stream may
              be down or the API URL wrong.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
