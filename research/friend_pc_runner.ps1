# AeroFleet — friend's-PC batch runner (Windows), ZIP-based, no token/git.
#
# Setup:
#   1. On github.com (logged in as a collaborator on the repo), click the
#      green "Code" button -> "Download ZIP".
#   2. Extract it. You should see requirements.txt, scenario_engine\, etc.
#      directly inside the extracted folder.
#   3. Put this script (friend_pc_runner.ps1) into that same extracted folder.
#   4. .\friend_pc_runner.ps1
#      (If it refuses to run: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass, then retry)
#
# Runs batches 15-26 of the 1,000-case mass forensics study on this machine.
# Safe to re-run any time (Ctrl+C, close the window, reboot) — progress is
# saved per-case to mass_forensics_friend\results.jsonl on this machine's own
# disk, and re-running this script picks up exactly where it left off.

$ErrorActionPreference = "Stop"

Write-Host "=== AeroFleet - friend's-PC batch runner (batches 15-26) ===" -ForegroundColor Cyan
Write-Host ""

# 0. Sanity check: are we actually inside the extracted repo?
if (-not (Test-Path "requirements.txt") -or -not (Test-Path "scenario_engine")) {
    Write-Host "ERROR: requirements.txt or scenario_engine\ not found in this folder." -ForegroundColor Red
    Write-Host "Move this script INSIDE the extracted repo folder (the one that has"
    Write-Host "requirements.txt directly in it) and run it from there."
    exit 1
}

# 1. Check Ollama is installed
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama isn't installed. Install it first, then re-run this script:"
    Write-Host "  https://ollama.com/download/windows"
    exit 1
}

# 2. Start the Ollama server if it isn't already running
$ollamaUp = $false
try {
    Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 | Out-Null
    $ollamaUp = $true
    Write-Host "Ollama already running."
} catch {
    Write-Host "Starting Ollama server..."
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 5
}

if (-not $ollamaUp) {
    try {
        Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 | Out-Null
    } catch {
        Write-Host "ERROR: Ollama did not start." -ForegroundColor Red
        exit 1
    }
}
Write-Host "Ollama is up."
Write-Host ""

# 3. Pull the model (~3.2GB, only happens once)
Write-Host "Pulling phi4-mini-reasoning..."
ollama pull phi4-mini-reasoning
Write-Host ""

# 4. Python environment
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
pip install -q -r requirements.txt

# 5. Confirm Ollama is really reachable before committing to a long run
python -c "
import requests, sys
try:
    r = requests.get('http://localhost:11434/api/tags', timeout=5)
    print('Ollama reachable:', r.json())
except Exception as e:
    print('Ollama NOT reachable:', e)
    sys.exit(1)
"

# 6. Run the harness - this machine's assigned batch range.
# Change $onlyBatches below if you've been assigned a different range - just
# double-check it doesn't overlap whatever the other machines are already
# covering.
$onlyBatches = "15-26"

$env:OLLAMA_HOST = "http://localhost:11434"
Remove-Item Env:USE_MOCK_AGENTS -ErrorAction SilentlyContinue

$studyDir = "mass_forensics_friend"
New-Item -ItemType Directory -Force -Path $studyDir | Out-Null

Write-Host ""
Write-Host "Starting the harness - batches $onlyBatches."
Write-Host "This runs for a long time. Leave this PowerShell window open while it runs."
Write-Host ""

python -m scenario_engine.mass_forensics_evaluation `
    --study-dir $studyDir `
    --target 1000 --batch-size 25 `
    --only-batches $onlyBatches `
    --retry-failed-max 5

Write-Host ""
Write-Host "Stopped (finished, or interrupted - either way, progress is saved)."
Write-Host "Results are in: $studyDir\results.jsonl"
Write-Host "Send that whole 'mass_forensics_friend' folder back when ready to merge with the other machines."
