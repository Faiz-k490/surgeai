# Follow SurgeAI backend log file with live updates (requires backend to have run once).
# Run from repo root:  powershell -ExecutionPolicy Bypass -File scripts\tail-backend-log.ps1

$here = $PSScriptRoot
$repoRoot = Split-Path $here -Parent
. "$here\_log-colors.ps1"

$logFile = Join-Path $repoRoot "logging\logs\surgeai-backend.log"
if (-not (Test-Path $logFile)) {
    Write-SurgeLogBad "No log file yet: $logFile"
    Write-SurgeLogWarn "Start the backend first: python -m backend.app.main"
    exit 1
}
Write-SurgeLogGood "Tailing $logFile (Ctrl+C to stop)"
Get-Content $logFile -Wait -Tail 50
