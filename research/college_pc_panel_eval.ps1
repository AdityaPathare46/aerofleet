# AeroFleet 2.0 — review-panel evaluation on a Windows PC (ZIP-based, no git, no tokens).
# Full instructions and how to read the result: docs\aerofleet2\PANEL_EVAL_RUNBOOK.md
#
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\research\college_pc_panel_eval.ps1                                   # the five laptop-size models
#   .\research\college_pc_panel_eval.ps1 -Models "qwen2.5:3b,phi4-mini"           # choose models
#   .\research\college_pc_panel_eval.ps1 -N 30                             # fewer cases (faster)
#
# Safe to stop and re-run: every case is saved as it finishes and a re-run continues where it left off.
# When it finishes, send back the folder:  research\results\panel_eval

param([string]$Models = "qwen2.5:3b,phi4-mini,gemma3:4b,qwen3:4b,llama3.2", [int]$N = 60)
$ErrorActionPreference = "Stop"
Write-Host "=== AeroFleet review-panel evaluation: $N cases, models: $Models ===" -ForegroundColor Cyan

if (-not (Test-Path "research\panel_eval\run.py")) {
    Write-Host "ERROR: run this from the extracted repo folder (the one containing the 'research' folder)." -ForegroundColor Red
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

if (-not (Test-Path ".venv-panel")) { python -m venv .venv-panel }
& .\.venv-panel\Scripts\Activate.ps1
python -m pip install --quiet requests

foreach ($m in $Models.Split(",")) {
    $model = $m.Trim()
    if (-not $model) { continue }
    Write-Host "`n--- $model : downloading if needed (only the first time) ---" -ForegroundColor Cyan
    ollama pull $model
    Write-Host "--- $model : running $N cases (one line per case) ---" -ForegroundColor Cyan
    python -m research.panel_eval.run --n $N --model $model
}

Write-Host "`n=== Report ===" -ForegroundColor Cyan
python -m research.panel_eval.run --report
python -m research.panel_eval.injection_reach 2>$null
Write-Host "`nDone. Send back the folder: research\results\panel_eval" -ForegroundColor Green
