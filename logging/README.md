# SurgeAI logging

All runtime log **files** live under **`logging/logs/`** (gitignored). Terminal output uses **green** for healthy/info, **red** for errors, **yellow** for warnings.

| Layer | Where it goes | How to watch |
|-------|----------------|--------------|
| **Backend (Python)** | `logging/logs/surgeai-backend.log` + colored stdout | Run backend from terminal; or `scripts\tail-backend-log.ps1` |
| **HUD (browser)** | Browser DevTools console (colored via `src/lib/logger.js`) | F12 → Console |
| **Vite dev server** | Terminal + optional `logging/logs/hud-dev.log` when using `scripts\dev-hud.ps1` | Run `npm run dev` or the script |
| **Scripts** | Colored `Write-Host` in PowerShell | Run scripts from repo root |

## Environment

- **`LOG_LEVEL`** — `DEBUG`, `INFO`, `WARNING`, `ERROR` (default `INFO`) in `backend/.env`.
- **`SURGEAI_LOG_DIR`** — optional absolute path; default is `repo/logging/logs`.

## Files

- `../backend/app/core/runtime_logging.py` — configures Python logging (file + colorlog).
- `../surgeon-hud/src/lib/logger.js` — HUD console helpers (`log.ok`, `log.bad`, …).
- `../scripts/_log-colors.ps1` — shared green/red helpers for PowerShell scripts.
