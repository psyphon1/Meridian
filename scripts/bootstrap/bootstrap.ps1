# =============================================================================
# Meridian — one-time local bootstrap (Windows / PowerShell).
# Mirrors `make setup` for Unix. See docs/SETUP.md.
#
#     .\scripts\bootstrap\bootstrap.ps1
#
# Creates a .venv, installs Python deps + pnpm workspaces, and starts Postgres/Redis.
# =============================================================================
[CmdletBinding()]
param(
    [switch]$SkipDocker
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Require([string]$Name, [string]$Hint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Error "$Name is required but not found. $Hint"
    }
}

Write-Host "==> Checking prerequisites" -ForegroundColor Cyan
Require "python"  "Install Python 3.12+ from https://www.python.org and ensure it is on PATH."
Require "pnpm"    "Install Node 20+ then run: npm install -g pnpm"
Require "git"     "Install Git from https://git-scm.com"
if (-not $SkipDocker) { Require "docker" "Install Docker Desktop from https://www.docker.com" }

Write-Host "==> Creating Python virtual environment" -ForegroundColor Cyan
if (-not (Test-Path "$Root\.venv")) {
    python -m venv "$Root\.venv"
}
$Py = "$Root\.venv\Scripts\python.exe"
& $Py -m pip install --upgrade pip
& $Py -m pip install -e "$Root[dev]"

Write-Host "==> Installing frontend workspaces" -ForegroundColor Cyan
Push-Location $Root
try {
    pnpm install
} finally {
    Pop-Location
}

Write-Host "==> Preparing environment" -ForegroundColor Cyan
if (-not (Test-Path "$Root\.env")) {
    Copy-Item "$Root\.env.example" "$Root\.env"
    Write-Warning ".env created from .env.example — fill in real values before running the app."
} else {
    Write-Host "    .env already exists; left untouched."
}

if ($SkipDocker) {
    Write-Host "==> Skipped Docker. Start backing services later: docker compose up -d postgres redis" -ForegroundColor Yellow
} else {
    Write-Host "==> Starting backing services (Postgres + Redis)" -ForegroundColor Cyan
    docker compose up -d postgres redis
}

Write-Host ""
Write-Host "Bootstrap complete." -ForegroundColor Green
Write-Host "  Backing services: docker compose up -d postgres redis"
Write-Host "  Run tests:        $Py -m pytest"
Write-Host "  Run API (Phase 1): $Py -m uvicorn apps.api.main:app --reload"
Write-Host "  Note: auth switch for the right GitHub account: gh auth switch -u psyphon1"
