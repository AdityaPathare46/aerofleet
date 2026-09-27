# AeroFleet — forensics v2 experiment on a Windows PC (ZIP-based, no git, no tokens).
#
# What it measures: whether each fix for phi4-mini's 1,000-case errors helps, on cases the model
# has never seen (research/forensics_v2/, research/PAPER_READINESS.md section 3).
#
# Setup (once):
#   1. Install Ollama: https://ollama.com/download/windows  (uses the GPU automatically if there is one)
#   2. Install Python 3.10 or 3.11 from python.org (tick "Add python.exe to PATH").
#   3. On github.com: the repo -> green "Code" button -> "Download ZIP". Extract it.
#   4. Open PowerShell in the extracted folder (the one with requirements.txt in it) and run:
#        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#        .\research\college_pc_forensics_v2.ps1
#
# Safe to stop and re-run at any time (Ctrl+C, close the window, reboot): every case is saved as it
# finishes and a re-run continues where it left off.
#
# When it finishes, send back the folder:  research\results\forensics_v2
#
# Size: -N sets how many unseen cases per dataset (default 60). The whole run is
# 5 conditions x N (eval) + 2 conditions x N (hard). It prints seconds per case as it goes.

param([int]$N = 60)
$ErrorActionPreference = "Stop"
Write-Host "=== AeroFleet forensics v2 — $N cases per dataset ===" -ForegroundColor Cyan

if (-not (Test-Path "requirements.txt") -or -not (Test-Path "research\forensics_v2")) {
    Write-Host "ERROR: run this from the extracted repo folder (the one containing requirements.txt)." -ForegroundColor Red
    exit 1
}
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama isn't installed: https://ollama.com/download/windows" -ForegroundColor Red
    exit 1
}
try { Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 | Out-Null }
catch {
    Write-Host "Starting Ollama..."
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 6
}

Write-Host "Pulling phi4-mini-reasoning (about 3.2 GB, only the first time)..."
ollama pull phi4-mini-reasoning

if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\Activate.ps1
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt

$env:OLLAMA_HOST = "http://localhost:11434"
$env:AEROFLEET_VR_NETWORK = "off"
Remove-Item Env:USE_MOCK_AGENTS -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "1/2  Unseen cases, conditions C0-C4 (the fixes one at a time)..." -ForegroundColor Cyan
python -m research.forensics_v2.run --condition C0 C1 C2 C3 C4 --dataset eval --n $N
Write-Host ""
Write-Host "2/2  Hard cases (near-miss distractors), baseline vs all fixes..." -ForegroundColor Cyan
python -m research.forensics_v2.run --condition C0 C4 --dataset hard --n $N

python -m research.forensics_v2.analyze
Write-Host ""
Write-Host "Done. Send back the whole folder: research\results\forensics_v2" -ForegroundColor Green
