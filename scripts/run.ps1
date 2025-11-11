#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run Sentinel Desktop Security Suite

.DESCRIPTION
    Activates Python virtual environment (if exists) and runs the application.
    Ensures all dependencies are installed before launch.

.PARAMETER Debug
    Run with verbose logging

.EXAMPLE
    .\run.ps1
    .\run.ps1 -Debug
#>

param(
    [switch]$Debug
)

$ErrorActionPreference = "Stop"

Write-Host "=== Sentinel Desktop Security Suite ===" -ForegroundColor Cyan
Write-Host ""

# Check for virtual environment
$venvPaths = @("venv", ".venv", "env")
$venvFound = $false

foreach ($venvPath in $venvPaths) {
    $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        Write-Host "[OK] Found virtual environment: $venvPath" -ForegroundColor Green
        & $activateScript
        $venvFound = $true
        break
    }
}

if (-not $venvFound) {
    Write-Host "[INFO] No virtual environment found. Using system Python." -ForegroundColor Yellow
}

# Check Python version
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python not found in PATH" -ForegroundColor Red
    exit 1
}

# Check if requirements are installed
Write-Host "[INFO] Checking dependencies..." -ForegroundColor Cyan
$missingPackages = @()

try {
    python -c "import PySide6" 2>$null
} catch {
    $missingPackages += "PySide6"
}

try {
    python -c "import psutil" 2>$null
} catch {
    $missingPackages += "psutil"
}

if ($missingPackages.Count -gt 0) {
    Write-Host "[WARNING] Missing packages: $($missingPackages -join ', ')" -ForegroundColor Yellow
    Write-Host "[INFO] Installing requirements..." -ForegroundColor Cyan
    pip install -r requirements.txt
}

# Check for admin privileges
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($isAdmin) {
    Write-Host "[OK] Running with administrator privileges" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Not running as administrator - some features may be limited" -ForegroundColor Yellow
    Write-Host "         Use run_as_admin.bat for full functionality" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Launching Application ===" -ForegroundColor Cyan
Write-Host ""

# Set environment variables
if ($Debug) {
    $env:QT_LOGGING_RULES = "*.debug=true"
    $env:PYTHONUNBUFFERED = "1"
}

# Run application
try {
    python main.py
} catch {
    Write-Host ""
    Write-Host "[ERROR] Application crashed: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Application Closed ===" -ForegroundColor Cyan
