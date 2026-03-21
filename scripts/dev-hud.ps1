# Run Vite HUD with stdout/stderr copied to logging/logs/hud-dev.log (plain text; colors in terminal may flatten).
# Run from repo root:  powershell -ExecutionPolicy Bypass -File scripts\dev-hud.ps1

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$repoRoot = Split-Path $here -Parent
. "$here\_log-colors.ps1"

$logDir = Join-Path $repoRoot "logging\logs"
$logFile = Join-Path $logDir "hud-dev.log"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Write-SurgeLogGood "Starting surgeon-hud (npm run dev)"
Write-SurgeLogInfo "Also writing to $logFile"
$hudDir = Join-Path $repoRoot "surgeon-hud"
if (-not (Test-Path (Join-Path $hudDir "package.json"))) {
    Write-SurgeLogBad "surgeon-hud not found under $repoRoot"
    exit 1
}
Push-Location $hudDir
try {
    npm run dev 2>&1 | Tee-Object -FilePath $logFile
} finally {
    Pop-Location
}
