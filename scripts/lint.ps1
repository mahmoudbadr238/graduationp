# Sentinel — Lint & Format Script
# Usage: powershell -File scripts/lint.ps1

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$python = Join-Path $root ".venv\Scripts\python.exe"

Write-Host "`n=== Step 1: Compile Check ===" -ForegroundColor Cyan
& $python -m compileall "$root\app" -q
if ($LASTEXITCODE -eq 0) { Write-Host "[OK] All .py files compile" -ForegroundColor Green }
else { Write-Host "[FAIL] Compile errors found" -ForegroundColor Red; exit 1 }

Write-Host "`n=== Step 2: Ruff Lint ===" -ForegroundColor Cyan
& $python -m ruff check "$root\app" --config "$root\pyproject.toml" --statistics 2>&1 | Select-Object -Last 10

Write-Host "`n=== Step 3: Ruff Format Check ===" -ForegroundColor Cyan
& $python -m ruff format "$root\app" --check --config "$root\pyproject.toml" 2>&1 | Select-Object -Last 5

Write-Host "`n=== Done ===" -ForegroundColor Cyan
