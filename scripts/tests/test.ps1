#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run Sentinel test suite

.DESCRIPTION
    Executes all unit tests and reports results.
    Tests backend services, repositories, and integration points.

.PARAMETER Coverage
    Generate code coverage report

.PARAMETER Verbose
    Show detailed test output

.EXAMPLE
    .\test.ps1
    .\test.ps1 -Coverage
    .\test.ps1 -Verbose
#>

param(
    [switch]$Coverage,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"

Write-Host "=== Sentinel Test Suite ===" -ForegroundColor Cyan
Write-Host ""

# Check for pytest
if (-not (Get-Command pytest -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] pytest not installed" -ForegroundColor Red
    Write-Host "        Install with: pip install pytest pytest-qt pytest-cov" -ForegroundColor Yellow
    exit 1
}

# Build test arguments
$testArgs = @("app/tests", "-v")

if ($Coverage) {
    Write-Host "[INFO] Code coverage enabled" -ForegroundColor Cyan
    $testArgs += @(
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "--cov-fail-under=60"
    )
}

if ($Verbose) {
    $testArgs += "-vv"
    $testArgs += "-s"  # Show print statements
}

Write-Host "[INFO] Running tests..." -ForegroundColor Cyan
Write-Host ""

# Run tests
try {
    & pytest @testArgs
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "[SUCCESS] All tests passed! ✓" -ForegroundColor Green
        
        if ($Coverage) {
            Write-Host ""
            Write-Host "[INFO] Coverage report saved to htmlcov/index.html" -ForegroundColor Cyan
        }
        
        exit 0
    } else {
        Write-Host ""
        Write-Host "[FAILED] Some tests failed ✗" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host ""
    Write-Host "[ERROR] Test execution failed: $_" -ForegroundColor Red
    exit 1
}
