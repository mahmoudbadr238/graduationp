# Sentinel — Lint & Format Script
# Usage: powershell -File scripts/lint.ps1

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$python = $null

foreach ($candidate in @(
    (Join-Path $root ".venv\Scripts\python.exe"),
    (Join-Path $root "venv\Scripts\python.exe")
)) {
    if (Test-Path $candidate) {
        $python = $candidate
        break
    }
}

if (-not $python) {
    $python = "python"
}

Write-Host "`n=== Step 1: Compile Check ===" -ForegroundColor Cyan
& $python -m compileall "$root\backend" "$root\scripts" "$root\payload" "$root\main.py" -q
if ($LASTEXITCODE -eq 0) { Write-Host "[OK] All .py files compile" -ForegroundColor Green }
else { Write-Host "[FAIL] Compile errors found" -ForegroundColor Red; exit 1 }

Write-Host "`n=== Step 2: Ruff Lint ===" -ForegroundColor Cyan
& $python -m ruff check "$root\backend" "$root\scripts" "$root\payload" "$root\main.py" --config "$root\pyproject.toml" --statistics 2>&1 | Select-Object -Last 10

Write-Host "`n=== Step 3: Ruff Format Check ===" -ForegroundColor Cyan
& $python -m ruff format "$root\backend" "$root\scripts" "$root\payload" "$root\main.py" --check --config "$root\pyproject.toml" 2>&1 | Select-Object -Last 5

Write-Host "`n=== Done ===" -ForegroundColor Cyan
