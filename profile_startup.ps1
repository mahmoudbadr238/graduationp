#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Profile Sentinel startup performance

.DESCRIPTION
    Measures application cold-start time using cProfile.
    Runs 3 iterations and calculates average startup time.
    Identifies performance bottlenecks in initialization.

.PARAMETER Runs
    Number of profiling runs (default: 3)

.PARAMETER Output
    Save profiling data to file

.EXAMPLE
    .\profile_startup.ps1
    .\profile_startup.ps1 -Runs 5
    .\profile_startup.ps1 -Output profile.stats
#>

param(
    [int]$Runs = 3,
    [string]$Output = ""
)

$ErrorActionPreference = "Stop"

Write-Host "=== Sentinel Startup Profiling ===" -ForegroundColor Cyan
Write-Host ""

if ($Runs -lt 1) {
    Write-Host "[ERROR] Runs must be >= 1" -ForegroundColor Red
    exit 1
}

# Create profiling script
$profileScript = @"
import cProfile
import pstats
import io
import sys
import time
from app.application import DesktopSecurityApplication

# Suppress GUI
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

# Profile startup
pr = cProfile.Profile()
pr.enable()

start_time = time.time()

try:
    app = DesktopSecurityApplication()
    # Don't run event loop, just measure initialization
except SystemExit:
    pass

elapsed = time.time() - start_time

pr.disable()

# Print timing
print(f'STARTUP_TIME: {elapsed:.3f}')

# Print stats
s = io.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
ps.print_stats(20)  # Top 20 functions
print(s.getvalue())

# Save if requested
if len(sys.argv) > 1:
    pr.dump_stats(sys.argv[1])
"@

$tempScript = "temp_profile.py"
$profileScript | Out-File -FilePath $tempScript -Encoding UTF8

$times = @()

Write-Host "[INFO] Running $Runs profiling iteration(s)..." -ForegroundColor Cyan
Write-Host ""

for ($i = 1; $i -le $Runs; $i++) {
    Write-Host "  Run $i/$Runs..." -ForegroundColor Yellow
    
    $scriptArgs = @($tempScript)
    if ($Output -and $i -eq $Runs) {
        # Save stats on last run
        $scriptArgs += $Output
    }
    
    $result = python @scriptArgs 2>&1
    
    # Extract timing
    $timingLine = $result | Select-String "STARTUP_TIME: ([\d\.]+)"
    if ($timingLine -and $timingLine.Matches.Groups.Count -ge 2) {
        $time = [double]$timingLine.Matches.Groups[1].Value
        $times += $time
        Write-Host "    → ${time}s" -ForegroundColor Green
    }
    
    # Show detailed stats on last run
    if ($i -eq $Runs) {
        Write-Host ""
        Write-Host "  [Profile Stats - Top 20 Functions]" -ForegroundColor Cyan
        Write-Host "  ----------------------------------------" -ForegroundColor DarkGray
        
        $statsStarted = $false
        foreach ($line in $result) {
            if ($line -match "ncalls.*tottime") {
                $statsStarted = $true
            }
            if ($statsStarted) {
                Write-Host "  $line" -ForegroundColor White
            }
        }
    }
    
    # Brief delay between runs
    if ($i -lt $Runs) {
        Start-Sleep -Milliseconds 500
    }
}

# Cleanup
Remove-Item $tempScript -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "=== Results ===" -ForegroundColor Cyan

if ($times.Count -gt 0) {
    $avgTime = ($times | Measure-Object -Average).Average
    $minTime = ($times | Measure-Object -Minimum).Minimum
    $maxTime = ($times | Measure-Object -Maximum).Maximum
    
    Write-Host "  Runs:    $($times.Count)" -ForegroundColor White
    Write-Host "  Average: $($avgTime.ToString('0.000'))s" -ForegroundColor Green
    Write-Host "  Min:     $($minTime.ToString('0.000'))s" -ForegroundColor Green
    Write-Host "  Max:     $($maxTime.ToString('0.000'))s" -ForegroundColor Green
    
    Write-Host ""
    
    if ($avgTime -lt 1.2) {
        Write-Host "[SUCCESS] Startup time meets target (< 1.2s) ✓" -ForegroundColor Green
    } elseif ($avgTime -lt 2.0) {
        Write-Host "[WARNING] Startup time acceptable but could be optimized (< 2.0s)" -ForegroundColor Yellow
    } else {
        Write-Host "[SLOW] Startup time exceeds target (>= 2.0s) - optimization needed!" -ForegroundColor Red
    }
    
    if ($Output) {
        Write-Host ""
        Write-Host "[INFO] Profile data saved to: $Output" -ForegroundColor Cyan
        Write-Host "       Analyze with: python -m pstats $Output" -ForegroundColor Cyan
    }
} else {
    Write-Host "[ERROR] No timing data collected" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Recommendations ===" -ForegroundColor Cyan
Write-Host "  • Defer heavy imports (GPUManager, scanners)" -ForegroundColor White
Write-Host "  • Use QTimer.singleShot for delayed initialization" -ForegroundColor White
Write-Host "  • Lazy-load QML components with Loader" -ForegroundColor White
Write-Host "  • Cache expensive computations" -ForegroundColor White
