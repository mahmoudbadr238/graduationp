#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Commit the current Sentinel working tree with optional checks.

.DESCRIPTION
    Runs the repo lint script unless skipped, stages current changes, shows the
    staged diff summary, and creates a commit after confirmation.

.PARAMETER Message
    Commit message to use.

.PARAMETER SkipChecks
    Skip lint checks before staging.

.EXAMPLE
    .\commit_changes.ps1 -Message "chore: clean up repo tooling"

.EXAMPLE
    .\commit_changes.ps1 -SkipChecks -Message "docs: update README"
#>

param(
    [string]$Message = "chore: update project files",
    [switch]$SkipChecks
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $PSCommandPath
$repoRoot = Split-Path -Parent (Split-Path -Parent $scriptRoot)
$lintScript = Join-Path $repoRoot "scripts\lint.ps1"

Push-Location $repoRoot

try {
    Write-Host "=== Sentinel Commit Helper ===" -ForegroundColor Cyan
    Write-Host ""

    if (-not $SkipChecks) {
        if (Test-Path $lintScript) {
            Write-Host "[1/4] Running lint checks..." -ForegroundColor Yellow
            & $lintScript
            if ($LASTEXITCODE -ne 0) {
                Write-Host ""
                Write-Host "[ERROR] Lint checks failed. Fix issues or re-run with -SkipChecks." -ForegroundColor Red
                exit 1
            }
        } else {
            Write-Host "[WARN] Lint script not found at $lintScript" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[SKIP] Lint checks skipped" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "[2/4] Staging current changes..." -ForegroundColor Yellow
    git add -A

    $stagedSummary = git diff --cached --stat
    if (-not $stagedSummary) {
        Write-Host "[INFO] No staged changes found." -ForegroundColor Yellow
        exit 0
    }

    Write-Host ""
    Write-Host "[3/4] Staged diff summary:" -ForegroundColor Yellow
    Write-Host $stagedSummary
    Write-Host ""
    Write-Host "Commit message:" -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor White
    Write-Host ""

    $confirm = Read-Host "Proceed with commit? (y/N)"
    if ($confirm -notin @("y", "Y")) {
        Write-Host "[CANCELLED] No commit created." -ForegroundColor Yellow
        exit 0
    }

    Write-Host ""
    Write-Host "[4/4] Creating commit..." -ForegroundColor Yellow
    git commit -m $Message

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "[SUCCESS] Commit created." -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "[ERROR] Commit failed." -ForegroundColor Red
        exit 1
    }
}
finally {
    Pop-Location
}
