#Requires -Version 5.1
<#
.SYNOPSIS
    Sentinel Sandbox — interactive guest runner.

.DESCRIPTION
    Registered as the "SentinelSandboxAgent" scheduled task (ONLOGON /IT).
    Fires automatically whenever the VM boots from the clean snapshot.

    Flow:
      1) Poll for C:\Sandbox\job.json (host writes it; up to 5 min)
      2) If no job arrives → exit 0 silently  (idle boot)
      3) Verify interactive session (explorer.exe present)
      4) Pre-execution baseline (processes, network, filesystem)
      5) Launch AutoHotkey run_ui.ahk for visible mouse/keyboard activity
         — AHK opens the sample via Win+R; move mouse; annotate Notepad
      6) Also launch sample directly via Start-Process -WindowStyle Normal
         (belt-and-suspenders: AHK opens it, PS also opens it)
      7) Monitor until timeout or sample exits; screenshots every 5 s
      8) Post-execution diff (new processes, files, connections)
      9) Write C:\Sandbox\out\summary.json
     10) Write C:\Sandbox\out\done.flag  (host polls for this)
     11) Delete C:\Sandbox\job.json      (signal idle)

    SAFETY: no evasion, no anti-VM, no exfiltration.
    The host reverts to the clean snapshot after every job.
#>

Set-StrictMode -Off
$ErrorActionPreference = "Continue"

# ═══════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════
$AgentDir  = "C:\Sandbox\agent"
$JobFile   = "C:\Sandbox\job.json"
$OutDir    = "C:\Sandbox\out"
$ShotsDir  = "$OutDir\shots"
$StepsFile = "$OutDir\steps.jsonl"
$DoneFlag  = "$OutDir\done.flag"
$AhkScript = "$AgentDir\run_ui.ahk"

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
$Script:Errors  = [System.Collections.Generic.List[string]]::new()
$Script:ShotIdx = 0

function Write-Step {
    param([string]$Status, [string]$Message)
    $ts   = (Get-Date).ToString("HH:mm:ss")
    $obj  = [ordered]@{ time=$ts; status=$Status; message=$Message }
    $line = $obj | ConvertTo-Json -Compress
    try { $line | Out-File -Append -Encoding UTF8 $StepsFile } catch {}
}

function Write-SandboxError { param([string]$M); $Script:Errors.Add($M); Write-Step "Failed" $M }

function Save-Json {
    param([string]$Path, [object]$Data)
    try { $Data | ConvertTo-Json -Depth 10 | Out-File -Encoding UTF8 $Path } catch { Write-SandboxError "Save-Json $Path : $_" }
}

function Save-Screenshot {
    param([string]$Label = "")
    try {
        Add-Type -AssemblyName System.Windows.Forms,System.Drawing -ErrorAction Stop
        $null = New-Item -ItemType Directory -Force $ShotsDir
        $b   = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $bmp = [System.Drawing.Bitmap]::new($b.Width, $b.Height)
        $g   = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
        $Script:ShotIdx++
        $fname = "shot_{0:D4}.png" -f $Script:ShotIdx
        $bmp.Save("$ShotsDir\$fname", [System.Drawing.Imaging.ImageFormat]::Png)
        $g.Dispose(); $bmp.Dispose()
        Write-Step "OK" "Screenshot: $fname$(if($Label){" [$Label]"})"
        return "$ShotsDir\$fname"
    } catch { Write-SandboxError "Screenshot failed: $_"; return "" }
}

function Find-AHK {
    foreach ($c in @(
        "$AgentDir\AutoHotkey64.exe",
        "$AgentDir\AutoHotkey.exe",
        "$env:ProgramFiles\AutoHotkey\v2\AutoHotkey64.exe",
        "$env:ProgramFiles\AutoHotkey\v2\AutoHotkey32.exe",
        "$env:ProgramFiles\AutoHotkey\AutoHotkey64.exe",
        "$env:ProgramFiles\AutoHotkey\AutoHotkey.exe",
        "${env:ProgramFiles(x86)}\AutoHotkey\AutoHotkey.exe"
    )) { if ($c -and (Test-Path $c)) { return $c } }
    return ""
}

# Visible mouse movement via P/Invoke (works with or without AHK)
Add-Type @"
using System;
using System.Drawing;
using System.Runtime.InteropServices;
public class SandboxMouse {
    [DllImport("user32.dll")] static extern bool GetCursorPos(out Point p);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f,int dx,int dy,uint d,UIntPtr e);
    [DllImport("user32.dll")] public static extern int GetSystemMetrics(int n);
    public static void SmoothMove(int tx,int ty,int steps=24){
        Point cur; GetCursorPos(out cur);
        for(int i=1;i<=steps;i++){
            SetCursorPos(cur.X+(tx-cur.X)*i/steps, cur.Y+(ty-cur.Y)*i/steps);
            System.Threading.Thread.Sleep(16);
        }
    }
    public static void Click(int x,int y){
        SmoothMove(x,y,16);
        System.Threading.Thread.Sleep(80);
        mouse_event(2,0,0,0,UIntPtr.Zero);
        System.Threading.Thread.Sleep(50);
        mouse_event(4,0,0,0,UIntPtr.Zero);
    }
    public static int ScreenW(){ return GetSystemMetrics(0); }
    public static int ScreenH(){ return GetSystemMetrics(1); }
}
"@ -ReferencedAssemblies "System.Drawing" -ErrorAction SilentlyContinue

# ═══════════════════════════════════════════════════════════════
# STEP 1 — POLL FOR JOB.JSON
# ═══════════════════════════════════════════════════════════════
$null = New-Item -ItemType Directory -Force $OutDir

$job      = $null
$pollEnd  = (Get-Date).AddSeconds(300)  # wait up to 5 minutes

while ((Get-Date) -lt $pollEnd) {
    if (Test-Path $JobFile) {
        try {
            $job = Get-Content $JobFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($job.job_id) { break }
        } catch {}
    }
    Start-Sleep -Seconds 2
}

if ($null -eq $job) {
    # Idle boot with no job — exit silently
    exit 0
}

# ═══════════════════════════════════════════════════════════════
# JOB VARS
# ═══════════════════════════════════════════════════════════════
$JobId       = $job.job_id
$SamplePath  = $job.sample_path
$MonitorSecs = if ($job.monitor_seconds) { [int]$job.monitor_seconds } else { 30 }
$DisableNet  = [bool]$job.disable_network
$SampleName  = [IO.Path]::GetFileName($SamplePath)
$SampleExt   = [IO.Path]::GetExtension($SamplePath).ToLower()
$Runnable    = $SampleExt -in @('.exe','.scr','.com','.bat','.cmd','.ps1')

# Clear previous artifacts
@("summary.json","done.flag","errors.txt") | ForEach-Object {
    $p = "$OutDir\$_"; if (Test-Path $p) { Remove-Item $p -Force }
}
$null = New-Item -ItemType Directory -Force $ShotsDir

Write-Step "Running" "=== Job $JobId  |  Sample: $SampleName  |  Monitor: ${MonitorSecs}s ==="

# ═══════════════════════════════════════════════════════════════
# STEP 2 — VERIFY INTERACTIVE SESSION
# ═══════════════════════════════════════════════════════════════
$explorerProc = Get-Process -Name "explorer" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $explorerProc) {
    Write-SandboxError "INTERACTIVE SESSION NOT FOUND: explorer.exe is absent."
    Write-SandboxError "Fix: enable auto-login in the guest (netplwiz) so the user is logged in after snapshot restore."
    Save-Json "$OutDir\summary.json" @{
        job_id=$JobId; error="No interactive session (explorer.exe missing)";
        executed=$false; verdict="Error"; alerts=@(); errors=@($Script:Errors)
    }
    "$(Get-Date -Format o)" | Out-File -Encoding UTF8 $DoneFlag
    Remove-Item $JobFile -Force -ErrorAction SilentlyContinue
    exit 1
}
Write-Step "OK" "Interactive session confirmed (explorer PID $($explorerProc.Id))"
$null = Save-Screenshot "startup"

# ═══════════════════════════════════════════════════════════════
# STEP 3 — VERIFY SAMPLE EXISTS
# ═══════════════════════════════════════════════════════════════
if (-not (Test-Path $SamplePath)) {
    Write-SandboxError "Sample not found at: $SamplePath"
    Save-Json "$OutDir\summary.json" @{
        job_id=$JobId; error="Sample not found: $SamplePath";
        executed=$false; verdict="Error"; alerts=@($Script:Errors); errors=@($Script:Errors)
    }
    "$(Get-Date -Format o)" | Out-File -Encoding UTF8 $DoneFlag
    Remove-Item $JobFile -Force -ErrorAction SilentlyContinue
    exit 1
}
Write-Step "OK" "Sample confirmed: $SamplePath ($((Get-Item $SamplePath).Length) bytes)"

# ═══════════════════════════════════════════════════════════════
# STEP 4 — PRE-EXECUTION BASELINE
# ═══════════════════════════════════════════════════════════════
Write-Step "Running" "[4] Pre-execution baseline"

$procsBefore = @()
try {
    $procsBefore = Get-CimInstance Win32_Process |
        Select-Object @{n='pid';   e={$_.ProcessId}},
                      @{n='ppid';  e={$_.ParentProcessId}},
                      @{n='name';  e={$_.Name}},
                      @{n='cmdline';e={($_.CommandLine -replace "`r`n"," ")}}
    Save-Json "$OutDir\processes_before.json" $procsBefore
    Write-Step "OK" "Baseline: $($procsBefore.Count) processes"
} catch { Write-SandboxError "Process baseline failed: $_" }

try {
    (netstat -ano 2>&1) | Out-File -Encoding UTF8 "$OutDir\connections.txt"
} catch {}

$MonDirs = @($env:TEMP,"$env:USERPROFILE\Desktop","$env:USERPROFILE\Downloads") |
    Where-Object { $_ -and (Test-Path $_) }
$fsBase = @{}
foreach ($d in $MonDirs) {
    try {
        $fsBase[$d] = Get-ChildItem $d -Recurse -Force -ErrorAction SilentlyContinue |
            Select-Object FullName,LastWriteTimeUtc,Length
    } catch {}
}

if ($DisableNet) {
    try {
        Get-NetAdapter | Disable-NetAdapter -Confirm:$false -ErrorAction SilentlyContinue
        Write-Step "OK" "Network adapters disabled"
    } catch { Write-SandboxError "Could not disable network: $_" }
}

# ═══════════════════════════════════════════════════════════════
# STEP 5 — VISIBLE GUI INTERACTION (AHK + Win32 fallback)
# ═══════════════════════════════════════════════════════════════
Write-Step "Running" "[5] Starting visible GUI interaction"

$AhkExe  = Find-AHK
$AhkProc = $null

if ($AhkExe -and (Test-Path $AhkScript)) {
    Write-Step "OK" "AutoHotkey found: $AhkExe"
    try {
        $AhkProc = Start-Process -FilePath $AhkExe `
            -ArgumentList @($AhkScript, $SamplePath, $OutDir, $JobId) `
            -PassThru -WindowStyle Normal -ErrorAction Stop
        Write-Step "OK" "AHK launched (PID $($AhkProc.Id)) — visible mouse/keyboard active"
    } catch { Write-SandboxError "AHK launch failed: $_ – using Win32 fallback"; $AhkExe = "" }
}

if (-not $AhkExe) {
    # ── Win32 visible mouse sweep + Notepad annotation ────────────────────────
    Write-Step "Running" "Win32 fallback: visible mouse sweep"
    try {
        $sw = [SandboxMouse]::ScreenW(); $sh = [SandboxMouse]::ScreenH()
        $cx = $sw/2; $cy = $sh/2
        [SandboxMouse]::SmoothMove($cx, $cy, 30)
        Start-Sleep -Milliseconds 300
        [SandboxMouse]::SmoothMove($sw * 0.2, $sh * 0.2, 24)
        Start-Sleep -Milliseconds 200
        [SandboxMouse]::SmoothMove($sw * 0.8, $sh * 0.8, 24)
        Start-Sleep -Milliseconds 200
        [SandboxMouse]::SmoothMove($cx, $cy, 24)
        $null = Save-Screenshot "mouse-sweep"

        # Notepad annotation
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
        $np = Start-Process notepad.exe -PassThru -WindowStyle Normal
        Start-Sleep 1
        [System.Windows.Forms.SendKeys]::SendWait(
            "Sentinel Sandbox{ENTER}Job: $JobId{ENTER}Sample: $SampleName{ENTER}Status: Detonating...{ENTER}"
        )
        $null = Save-Screenshot "notepad"
        Start-Sleep 1
        if ($np -and -not $np.HasExited) {
            $np.CloseMainWindow() | Out-Null
            Start-Sleep -Milliseconds 500
            if (-not $np.HasExited) { try { $np.Kill() } catch {} }
        }
        Write-Step "OK" "Win32 GUI interaction done"
    } catch { Write-SandboxError "Win32 GUI failed: $_" }
}

# ═══════════════════════════════════════════════════════════════
# STEP 6 — EXECUTE SAMPLE
# ═══════════════════════════════════════════════════════════════
Write-Step "Running" "[6] Executing sample: $SampleName"
$null = Save-Screenshot "pre-execute"

$executed   = $false
$exitCode   = $null
$durationSec = 0.0
$proc       = $null
$startTime  = Get-Date

if ($Runnable) {
    try {
        $proc     = Start-Process -FilePath $SamplePath -PassThru -WindowStyle Normal -ErrorAction Stop
        $executed = $true
        Write-Step "OK" "Sample launched visibly — PID $($proc.Id)"
        $null = Save-Screenshot "launched"

        $deadline  = $startTime.AddSeconds($MonitorSecs)
        $lastShot  = Get-Date
        while ((Get-Date) -lt $deadline) {
            if ($proc.HasExited) { $exitCode = $proc.ExitCode; break }
            if (((Get-Date) - $lastShot).TotalSeconds -ge 5) {
                $null = Save-Screenshot "monitoring"
                $lastShot = Get-Date
            }
            Start-Sleep -Milliseconds 500
        }
        if (-not $proc.HasExited) {
            try { $proc.Kill(); $proc.WaitForExit(5000) | Out-Null; $exitCode = -1 } catch {}
            Write-Step "OK" "Sample terminated after ${MonitorSecs}s timeout"
        }
        $durationSec = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 2)
    } catch { Write-SandboxError "Launch failed: $_" }
} else {
    Write-Step "Running" "Non-executable ($SampleExt) — skipping execution, static only"
}

# Wait for AHK to finish (if running)
if ($AhkProc -and -not $AhkProc.HasExited) {
    $null = $AhkProc.WaitForExit(15000)
}

Start-Sleep -Seconds 2
$null = Save-Screenshot "post-execute"

# ═══════════════════════════════════════════════════════════════
# STEP 7 — POST-EXECUTION DIFF
# ═══════════════════════════════════════════════════════════════
Write-Step "Running" "[7] Post-execution diff"

$procsAfter = @()
try {
    $procsAfter = Get-CimInstance Win32_Process |
        Select-Object @{n='pid';e={$_.ProcessId}},@{n='ppid';e={$_.ParentProcessId}},
                      @{n='name';e={$_.Name}},@{n='cmdline';e={($_.CommandLine -replace "`r`n"," ")}}
    Save-Json "$OutDir\processes_after.json" $procsAfter
} catch { Write-SandboxError "Post-process snapshot: $_" }

$pidsBefore = $procsBefore | ForEach-Object { $_.pid }
$newProcs   = @($procsAfter | Where-Object { $_.pid -notin $pidsBefore })

$newFiles = [System.Collections.Generic.List[object]]::new()
$modFiles = [System.Collections.Generic.List[object]]::new()
foreach ($d in $MonDirs) {
    try {
        $cur  = Get-ChildItem $d -Recurse -Force -ErrorAction SilentlyContinue |
                    Select-Object FullName,LastWriteTimeUtc,Length
        $bmap = @{}
        if ($fsBase.ContainsKey($d)) { foreach ($f in $fsBase[$d]) { if ($f.FullName) { $bmap[$f.FullName]=$f } } }
        foreach ($f in $cur) {
            if (-not $f.FullName) { continue }
            if ($bmap.ContainsKey($f.FullName)) {
                if ($f.LastWriteTimeUtc -gt $bmap[$f.FullName].LastWriteTimeUtc) {
                    $modFiles.Add([PSCustomObject]@{path=$f.FullName;action="modified";size=$f.Length})
                }
            } else {
                $newFiles.Add([PSCustomObject]@{path=$f.FullName;action="created";size=$f.Length})
            }
        }
    } catch {}
}
Save-Json "$OutDir\new_files.json" @($newFiles + $modFiles)

$alerts = [System.Collections.Generic.List[string]]::new()
foreach ($p in $newProcs)    { $alerts.Add("New process: $($p.name) [PID $($p.pid)]") }
if ($newFiles.Count -gt 0)   { $alerts.Add("$($newFiles.Count) new file(s) created") }
if ($modFiles.Count -gt 0)   { $alerts.Add("$($modFiles.Count) file(s) modified") }
if ($exitCode -eq -1)        { $alerts.Add("Sample force-terminated after ${MonitorSecs}s") }

Write-Step "OK" "Diff: +$($newProcs.Count) procs | +$($newFiles.Count) new files | $($modFiles.Count) modified"

$null = Save-Screenshot "final"

# ═══════════════════════════════════════════════════════════════
# STEP 8 — WRITE SUMMARY
# ═══════════════════════════════════════════════════════════════
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
    interactive_session     = ($null -ne $explorerProc)
    screenshots_count       = $Script:ShotIdx
    ahk_used                = ($AhkExe -ne "")
    new_processes           = @($newProcs)
    new_files               = @($newFiles)
    modified_files          = @($modFiles)
    process_snapshot_before = @($procsBefore | Select-Object -First 100)
    process_snapshot_after  = @($procsAfter  | Select-Object -First 100)
    alerts                  = @($alerts)
    errors                  = @($Script:Errors)
}
Save-Json "$OutDir\summary.json" $summary

if ($Script:Errors.Count -gt 0) {
    $Script:Errors | Out-File -Encoding UTF8 "$OutDir\errors.txt"
}

Write-Step "OK" "=== DONE | executed=$executed alerts=$($alerts.Count) shots=$($Script:ShotIdx) ==="

# ── Done flag (host polls for this) ──────────────────────────────────────────
(Get-Date).ToUniversalTime().ToString("o") | Out-File -Encoding UTF8 $DoneFlag

# ── Delete job.json (agent is idle again) ─────────────────────────────────────
Remove-Item $JobFile -Force -ErrorAction SilentlyContinue

exit 0
