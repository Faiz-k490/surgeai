# SurgeAI — shared terminal colors for PowerShell scripts (dot-source from repo root scripts).
# Usage:  . "$PSScriptRoot\_log-colors.ps1"

function Write-SurgeLogGood {
    param([string]$Message)
    Write-Host "[OK]   $Message" -ForegroundColor Green
}

function Write-SurgeLogBad {
    param([string]$Message)
    Write-Host "[FAIL] $Message" -ForegroundColor Red
}

function Write-SurgeLogWarn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-SurgeLogInfo {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}
