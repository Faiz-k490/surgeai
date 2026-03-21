/**
 * Browser console logging with green (ok) / red (bad) / yellow (warn) styling.
 * Open DevTools → Console to see HUD diagnostics when Socket.IO or video fails.
 */

const styles = {
  ok: 'color:#22c55e;font-weight:600;',
  bad: 'color:#ef4444;font-weight:600;',
  warn: 'color:#eab308;font-weight:600;',
  info: 'color:#94a3b8;',
  dim: 'color:#64748b;',
};

function stamp() {
  return new Date().toISOString().slice(11, 23);
}

export const log = {
  ok: (msg, ...rest) => console.log(`%c[HUD ${stamp()}] ${msg}`, styles.ok, ...rest),
  bad: (msg, ...rest) => console.error(`%c[HUD ${stamp()}] ${msg}`, styles.bad, ...rest),
  warn: (msg, ...rest) => console.warn(`%c[HUD ${stamp()}] ${msg}`, styles.warn, ...rest),
  info: (msg, ...rest) => console.log(`%c[HUD ${stamp()}] ${msg}`, styles.info, ...rest),
  dim: (msg, ...rest) => console.log(`%c[HUD ${stamp()}] ${msg}`, styles.dim, ...rest),
};
