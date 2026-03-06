# Sentinel – Interactive Session Launcher (Session 0 → Session 1 bridge)
# ─────────────────────────────────────────────────────────────────────────────
# Context: This script is executed by vmrun runProgramInGuest (Session 0,
#          no visible desktop, running as SYSTEM or a service account).
#
# Goal:    Start ui_runner.ps1 in the GUEST USER's interactive session
#          (Session 1) so the automation is VISIBLE on the VM desktop.
#
# Mechanism:
#   - Creates a Windows Scheduled Task under the guest user account credentials.
#   - Runs the task immediately via `schtasks /run`.
#   - Polls for the sentinel file C:\Sandbox\out\ui_runner_done.txt.
#   - Exits 0 when done (or on timeout).
#
# Parameters are passed by the Python host after substituting actual values.
# ─────────────────────────────────────────────────────────────────────────────
param(
    [Parameter(Mandatory=$true)] [string]$GuestUser,
    [Parameter(Mandatory=$true)] [string]$GuestPass,
    [Parameter(Mandatory=$true)] [string]$SamplePath,
    [Parameter(Mandatory=$true)] [string]$JobId,
    [int]   $MonitorSeconds = 60,
    [switch]$InspectOnly
)

$ErrorActionPreference = "Continue"

$taskName    = "SentinelUIRunner_$JobId"
$outDir      = "C:\Sandbox\out"
$doneFile    = "$outDir\ui_runner_done.txt"
$logFile     = "$outDir\launch_interactive_log.txt"
$runnerScript = "C:\Sandbox\jobs\$JobId\tools\ui_runner\ui_runner.ps1"

New-Item -ItemType Directory -Force -Path $outDir -ErrorAction SilentlyContinue | Out-Null

function Log([string]$msg) {
    $ts = (Get-Date -Format "HH:mm:ss.fff")
    $line = "[$ts] $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line -ErrorAction SilentlyContinue
}

Log "launch_interactive: starting for job=$JobId user=$GuestUser"
Log "  SamplePath = $SamplePath"
Log "  RunnerScript = $runnerScript"

# ── Verify runner script was deployed ─────────────────────────────────────────
if (-not (Test-Path $runnerScript)) {
    Log "ERROR: ui_runner.ps1 not found at $runnerScript. Deploy aborted."
    "ERROR: runner missing" | Out-File $doneFile -Encoding utf8 -Force
    exit 0
}

# ── Remove stale done-file ─────────────────────────────────────────────────────
Remove-Item $doneFile -Force -ErrorAction SilentlyContinue

# ── Build schtasks arguments ────────────────────────────────────────────────────
$inspectFlag = if ($InspectOnly) { " -InspectOnly" } else { "" }
# NOTE: Do NOT use -NonInteractive — it prevents visible windows.
# -WindowStyle Normal is passed to powershell.exe so it shows a window on the desktop.
$psArgs = "-ExecutionPolicy Bypass -WindowStyle Normal " +
          "-File `"$runnerScript`" " +
          "-SamplePath `"$SamplePath`" " +
          "-JobId `"$JobId`" " +
          "-MonitorSeconds $MonitorSeconds$inspectFlag"

# Delete any stale task with the same name
schtasks /delete /f /tn $taskName 2>&1 | Out-Null

# Create task.
# /ru + /rp  -> run under the interactive user's token.
# /it        -> INTERACTIVE flag: forces the task into the logged-in desktop session.
#              Without /it the task runs in Session 0 (hidden service desktop).
$createResult = schtasks /create /f `
    /tn $taskName `
    /sc once `
    /st 00:00 `
    /sd "01/01/2000" `
    /tr "powershell.exe $psArgs" `
    /ru "$GuestUser" `
    /rp "$GuestPass" `
    /it 2>&1

Log "schtasks /create → $($createResult -join ' ')"

# ── Run the task immediately ────────────────────────────────────────────────────
$runResult = schtasks /run /tn $taskName /i 2>&1
Log "schtasks /run → $($runResult -join ' ')"

# ── Poll for completion ────────────────────────────────────────────────────────
$totalWait  = $MonitorSeconds + 90          # extra headroom for startup
$deadline   = (Get-Date).AddSeconds($totalWait)
$pollSec    = 3
$elapsed    = 0

Log "Polling for done file every ${pollSec}s (timeout ${totalWait}s)…"

while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds $pollSec
    $elapsed += $pollSec

    if (Test-Path $doneFile) {
        $content = (Get-Content $doneFile -ErrorAction SilentlyContinue) -join " "
        Log "Done file found after ${elapsed}s: $content"
        break
    }

    # Also poll task status so we notice early completion / failure
    $taskStatus = (schtasks /query /tn $taskName /fo csv /nh 2>$null) -join ""
    if ($taskStatus -match '"Ready"' -or $taskStatus -match '"Disabled"') {
        Log "Scheduled task status = Ready/Disabled at ${elapsed}s — treating as finished"
        break
    }

    if (($elapsed % 15) -eq 0) {
        Log "Still waiting… task status: $taskStatus"
    }
}

if (-not (Test-Path $doneFile)) {
    Log "WARNING: Timed out waiting for ui_runner_done.txt after ${elapsed}s"
    "TIMEOUT" | Out-File $doneFile -Encoding utf8 -Force
}

# ── Cleanup task ───────────────────────────────────────────────────────────────
schtasks /delete /f /tn $taskName 2>&1 | Out-Null
Log "Task deleted. launch_interactive complete."
exit 0
