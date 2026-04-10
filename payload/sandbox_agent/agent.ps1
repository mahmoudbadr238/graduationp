#Requires -Version 5.1
<#
.SYNOPSIS
    Sentinel Sandbox Agent — persistent guest-side runner.

.DESCRIPTION
    Must run inside the INTERACTIVE desktop session via the "SentinelSandboxAgent"
    scheduled task (installed by install_agent.ps1).

    Flow:
      1) Read  C:\Sandbox\job.json  written by host
      2) Run   ui.ahk  for visible cursor/keyboard interaction
      3) Execute the sample (timed, visible)
      4) Collect behavioral evidence
      5) Write C:\Sandbox\out\summary.json + steps.jsonl + artifacts
      6) Write C:\Sandbox\out\done.flag   (host polls for this)
      7) Delete C:\Sandbox\job.json       (signal "idle")

    If no job.json is present, the script exits immediately (idempotent).
    The scheduled task re-triggers for each new job.

.NOTES
    DEFENSIVE ONLY. No anti-VM tricks, no evasion, no exfiltration.
    The host (analyzer_dynamic.py) reverts to a clean snapshot after every run.
#>

Set-StrictMode -Off
$ErrorActionPreference = "Continue"

# ═══════════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════════

$AgentDir  = "C:\Sandbox\agent"
$JobFile   = "C:\Sandbox\job.json"
$OutDir    = "C:\Sandbox\out"
$ShotsDir  = "$OutDir\shots"
$StepsFile = "$OutDir\steps.jsonl"
$DoneFlag  = "$OutDir\done.flag"
$AhkScript = "$AgentDir\ui.ahk"

# Find AutoHotkey — portable copy in agent dir wins, then installed
function Find-AHK {
    $candidates = @(
        "$AgentDir\AutoHotkey64.exe",
        "$AgentDir\AutoHotkey.exe",
        "$env:ProgramFiles\AutoHotkey\v2\AutoHotkey64.exe",
        "$env:ProgramFiles\AutoHotkey\v2\AutoHotkey32.exe",
        "$env:ProgramFiles\AutoHotkey\AutoHotkey64.exe",
        "$env:ProgramFiles\AutoHotkey\AutoHotkey.exe",
        "${env:ProgramFiles(x86)}\AutoHotkey\AutoHotkey.exe"
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    return ""
}

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

$Script:Errors = [System.Collections.Generic.List[string]]::new()

function Write-Step {
    param([string]$Status, [string]$Message)
    $ts  = (Get-Date).ToString("HH:mm:ss")
    $obj = [ordered]@{ time = $ts; status = $Status; message = $Message }
    $line = ($obj | ConvertTo-Json -Compress)
    try {
        $line | Out-File -Append -Encoding UTF8 -FilePath $StepsFile
    } catch {}
    # Also write to Windows Event Log (optional; ignore errors)
    try {
        Write-EventLog -LogName Application -Source "SentinelSandbox" `
                       -EntryType Information -EventId 1000 `
                       -Message "[$Status] $Message" -ErrorAction SilentlyContinue
    } catch {}
}

function Write-SandboxError { param([string]$Msg); $Script:Errors.Add($Msg); Write-Step "Failed" $Msg }

function Save-Json {
    param([string]$Path, [object]$Data)
    try {
        $Data | ConvertTo-Json -Depth 10 | Out-File -Encoding UTF8 -FilePath $Path
    } catch { Write-SandboxError "Save-Json failed for ${Path}: $_" }
}

# Screenshot using .NET — no external tools needed
$Script:ShotIdx = 0

function Save-Screenshot {
    param([string]$Label = "")
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        Add-Type -AssemblyName System.Drawing        -ErrorAction Stop
        $null = New-Item -ItemType Directory -Force -Path $ShotsDir
        $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $bmp = [System.Drawing.Bitmap]::new($b.Width, $b.Height)
        $g   = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
        $Script:ShotIdx++
        $fname = "shot_{0:D4}.png" -f $Script:ShotIdx
        $path  = Join-Path $ShotsDir $fname
        $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
        $g.Dispose(); $bmp.Dispose()
        Write-Step "OK" "Screenshot: $fname $(if($Label){"[$Label]"})"
        return $path
    } catch {
        Write-SandboxError "Screenshot failed: $_"
        return ""
    }
}

# P/Invoke for smooth mouse movement (visible even without AHK)
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Drawing;

public class SentinelMouse {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, int dx, int dy, uint d, UIntPtr e);
    [DllImport("user32.dll")] static extern bool GetCursorPos(out Point p);
    [DllImport("user32.dll")] public static extern int GetSystemMetrics(int n);

    public static void SmoothMove(int x, int y, int steps = 24) {
        Point pt; GetCursorPos(out pt);
        for (int i = 1; i <= steps; i++) {
            SetCursorPos(pt.X + (x - pt.X) * i / steps, pt.Y + (y - pt.Y) * i / steps);
            System.Threading.Thread.Sleep(16);
        }
    }
    public static void Click(int x, int y) {
        SmoothMove(x, y);
        System.Threading.Thread.Sleep(80);
        mouse_event(2, 0, 0, 0, UIntPtr.Zero);
        System.Threading.Thread.Sleep(60);
        mouse_event(4, 0, 0, 0, UIntPtr.Zero);
    }
    public static int W() { return GetSystemMetrics(0); }
    public static int H() { return GetSystemMetrics(1); }
}
"@ -ReferencedAssemblies "System.Drawing" -ErrorAction SilentlyContinue

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK FOR JOB
# ═══════════════════════════════════════════════════════════════════════════════

if (-not (Test-Path $JobFile)) {
    # No job pending — exit silently (task will be re-triggered by host)
    exit 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# PARSE JOB
# ═══════════════════════════════════════════════════════════════════════════════

$job = $null
try {
    $job = Get-Content $JobFile -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Write-Step "Failed" "Could not parse job.json: $_"
    exit 1
}

$JobId         = $job.job_id
$SamplePath    = $job.sample_path
$MonitorSecs   = if ($job.monitor_seconds) { [int]$job.monitor_seconds } else { 30 }
$DisableNet    = [bool]$job.disable_network
$SampleName    = [IO.Path]::GetFileName($SamplePath)

# ═══════════════════════════════════════════════════════════════════════════════
# SETUP OUTPUT DIR
# ═══════════════════════════════════════════════════════════════════════════════

$null = New-Item -ItemType Directory -Force -Path $OutDir
$null = New-Item -ItemType Directory -Force -Path $ShotsDir

# Clear previous run artifacts
@("summary.json","steps.jsonl","done.flag","processes_before.json",
  "processes_after.json","connections.txt","new_files.json","errors.txt") |
    ForEach-Object { $p = Join-Path $OutDir $_; if (Test-Path $p) { Remove-Item $p -Force } }

Write-Step "Running" "Agent started | Job: $JobId | Sample: $SampleName | Session: $(whoami)"
Write-Step "OK"      "Monitor: ${MonitorSecs}s | DisableNet: $DisableNet"

# ─── Session check ─────────────────────────────────────────────────────────
$explorerOk = @(Get-Process -Name "explorer" -ErrorAction SilentlyContinue).Count -gt 0
if (-not $explorerOk) {
    Write-Step "Failed" "explorer.exe not found — guest may not be logged in interactively. Configure auto-login (netplwiz) for visible GUI automation."
}

$null = Save-Screenshot "startup"

# ═══════════════════════════════════════════════════════════════════════════════
# VISIBLE GUI INTERACTION (AHK or Win32 fallback)
# ═══════════════════════════════════════════════════════════════════════════════

Write-Step "Running" "Starting visible GUI interaction"

$AhkExe = Find-AHK

if ($AhkExe -and (Test-Path $AhkScript)) {
    Write-Step "OK" "AutoHotkey found: $AhkExe — launching ui.ahk"
    try {
        $ahkArgs = @($AhkScript, $SamplePath, $OutDir, $MonitorSecs.ToString())
        $ahkProc = Start-Process -FilePath $AhkExe -ArgumentList $ahkArgs `
                                 -PassThru -WindowStyle Normal -ErrorAction Stop
        # Wait up to 35s for AHK visible sequence to finish
        $null = $ahkProc.WaitForExit(35000)
        Write-Step "OK" "AHK interaction complete (exit: $($ahkProc.ExitCode))"
    } catch {
        Write-SandboxError "AHK launch failed: $_ — falling back to Win32"
        $AhkExe = ""
    }
}

if (-not $AhkExe -or -not (Test-Path $AhkScript)) {
    # ── Win32 API fallback: visible mouse sweep + Notepad annotation ──────────
    Write-Step "Running" "Win32 fallback: visible mouse + Notepad annotation"
    try {
        $sw = [SentinelMouse]::W()
        $sh = [SentinelMouse]::H()
        $cx = $sw / 2; $cy = $sh / 2

        # Smooth arc across screen
        [SentinelMouse]::SmoothMove([int]$cx, [int]$cy, 30)
        Start-Sleep -Milliseconds 300
        [SentinelMouse]::SmoothMove([int]($sw * 0.25), [int]($sh * 0.25), 24)
        Start-Sleep -Milliseconds 200
        [SentinelMouse]::SmoothMove([int]($sw * 0.75), [int]($sh * 0.75), 24)
        Start-Sleep -Milliseconds 200
        [SentinelMouse]::SmoothMove([int]$cx, [int]$cy, 24)

        Write-Step "OK" "Visible mouse sweep complete"
        $null = Save-Screenshot "mouse-sweep"

        # Open Notepad with analysis annotation
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
        $np = Start-Process notepad.exe -PassThru -WindowStyle Normal
        Start-Sleep -Seconds 2
        [System.Windows.Forms.SendKeys]::SendWait(
            "Sentinel Sandbox Analysis{ENTER}Job: $JobId{ENTER}Sample: $SampleName{ENTER}Status: Detonating...{ENTER}"
        )
        $null = Save-Screenshot "notepad-open"
        Start-Sleep -Seconds 1

        # Close Notepad (discard)
        if ($np -and -not $np.HasExited) {
            $np.CloseMainWindow() | Out-Null
            Start-Sleep -Milliseconds 600
            [System.Windows.Forms.SendKeys]::SendWait("%{F4}")
            Start-Sleep -Milliseconds 400
            if (-not $np.HasExited) { try { $np.Kill() } catch {} }
        }
        Write-Step "OK" "Notepad annotation done"
    } catch {
        Write-SandboxError "Win32 GUI fallback failed: $_"
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 10 — BASELINE SNAPSHOT
# ═══════════════════════════════════════════════════════════════════════════════

Write-Step "Running" "[10] Pre-execution baseline"

$procsBefore = @()
try {
    $procsBefore = Get-CimInstance Win32_Process |
        Select-Object @{n='pid';e={$_.ProcessId}}, @{n='ppid';e={$_.ParentProcessId}},
                      @{n='name';e={$_.Name}},     @{n='cmdline';e={$_.CommandLine -replace "`r`n"," "}}
    Save-Json -Path "$OutDir\processes_before.json" -Data $procsBefore
    Write-Step "OK" "Process baseline: $($procsBefore.Count) processes"
} catch { Write-SandboxError "Process baseline failed: $_" }

try {
    (netstat -ano 2>&1) | Out-File -Encoding UTF8 "$OutDir\connections.txt"
    Write-Step "OK" "Network baseline captured"
} catch { Write-SandboxError "netstat failed: $_" }

$MonitoredDirs = @($env:TEMP, "$env:USERPROFILE\Desktop", "$env:USERPROFILE\Downloads", $OutDir) |
    Where-Object { $_ -and (Test-Path $_) }

$fsBase = @{}
foreach ($d in $MonitoredDirs) {
    try {
        $fsBase[$d] = Get-ChildItem -Path $d -Recurse -Force -ErrorAction SilentlyContinue |
            Select-Object FullName, LastWriteTimeUtc, Length
    } catch {}
}

if ($DisableNet) {
    try {
        Get-NetAdapter | Disable-NetAdapter -Confirm:$false -ErrorAction SilentlyContinue
        Write-Step "OK" "Network adapters disabled"
    } catch { Write-SandboxError "Could not disable network: $_" }
}

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 11 — EXECUTE SAMPLE
# ═══════════════════════════════════════════════════════════════════════════════

Write-Step "Running" "[11] Executing: $SampleName"
$null = Save-Screenshot "pre-execute"

$executed = $false; $exitCode = $null; $durationSec = 0.0
$proc = $null; $startTime = Get-Date
$ext = [IO.Path]::GetExtension($SamplePath).ToLower()
$runnable = $ext -in @('.exe','.scr','.com')

if (-not (Test-Path $SamplePath)) {
    Write-SandboxError "Sample not found: $SamplePath"
} elseif (-not $runnable) {
    Write-Step "Running" "Non-executable ($ext) — static analysis only"
} else {
    try {
        $proc = Start-Process -FilePath $SamplePath -PassThru -WindowStyle Normal -ErrorAction Stop
        $executed = $true
        Write-Step "OK" "Sample launched visibly — PID $($proc.Id)"
        $null = Save-Screenshot "launched"

        $deadline = $startTime.AddSeconds($MonitorSecs)
        $lastShot  = Get-Date

        while ((Get-Date) -lt $deadline) {
            if ($proc.HasExited) { $exitCode = $proc.ExitCode; Write-Step "OK" "Exited: $exitCode"; break }
            if (((Get-Date) - $lastShot).TotalSeconds -ge 5) {
                $null = Save-Screenshot "monitoring"
                $lastShot = Get-Date
            }
            Start-Sleep -Milliseconds 500
        }

        if (-not $proc.HasExited) {
            Write-Step "Running" "Timeout — killing sample"
            try { $proc.Kill(); $proc.WaitForExit(5000) | Out-Null; $exitCode = -1 } catch {}
            Write-Step "OK" "Sample terminated"
        }

        $durationSec = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 2)
        Write-Step "OK" "Duration: ${durationSec}s"
        $null = Save-Screenshot "post-execute"
    } catch { Write-SandboxError "Launch failed: $_" }
}

Start-Sleep -Seconds 3

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 12 — POST-EXECUTION DIFF
# ═══════════════════════════════════════════════════════════════════════════════

Write-Step "Running" "[12] Post-execution diff"

$procsAfter = @()
try {
    $procsAfter = Get-CimInstance Win32_Process |
        Select-Object @{n='pid';e={$_.ProcessId}}, @{n='ppid';e={$_.ParentProcessId}},
                      @{n='name';e={$_.Name}},     @{n='cmdline';e={$_.CommandLine -replace "`r`n"," "}}
    Save-Json -Path "$OutDir\processes_after.json" -Data $procsAfter
} catch { Write-SandboxError "Post-process snapshot failed: $_" }

$pidsBefore = $procsBefore | ForEach-Object { $_.pid }
$newProcs   = @($procsAfter | Where-Object { $_.pid -notin $pidsBefore })

$newFiles = [System.Collections.Generic.List[object]]::new()
$modFiles = [System.Collections.Generic.List[object]]::new()

foreach ($d in $MonitoredDirs) {
    try {
        $cur = Get-ChildItem -Path $d -Recurse -Force -ErrorAction SilentlyContinue |
            Select-Object FullName, LastWriteTimeUtc, Length
        $bmap = @{}
        if ($fsBase.ContainsKey($d)) { foreach ($f in $fsBase[$d]) { if ($f.FullName) { $bmap[$f.FullName] = $f } } }
        foreach ($f in $cur) {
            if (-not $f.FullName) { continue }
            if ($bmap.ContainsKey($f.FullName)) {
                if ($f.LastWriteTimeUtc -gt $bmap[$f.FullName].LastWriteTimeUtc) {
                    $modFiles.Add([PSCustomObject]@{ path=$f.FullName; action="modified"; size=$f.Length })
                }
            } else {
                $newFiles.Add([PSCustomObject]@{ path=$f.FullName; action="created"; size=$f.Length })
            }
        }
    } catch {}
}

Save-Json -Path "$OutDir\new_files.json" -Data @($newFiles + $modFiles)

$alerts = [System.Collections.Generic.List[string]]::new()
foreach ($p in $newProcs) { $alerts.Add("New process: $($p.name) [PID $($p.pid)]") }
if ($newFiles.Count -gt 0) { $alerts.Add("$($newFiles.Count) new file(s) created") }
if ($modFiles.Count -gt 0) { $alerts.Add("$($modFiles.Count) file(s) modified") }
if ($exitCode -eq -1)      { $alerts.Add("Sample forcibly terminated after ${MonitorSecs}s") }

Write-Step "OK" "Diff: +$($newProcs.Count) procs | +$($newFiles.Count) new files | $($modFiles.Count) modified | $($alerts.Count) alerts"

# ═══════════════════════════════════════════════════════════════════════════════
# WRITE ARTIFACTS
# ═══════════════════════════════════════════════════════════════════════════════

$summary = [ordered]@{
    job_id                  = $JobId
    sample_name             = $SampleName
    executed                = $executed
    exit_code               = $exitCode
    duration_sec            = $durationSec
    started_at              = $startTime.ToUniversalTime().ToString("o")
    finished_at             = (Get-Date).ToUniversalTime().ToString("o")
    monitor_seconds         = $MonitorSecs
    network_disabled        = $DisableNet
    interactive_session     = $explorerOk
    screenshots_count       = $Script:ShotIdx
    ahk_used                = ($AhkExe -ne "")
    new_processes           = @($newProcs)
    new_files               = @($newFiles)
    modified_files          = @($modFiles)
    new_connections         = @()
    process_snapshot_before = @($procsBefore | Select-Object -First 100)
    process_snapshot_after  = @($procsAfter  | Select-Object -First 100)
    alerts                  = @($alerts)
    errors                  = @($Script:Errors)
}

Save-Json -Path "$OutDir\summary.json" -Data $summary

if ($Script:Errors.Count -gt 0) {
    $Script:Errors | Out-File -Encoding UTF8 "$OutDir\errors.txt"
}

$null = Save-Screenshot "final"

Write-Step "OK" "Artifacts written | executed=$executed alerts=$($alerts.Count) shots=$($Script:ShotIdx)"

# ─── Done flag (host polls for this) ─────────────────────────────────────────
(Get-Date).ToUniversalTime().ToString("o") | Out-File -Encoding UTF8 $DoneFlag
Write-Step "OK" "done.flag written"

# ─── Remove job file so task is "idle" again ─────────────────────────────────
try { Remove-Item $JobFile -Force -ErrorAction Stop } catch {}

exit 0
