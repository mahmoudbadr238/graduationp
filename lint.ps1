#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Lint Sentinel codebase for quality issues

.DESCRIPTION
    Runs QML linting (qmllint) and Python linting (ruff + mypy) to catch errors.
    Ensures code meets quality standards before commit.

.PARAMETER Fix
    Automatically fix issues where possible

.PARAMETER Strict
    Use strict mode (fails on warnings)

.EXAMPLE
    .\lint.ps1
    .\lint.ps1 -Fix
    .\lint.ps1 -Strict
#>

param(
    [switch]$Fix,
    [switch]$Strict
)

$ErrorActionPreference = "Continue"
$failCount = 0

Write-Host "=== Sentinel Code Quality Check ===" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# QML Linting
# ============================================================
Write-Host "[1/3] QML Linting (qmllint)" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor DarkGray

$qmlFiles = Get-ChildItem -Path "qml" -Recurse -Filter "*.qml" -File

if (Get-Command qmllint -ErrorAction SilentlyContinue) {
    $qmlErrors = 0
    
    foreach ($file in $qmlFiles) {
        $result = qmllint $file.FullName 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  [FAIL] $($file.Name)" -ForegroundColor Red
            Write-Host "         $result" -ForegroundColor DarkRed
            $qmlErrors++
        }
    }
    
    if ($qmlErrors -eq 0) {
        Write-Host "  [OK] All $($qmlFiles.Count) QML files passed" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] $qmlErrors QML files have errors" -ForegroundColor Red
        $failCount++
    }
} else {
    Write-Host "  [SKIP] qmllint not found (install Qt6 development tools)" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================
# Python Linting (Ruff)
# ============================================================
Write-Host "[2/3] Python Linting (Ruff)" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor DarkGray

if (Get-Command ruff -ErrorAction SilentlyContinue) {
    $ruffArgs = @("check", "app", "main.py")
    
    if ($Fix) {
        $ruffArgs += "--fix"
        Write-Host "  [INFO] Auto-fixing issues..." -ForegroundColor Cyan
    }
    
    if ($Strict) {
        $ruffArgs += "--select=ALL"
    }
    
    $result = & ruff @ruffArgs 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] No Python linting errors" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] Python linting errors found:" -ForegroundColor Red
        Write-Host $result -ForegroundColor DarkRed
        $failCount++
    }
} else {
    Write-Host "  [SKIP] Ruff not installed (pip install ruff)" -ForegroundColor Yellow
    Write-Host "  [INFO] Falling back to flake8..." -ForegroundColor Cyan
    
    if (Get-Command flake8 -ErrorAction SilentlyContinue) {
        $result = flake8 app main.py --max-line-length=120 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] No Python linting errors (flake8)" -ForegroundColor Green
        } else {
            Write-Host "  [FAIL] Flake8 errors:" -ForegroundColor Red
            Write-Host $result -ForegroundColor DarkRed
            $failCount++
        }
    } else {
        Write-Host "  [SKIP] flake8 not installed (pip install flake8)" -ForegroundColor Yellow
    }
}

Write-Host ""

# ============================================================
# Type Checking (MyPy)
# ============================================================
Write-Host "[3/3] Type Checking (MyPy)" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor DarkGray

if (Get-Command mypy -ErrorAction SilentlyContinue) {
    $mypyArgs = @(
        "app",
        "--ignore-missing-imports",
        "--no-strict-optional",
        "--warn-redundant-casts",
        "--warn-unused-ignores"
    )
    
    if ($Strict) {
        $mypyArgs += "--strict"
    }
    
    $result = & mypy @mypyArgs 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] No type errors" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] Type errors found:" -ForegroundColor Red
        Write-Host $result -ForegroundColor DarkRed
        
        if ($Strict) {
            $failCount++
        } else {
            Write-Host "  [INFO] Type errors are warnings only (use -Strict to fail)" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  [SKIP] MyPy not installed (pip install mypy)" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================
# Summary
# ============================================================
Write-Host "=== Summary ===" -ForegroundColor Cyan

if ($failCount -eq 0) {
    Write-Host "[SUCCESS] All checks passed! ✓" -ForegroundColor Green
    exit 0
} else {
    Write-Host "[FAILED] $failCount check(s) failed ✗" -ForegroundColor Red
    exit 1
}
