# Stop local SurgeAI dev servers (common ports: backend + Vite).
# Run from repo root:  powershell -ExecutionPolicy Bypass -File scripts/stop-dev.ps1

$here = $PSScriptRoot
. "$here\_log-colors.ps1"

$ports = 5000, 5001, 5173, 5174, 5175, 5176, 5177
$stopped = 0
foreach ($p in $ports) {
    Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue |
        Where-Object { $_.OwningProcess -gt 0 } |
        ForEach-Object {
            try {
                Stop-Process -Id $_.OwningProcess -Force -ErrorAction Stop
                Write-SurgeLogGood "Stopped PID $($_.OwningProcess) on port $p"
                $stopped++
            } catch {
                Write-SurgeLogBad "Could not stop port $p : $_"
            }
        }
}
if ($stopped -eq 0) {
    Write-SurgeLogWarn "No listeners found on dev ports (nothing to stop)."
} else {
    Write-SurgeLogGood "Stopped $stopped process(es)."
}
Write-SurgeLogInfo "Backend: python -m backend.app.main  (logs: logging\logs\surgeai-backend.log)"
Write-SurgeLogInfo "HUD:     cd surgeon-hud; npm run dev   (or: scripts\dev-hud.ps1)"
Write-SurgeLogInfo "Tail:    scripts\tail-backend-log.ps1"
