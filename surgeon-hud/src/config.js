/** Backend origin — must match `PORT` in backend/.env (see surgeon-hud/.env.example). */
export function getApiBase() {
  const raw = import.meta.env.VITE_API_BASE || "http://localhost:5000";
  return String(raw).replace(/\/$/, "");
}

/**
 * Socket.IO namespace path — must match `SOCKET_NAMESPACE` in backend/.env
 * (e.g. `/realtime`). Client connects with io(`${getApiBase()}${getSocketNamespace()}`).
 */
export function getSocketNamespace() {
  const raw = import.meta.env.VITE_SOCKET_NAMESPACE ?? "/realtime";
  const s = String(raw).trim() || "/realtime";
  return s.startsWith("/") ? s : `/${s}`;
}

/** Full URL passed to socket.io-client (namespace is the URL path after origin). */
export function getSocketUrl() {
  return `${getApiBase()}${getSocketNamespace()}`;
}
