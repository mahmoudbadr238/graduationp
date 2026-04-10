#Requires -Version 5.1
<#
.SYNOPSIS
    Sentinel Interactive Sandbox Agent — defensive malware analysis with visible GUI.

.DESCRIPTION
    This script MUST run inside the guest VM in the ACTIVE INTERACTIVE desktop session
    (launched via schtasks /it from bootstrap_interactive.ps1, NOT directly from vmrun).

    It performs:
      1) Visible mouse movement and UI interaction (AHK if available, else Win32 API)
      2) Pre-execution baseline snapshot (processes, network, filesystem)
      3) Visible sample detonation via Start-Process
      4) Periodic in-guest screenshots to shots\ subdirectory
      5) Post-execution behavioral diff
      6) Writes all artifacts (summary.json, steps.jsonl, new_files.json, etc.)
      7) Writes agent_done.flag when complete so host knows to fetch artifacts

    SAFETY: DEFENSIVE-ONLY. No anti-VM tricks, no exfiltration, no evasion.
    The caller (analyzer_dynamic.py) reverts the VM before AND after every run.

.PARAMETER JobId
    Unique job identifier (set by host).

.PARAMETER SamplePath
    Full path to the sample in the guest.

.PARAMETER JobDir
    Full path to the job directory in the guest.

.PARAMETER MonitorSeconds
    How many seconds to monitor execution. Default: 30.

.PARAMETER DisableNetwork
    If set, disable all network adapters before detonation.

.PARAMETER AhkPath
    Optional: path to AutoHotkey.exe. If empty, auto-detected.

.NOTES
    Called via:
        schtasks /create /tn SentinelJob_<id> /tr "powershell.exe -File run_sandbox_ui.ps1 ..." /sc ONCE /st 00:00 /f /it /rl HIGHEST
        schtasks /run /tn SentinelJob_<id>
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$JobId,
    [Parameter(Mandatory=$true)][string]$SamplePath,
    [Parameter(Mandatory=$true)][string]$JobDir,
    [int]$MonitorSeconds = 30,
    [switch]$DisableNetwork,
    [string]$AhkPath = ""
)

Set-StrictMode -Off
$ErrorActionPreference = "Continue"

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

$Script:Steps  = [System.Collections.Generic.List[string]]::new()
$Script:Errors = [System.Collections.Generic.List[string]]::new()

function Write-Step {
    param([string]$Status, [string]$Message)
    $ts  = (Get-Date).ToString("HH:mm:ss")
    $obj = [ordered]@{ time = $ts; status = $Status; message = $Message }
    $line = ($obj | ConvertTo-Json -Compress)
    $Script:Steps.Add($line)
    try {
        $line | Out-File -Append -Encoding UTF8 -FilePath (Join-Path $JobDir "steps.jsonl")
    } catch {}
    Write-Verbose "[$ts][$Status] $Message"
}

function Write-SandboxError {
    param([string]$Msg)
    $Script:Errors.Add($Msg)
    Write-Step "Failed" $Msg
}

function Save-Json {
    param([string]$Path, [object]$Data)
    try {
        $Data | ConvertTo-Json -Depth 10 -Compress | Out-File -Encoding UTF8 -FilePath $Path
    } catch {
        Write-SandboxError "Save-Json failed for ${Path}: $_"
    }
}

# ── Screenshot helper (no external tools needed) ─────────────────────────────
$Script:ShotIndex = 0
$Script:ShotsDir  = Join-Path $JobDir "shots"

function Save-Screenshot {
    param([string]$Label = "")
    try {
        Add-Type -AssemblyName System.Windows.Forms  -ErrorAction Stop
        Add-Type -AssemblyName System.Drawing        -ErrorAction Stop

        $null = New-Item -ItemType Directory -Force -Path $Script:ShotsDir

        $bounds  = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $bmp     = [System.Drawing.Bitmap]::new($bounds.Width, $bounds.Height)
        $g       = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)

        $Script:ShotIndex++
        $fname = "shot_{0:D4}.png" -f $Script:ShotIndex
        $path  = Join-Path $Script:ShotsDir $fname
        $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
        $g.Dispose(); $bmp.Dispose()

        Write-Step "OK" "Screenshot: $fname  $(if($Label){"[$Label]"})"
        return $path
    } catch {
        Write-SandboxError "Screenshot failed: $_"
        return ""
    }
}

# ── Win32 Mouse / Keyboard (P/Invoke) ─────────────────────────────────────────
Add-Type @"
using System;
using System.Runtime.InteropServices;

public class SentinelInput {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, int dx, int dy, uint data, UIntPtr extra);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern int  GetSystemMetrics(int nIndex);

    public const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
    public const uint MOUSEEVENTF_LEFTUP   = 0x0004;
    public const uint MOUSEEVENTF_MOVE     = 0x0001;

    public static void SmoothMove(int x, int y, int steps = 20) {
        bool dummy; int cx, cy;
        var pt = new System.Drawing.Point();
        GetCursorPos(out pt);
        cx = pt.X; cy = pt.Y;
        for (int i = 1; i <= steps; i++) {
            int nx = cx + (x - cx) * i / steps;
            int ny = cy + (y - cy) * i / steps;
            SetCursorPos(nx, ny);
            System.Threading.Thread.Sleep(18);
        }
    }

    [DllImport("user32.dll")] static extern bool GetCursorPos(out System.Drawing.Point p);

    public static void Click(int x, int y) {
        SmoothMove(x, y);
        System.Threading.Thread.Sleep(80);
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, UIntPtr.Zero);
        System.Threading.Thread.Sleep(60);
        mouse_event(MOUSEEVENTF_LEFTUP,   0, 0, 0, UIntPtr.Zero);
    }

    public static int ScreenW() { return GetSystemMetrics(0); }
    public static int ScreenH() { return GetSystemMetrics(1); }
}
"@ -ReferencedAssemblies "System.Drawing" -ErrorAction SilentlyContinue

# ── Find AutoHotkey ───────────────────────────────────────────────────────────
function Find-AHK {
    if ($AhkPath -and (Test-Path $AhkPath)) { return $AhkPath }
    $candidates = @(
        "$env:ProgramFiles\AutoHotkey\v2\AutoHotkey64.exe",
        "$env:ProgramFiles\AutoHotkey\v2\AutoHotkey32.exe",
        "$env:ProgramFiles\AutoHotkey\AutoHotkey64.exe",
        "$env:ProgramFiles\AutoHotkey\AutoHotkey.exe",
        "$env:ProgramFiles(x86)\AutoHotkey\AutoHotkey.exe",
        (Join-Path $JobDir "AutoHotkey64.exe"),
        (Join-Path $JobDir "AutoHotkey.exe")
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    return ""
}

$AhkExe = Find-AHK
$AhkAvailable = $AhkExe.Length -gt 0

# ═══════════════════════════════════════════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════════════════════════════════════════

Write-Step "Running" "Interactive agent started — Job: $JobId  |  Session: $(whoami)"
Write-Step "OK"      "AHK: $(if($AhkAvailable){"Found: $AhkExe"}else{"Not installed — using Win32 API fallback"})"

try {
    New-Item -ItemType Directory -Force -Path $JobDir   | Out-Null
    New-Item -ItemType Directory -Force -Path $Script:ShotsDir | Out-Null
    Write-Step "OK" "Directories ready"
} catch {
    Write-SandboxError "Directory setup failed: $_"
}

# Initial screenshot (shows desktop / locked screen state)
$null = Save-Screenshot "startup"
Write-Step "OK" "Initial state captured"

# ─── Session / auto-login check ──────────────────────────────────────────────
$explorerRunning = @(Get-Process -Name "explorer" -ErrorAction SilentlyContinue).Count -gt 0
if (-not $explorerRunning) {
    Write-Step "Failed" "SETUP REQUIRED: explorer.exe is not running — guest is not logged in interactively.  Configure auto-login: run 'netplwiz' in guest and uncheck 'Users must enter a user name and password'."
    # Continue anyway — screenshots will still capture what's visible
}

# ═══════════════════════════════════════════════════════════════════════════════
# VISIBLE GUI INTERACTION
# ═══════════════════════════════════════════════════════════════════════════════

Write-Step "Running" "Starting visible GUI interaction sequence"

if ($AhkAvailable) {
    # ── AHK path: copy sandbox_ui.ahk alongside this script and run it ──────
    $ahkScript = Join-Path $JobDir "sandbox_ui.ahk"
    if (-not (Test-Path $ahkScript)) {
        # sandbox_ui.ahk should have been deployed by host; try script dir
        $thisDirAhk = Join-Path (Split-Path $PSCommandPath -Parent) "sandbox_ui.ahk"
        if (Test-Path $thisDirAhk) {
            Copy-Item $thisDirAhk $ahkScript -Force
        }
    }

    if (Test-Path $ahkScript) {
        Write-Step "Running" "Launching AHK visible interaction: $ahkScript"
        try {
            $ahkArgs = @(
                $ahkScript,
                $SamplePath,
                $JobDir,
                $MonitorSeconds.ToString()
            )
            $ahkProc = Start-Process -FilePath $AhkExe -ArgumentList $ahkArgs `
                                     -PassThru -WindowStyle Normal -ErrorAction Stop
            # Give AHK ~30s to complete its visible sequence
            $null = $ahkProc.WaitForExit(30000)
            Write-Step "OK" "AHK interaction sequence completed (exit: $($ahkProc.ExitCode))"
        } catch {
            Write-SandboxError "AHK launch failed: $_  — falling back to Win32 API"
            $AhkAvailable = $false
        }
    } else {
        Write-Step "Running" "sandbox_ui.ahk not found in job dir — using Win32 API fallback"
        $AhkAvailable = $false
    }
}

if (-not $AhkAvailable) {
    # ── Win32 API fallback: visible mouse + Notepad demo ────────────────────
    try {
        $sw = [SentinelInput]::ScreenW()
        $sh = [SentinelInput]::ScreenH()
        $cx = [int]($sw / 2)
        $cy = [int]($sh / 2)

        Write-Step "Running" "Moving mouse to screen center ($cx, $cy)"
        [SentinelInput]::SmoothMove($cx, $cy, 30)
        Start-Sleep -Milliseconds 400
        Write-Step "OK" "Mouse at center"

        # Open Notepad visibly
        Write-Step "Running" "Opening Notepad for analysis annotation"
        $notepadProc = Start-Process -FilePath "notepad.exe" -PassThru -WindowStyle Normal
        Start-Sleep -Seconds 2

        # Type into Notepad using SendKeys
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
        [System.Windows.Forms.SendKeys]::SendWait("Sentinel Sandbox Analysis{ENTER}")
        [System.Windows.Forms.SendKeys]::SendWait("Job ID  : $JobId{ENTER}")
        [System.Windows.Forms.SendKeys]::SendWait("Sample  : $([IO.Path]::GetFileName($SamplePath)){ENTER}")
        [System.Windows.Forms.SendKeys]::SendWait("Status  : Detonating…{ENTER}")
        Start-Sleep -Seconds 1

        $null = Save-Screenshot "notepad-open"
        Write-Step "OK" "Notepad annotation visible"

        # Move mouse around to show activity
        [SentinelInput]::SmoothMove([int]($sw * 0.3), [int]($sh * 0.3), 25)
        Start-Sleep -Milliseconds 300
        [SentinelInput]::SmoothMove([int]($sw * 0.7), [int]($sh * 0.7), 25)
        Start-Sleep -Milliseconds 300
        [SentinelInput]::SmoothMove($cx, $cy, 25)

        $null = Save-Screenshot "mouse-demo"
        Write-Step "OK" "Visible mouse interaction complete"

        # Close Notepad
        if ($notepadProc -and -not $notepadProc.HasExited) {
            $notepadProc.CloseMainWindow() | Out-Null
            Start-Sleep -Milliseconds 800
            # Discard any "Save?" prompt
            [System.Windows.Forms.SendKeys]::SendWait("%{F4}")
            Start-Sleep -Milliseconds 400
            if (-not $notepadProc.HasExited) { $notepadProc.Kill() }
        }
        Write-Step "OK" "Notepad closed"
    } catch {
        Write-SandboxError "Win32 GUI interaction failed: $_"
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 10 — BASELINE SNAPSHOT
# ═══════════════════════════════════════════════════════════════════════════════

Write-Step "Running" "[10] Collecting pre-execution baseline"

$procsBefore = @()
try {
    $procsBefore = Get-CimInstance Win32_Process -ErrorAction Stop |
        Select-Object @{n='pid';e={$_.ProcessId}},
                      @{n='ppid';e={$_.ParentProcessId}},
                      @{n='name';e={$_.Name}},
                      @{n='cmdline';e={$_.CommandLine -replace "`r`n"," "}}
    Save-Json -Path (Join-Path $JobDir "processes_before.json") -Data $procsBefore
    Write-Step "OK" "Process baseline: $($procsBefore.Count) processes"
} catch {
    Write-SandboxError "Process baseline failed: $_"
}

try {
    (netstat -ano 2>&1) | Out-File -Encoding UTF8 -FilePath (Join-Path $JobDir "connections.txt")
    Write-Step "OK" "Network baseline captured"
} catch {
    Write-SandboxError "Network baseline failed: $_"
}

$MonitoredDirs = @(
    $env:TEMP,
    "$env:USERPROFILE\Desktop",
    "$env:USERPROFILE\Downloads",
    $JobDir
) | Where-Object { $_ -and (Test-Path $_) }

$fsBaseline = @{}
foreach ($dir in $MonitoredDirs) {
    try {
        $fsBaseline[$dir] = Get-ChildItem -Path $dir -Recurse -Force -ErrorAction SilentlyContinue |
            Select-Object FullName, LastWriteTimeUtc, Length
    } catch {}
}
Write-Step "OK" "Filesystem baseline collected for $($MonitoredDirs.Count) dirs"

# Disable network if requested
if ($DisableNetwork) {
    try {
        Get-NetAdapter | Disable-NetAdapter -Confirm:$false -ErrorAction SilentlyContinue
        Write-Step "OK" "Network adapters disabled"
    } catch {
        Write-SandboxError "Could not disable network: $_"
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 11 — EXECUTE SAMPLE
# ═══════════════════════════════════════════════════════════════════════════════

Write-Step "Running" "[11] Executing sample: $SamplePath"

$null = Save-Screenshot "pre-execution"

$executed    = $false
$exitCode    = $null
$durationSec = 0.0
$proc        = $null
$startTime   = Get-Date

$ext     = [IO.Path]::GetExtension($SamplePath).ToLower()
$runnable = $ext -in @('.exe', '.scr', '.com')

if (-not (Test-Path $SamplePath)) {
    Write-SandboxError "Sample not found in guest: $SamplePath"
} elseif (-not $runnable) {
    Write-Step "Running" "Non-executable extension '$ext' — static only"
} else {
    try {
        # Launch visibly (WindowStyle Normal so it's on-screen)
        $proc     = Start-Process -FilePath $SamplePath -PassThru -WindowStyle Normal -ErrorAction Stop
        $executed = $true
        Write-Step "OK" "Sample started visibly — PID $($proc.Id)"

        $null = Save-Screenshot "sample-launched"

        # Monitor loop — screenshot every 5 seconds
        $deadline    = $startTime.AddSeconds($MonitorSeconds)
        $shotInterval = 5
        $lastShot    = Get-Date

        while ((Get-Date) -lt $deadline) {
            if ($proc.HasExited) {
                $exitCode = $proc.ExitCode
                Write-Step "OK" "Sample exited — code: $exitCode"
                break
            }
            if (((Get-Date) - $lastShot).TotalSeconds -ge $shotInterval) {
                $null = Save-Screenshot "monitoring"
                $lastShot = Get-Date
            }
            Start-Sleep -Milliseconds 500
        }

        if (-not $proc.HasExited) {
            Write-Step "Running" "Timeout reached — terminating sample"
            try { $proc.Kill(); $proc.WaitForExit(5000) | Out-Null; $exitCode = -1 } catch {}
            Write-Step "OK" "Sample terminated"
        }

        $durationSec = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 2)
        Write-Step "OK" "Execution duration: ${durationSec}s"
        $null = Save-Screenshot "post-execution"

    } catch {
        Write-SandboxError "Failed to start sample: $_"
    }
}

Start-Sleep -Seconds 3

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 12 — POST-EXECUTION SNAPSHOT
# ═══════════════════════════════════════════════════════════════════════════════

Write-Step "Running" "[12] Collecting post-execution state"

$procsAfter = @()
try {
    $procsAfter = Get-CimInstance Win32_Process -ErrorAction Stop |
        Select-Object @{n='pid';e={$_.ProcessId}},
                      @{n='ppid';e={$_.ParentProcessId}},
                      @{n='name';e={$_.Name}},
                      @{n='cmdline';e={$_.CommandLine -replace "`r`n"," "}}
    Save-Json -Path (Join-Path $JobDir "processes_after.json") -Data $procsAfter
    Write-Step "OK" "Post-execution processes: $($procsAfter.Count)"
} catch {
    Write-SandboxError "Post-execution snapshot failed: $_"
}

$pidsBefore = $procsBefore | ForEach-Object { $_.pid }
$newProcs   = @($procsAfter | Where-Object { $_.pid -notin $pidsBefore })

$newFiles = [System.Collections.Generic.List[object]]::new()
$modFiles = [System.Collections.Generic.List[object]]::new()

foreach ($dir in $MonitoredDirs) {
    try {
        $current = Get-ChildItem -Path $dir -Recurse -Force -ErrorAction SilentlyContinue |
            Select-Object FullName, LastWriteTimeUtc, Length
        $baseMap = @{}
        if ($fsBaseline.ContainsKey($dir)) {
            foreach ($f in $fsBaseline[$dir]) { if ($f.FullName) { $baseMap[$f.FullName] = $f } }
        }
        foreach ($f in $current) {
            if (-not $f.FullName) { continue }
            if ($baseMap.ContainsKey($f.FullName)) {
                if ($f.LastWriteTimeUtc -gt $baseMap[$f.FullName].LastWriteTimeUtc) {
                    $modFiles.Add([PSCustomObject]@{ path=$f.FullName; action="modified"; size=$f.Length })
                }
            } else {
                $newFiles.Add([PSCustomObject]@{ path=$f.FullName; action="created"; size=$f.Length })
            }
        }
    } catch {}
}

Save-Json -Path (Join-Path $JobDir "new_files.json") -Data @($newFiles + $modFiles)
Write-Step "OK" "File diff: $($newFiles.Count) new, $($modFiles.Count) modified"

$alerts = [System.Collections.Generic.List[string]]::new()
foreach ($p in $newProcs) { $alerts.Add("New process: $($p.name) [PID $($p.pid)]") }
if ($newFiles.Count -gt 0) { $alerts.Add("$($newFiles.Count) new file(s) created") }
if ($modFiles.Count -gt 0) { $alerts.Add("$($modFiles.Count) file(s) modified") }
if ($exitCode -eq -1)      { $alerts.Add("Sample forcibly terminated after ${MonitorSeconds}s") }

Write-Step "OK" "Alerts detected: $($alerts.Count)"

# ═══════════════════════════════════════════════════════════════════════════════
# WRITE ARTIFACTS
# ═══════════════════════════════════════════════════════════════════════════════

Write-Step "Running" "Writing summary.json"

$summary = [ordered]@{
    job_id                  = $JobId
    sample_name             = [IO.Path]::GetFileName($SamplePath)
    executed                = $executed
    exit_code               = $exitCode
    duration_sec            = $durationSec
    started_at              = $startTime.ToUniversalTime().ToString("o")
    finished_at             = (Get-Date).ToUniversalTime().ToString("o")
    monitor_seconds         = $MonitorSeconds
    network_disabled        = [bool]$DisableNetwork
    ahk_used                = $AhkAvailable
    interactive_session     = $true
    screenshots_count       = $Script:ShotIndex
    new_processes           = @($newProcs)
    new_files               = @($newFiles)
    modified_files          = @($modFiles)
    new_connections         = @()
    process_snapshot_before = @($procsBefore | Select-Object -First 100)
    process_snapshot_after  = @($procsAfter  | Select-Object -First 100)
    alerts                  = @($alerts)
    errors                  = @($Script:Errors)
}

Save-Json -Path (Join-Path $JobDir "summary.json") -Data $summary

if ($Script:Errors.Count -gt 0) {
    $Script:Errors | Out-File -Encoding UTF8 -FilePath (Join-Path $JobDir "errors.txt")
}

Write-Step "OK" "summary.json written — executed=$executed  alerts=$($alerts.Count)  screenshots=$($Script:ShotIndex)"

# Final screenshot
$null = Save-Screenshot "final"

# ═══════════════════════════════════════════════════════════════════════════════
# WRITE DONE FLAG  (host polls for this to know job is complete)
# ═══════════════════════════════════════════════════════════════════════════════

$doneTs = (Get-Date).ToUniversalTime().ToString("o")
"done:$doneTs" | Out-File -Encoding UTF8 -FilePath (Join-Path $JobDir "agent_done.flag")

Write-Step "OK" "agent_done.flag written — interactive agent finished"

exit 0
