#Requires -Version 5.1
<#
.SYNOPSIS
    One-time guest setup: deploy Sentinel Sandbox Agent + register scheduled task.

.DESCRIPTION
    Run this ONCE inside the guest (e.g. via vmrun RunProgramInGuest after first
    snapshot creation).  It installs:
        C:\Sandbox\agent\agent.ps1           (legacy fallback)
        C:\Sandbox\agent\run_ui_wrapper.ps1  (ONLOGON interactive runner)
        C:\Sandbox\agent\run_ui.ahk          (visible AHK interaction layer)
    And registers a scheduled task:
        Name:    SentinelSandboxAgent
        Trigger: ONLOGON (fires each time the user logs in, i.e. each VM revert+boot)
        Run as:  INTERACTIVE user (no admin required)
        Action:  powershell.exe ... run_ui_wrapper.ps1
    The wrapper polls for C:\Sandbox\job.json (up to 5 min) and exits cleanly
    if no job is found — no manual /Run trigger needed from the host.

.PARAMETER SourceDir
    Directory containing agent.ps1 (and optionally ui.ahk).
    Defaults to the directory of this script.

.NOTES
    After running this script, take a clean snapshot so every job starts from it.
#>

param(
    [string]$SourceDir = $PSScriptRoot
)

Set-StrictMode -Off
$ErrorActionPreference = "Stop"

$AgentDir     = "C:\Sandbox\agent"
$InDir        = "C:\Sandbox\in"
$OutDir       = "C:\Sandbox\out"
$TaskName     = "SentinelSandboxAgent"
$AgentPs1     = Join-Path $AgentDir "agent.ps1"
$WrapperPs1   = Join-Path $AgentDir "run_ui_wrapper.ps1"
$AhkScript    = Join-Path $AgentDir "run_ui.ahk"

function Write-OK   { param([string]$M); Write-Host "[OK]     $M" -ForegroundColor Green }
function Write-Warn { param([string]$M); Write-Host "[WARN]   $M" -ForegroundColor Yellow }
function Write-Fail { param([string]$M); Write-Host "[FAIL]   $M" -ForegroundColor Red }
function Write-Info { param([string]$M); Write-Host "[INFO]   $M" -ForegroundColor Cyan }

Write-Info "Sentinel Sandbox Agent — guest install"
Write-Info "Source : $SourceDir"
Write-Info "Target : $AgentDir"

# ─── Create directories ───────────────────────────────────────────────────────
foreach ($d in @($AgentDir, $InDir, $OutDir, "$OutDir\shots")) {
    if (Test-Path $d) {
        Write-OK "$d already exists"
    } else {
        $null = New-Item -ItemType Directory -Force -Path $d
        Write-OK "Created $d"
    }
}

# ─── Copy agent.ps1 (legacy fallback) ────────────────────────────────────────
$srcAgent = Join-Path $SourceDir "agent.ps1"
if (Test-Path $srcAgent) {
    Copy-Item -Path $srcAgent -Destination $AgentPs1 -Force
    Write-OK "Copied agent.ps1 (legacy)"
} else {
    Write-Warn "agent.ps1 not found — skipping (run_ui_wrapper.ps1 is the active runner)"
}

# ─── Copy run_ui_wrapper.ps1 (ONLOGON interactive runner) ─────────────────────
$srcWrapper = Join-Path $SourceDir "run_ui_wrapper.ps1"
if (-not (Test-Path $srcWrapper)) {
    Write-Fail "run_ui_wrapper.ps1 not found in $SourceDir — aborting"
    exit 1
}
Copy-Item -Path $srcWrapper -Destination $WrapperPs1 -Force
Write-OK "Copied run_ui_wrapper.ps1 → $WrapperPs1"

# ─── Copy run_ui.ahk (visible AHK interaction layer) ──────────────────────────
$srcAhk = Join-Path $SourceDir "run_ui.ahk"
if (Test-Path $srcAhk) {
    Copy-Item -Path $srcAhk -Destination $AhkScript -Force
    Write-OK "Copied run_ui.ahk"
} else {
    Write-Warn "run_ui.ahk not found in $SourceDir — Win+R interaction will be skipped"
}

# ─── Set permissive ACL on C:\Sandbox so agent can read/write freely ─────────
try {
    $acl = Get-Acl "C:\Sandbox"
    $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
        "Everyone", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow"
    )
    $acl.AddAccessRule($rule)
    Set-Acl "C:\Sandbox" $acl
    Write-OK "ACL: Everyone FullControl on C:\Sandbox"
} catch {
    Write-Warn "Could not set ACL on C:\Sandbox: $_ (may not matter if running as SYSTEM)"
}

# ─── Set unrestricted execution policy in guest ───────────────────────────────
try {
    Set-ExecutionPolicy -Scope LocalMachine -ExecutionPolicy Bypass -Force
    Write-OK "ExecutionPolicy set to Bypass (LocalMachine)"
} catch {
    Write-Warn "Could not set ExecutionPolicy: $_"
}

# ─── Unregister existing task if present ─────────────────────────────────────
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-OK "Removed existing task: $TaskName"
}

# ─── Create the scheduled task ───────────────────────────────────────────────
#
#  Key flags:
#    /it   — interactive (run in logged-on user's session, VISIBLE)
#    /rl HIGHEST — run with highest available privileges
#    /sc ONCE /st 00:00  — no automatic trigger; host uses /Run explicitly
#    /f    — force overwrite
#
# ONLOGON approach: task fires every time the user logs in (i.e. after each VM revert+boot).
# The wrapper polls for job.json — no explicit /Run trigger needed from the host.
$psExe  = "powershell.exe"
$psArgs = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$WrapperPs1`""

Write-Info "Registering scheduled task: $TaskName (ONLOGON)"

$result = schtasks.exe /Create `
    /TN $TaskName `
    /TR "$psExe $psArgs" `
    /SC ONLOGON `
    /IT `
    /F 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-OK "Task registered: $TaskName"
} else {
    Write-Warn "schtasks exit $LASTEXITCODE — trying CIM/WMI path as fallback"

    # Fallback: New-ScheduledTask (requires TaskScheduler module, Win8+)
    try {
        $action  = New-ScheduledTaskAction -Execute $psExe -Argument $psArgs
        $settings = New-ScheduledTaskSettingsSet `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
            -MultipleInstances IgnoreNew `
            -RunOnlyIfIdle:$false `
            -StartWhenAvailable

        $trigger   = New-ScheduledTaskTrigger -AtLogOn
        $principal = New-ScheduledTaskPrincipal `
            -UserId $env:USERNAME `
            -LogonType Interactive `
            -RunLevel Limited

        Register-ScheduledTask `
            -TaskName $TaskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -Principal $principal `
            -Force | Out-Null

        Write-OK "Task registered via CIM: $TaskName"
    } catch {
        Write-Fail "Could not register task via CIM either: $_ — please register manually."
        exit 1
    }
}

# ─── Verify ───────────────────────────────────────────────────────────────────
$t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($t) {
    Write-OK "Verification: task '$TaskName' state = $($t.State)"
} else {
    Write-Warn "Task not found after registration — check Task Scheduler manually"
}

# ─── Event source for logging (optional) ─────────────────────────────────────
try {
    if (-not [System.Diagnostics.EventLog]::SourceExists("SentinelSandbox")) {
        New-EventLog -LogName Application -Source "SentinelSandbox"
        Write-OK "Event Log source 'SentinelSandbox' created"
    }
} catch { Write-Warn "Could not create Event Log source: $_" }

Write-Info ""
Write-OK "Installation complete."
Write-Info ""
Write-Info "Next steps:"
Write-Info "  1. Verify the VM auto-logs in after revert (netplwiz — remove PW prompt)"
Write-Info "  2. Take a clean snapshot: vmrun snapshot <vmx> clean"
Write-Info "  3. Host writes job.json to C:\\Sandbox\\job.json — task fires automatically on next login"
Write-Info "  4. Output lands in: $OutDir"
exit 0
