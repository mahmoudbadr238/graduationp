# Sentinel Guest UI Runner – v1
# ─────────────────────────────────────────────────────────────────────────────
# Runs INSIDE the guest VM in the INTERACTIVE desktop session (Session 1).
# Started by launch_interactive.ps1 via a scheduled task so the window is
# visible on screen and captured by vmrun captureScreen.
#
# Responsibilities:
#   1.  Take a baseline desktop screenshot.
#   2.  Launch the sample process with a visible window.
#   3.  Wait for the sample window to appear (up to 30 s).
#   4.  Attempt best-effort installer button clicks (Next / Install / Accept…).
#   5.  After install, attempt to open the installed app from Start.
#   6.  Capture a screenshot every ~1 s while running.
#   7.  Write C:\Sandbox\out\behavior.json + ui_runner_done.txt.
#
# Always exits 0 (infrastructure failure) or 0 (success). Never exits 1.
# ─────────────────────────────────────────────────────────────────────────────
param(
    [Parameter(Mandatory=$true)][string]$SamplePath,
    [int]   $MonitorSeconds = 60,
    [string]$JobId          = "unknown",
    [switch]$InspectOnly            # if set: launch but do NOT click installer
)

Set-StrictMode -Off
$ErrorActionPreference = "Continue"

# ── Paths ─────────────────────────────────────────────────────────────────────
$outDir    = "C:\Sandbox\out"
$framesDir = "$outDir\frames"
$doneFile  = "$outDir\ui_runner_done.txt"
$behavFile = "$outDir\behavior.json"

New-Item -ItemType Directory -Force -Path $framesDir -ErrorAction SilentlyContinue | Out-Null

# ── Step-marker helper ────────────────────────────────────────────────────────
# Writes C:\Sandbox\out\ui_step_N.txt so the host can verify visible progress.
$script:stepIndex = 0
function Write-UiStep([string]$Label) {
    $n    = ($script:stepIndex++).ToString("D2")
    $path = "$outDir\ui_step_$n.txt"
    $ts   = (Get-Date -Format "HH:mm:ss.fff")
    "$ts $Label" | Out-File -FilePath $path -Encoding utf8 -Force
    Write-Host "UI_STEP [$n] $Label"
}

# ── Assemblies ───────────────────────────────────────────────────────────────
Add-Type -AssemblyName System.Drawing          -ErrorAction SilentlyContinue
Add-Type -AssemblyName System.Windows.Forms    -ErrorAction SilentlyContinue
Add-Type -AssemblyName UIAutomationClient      -ErrorAction SilentlyContinue
Add-Type -AssemblyName UIAutomationTypes       -ErrorAction SilentlyContinue

# ── P/Invoke helpers ──────────────────────────────────────────────────────────
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class SentinelWin32 {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, int x, int y, uint data, UIntPtr extra);
    [DllImport("user32.dll")] public static extern IntPtr FindWindow(string cls, string title);
    [DllImport("user32.dll")] public static extern int  GetWindowThreadProcessId(IntPtr hwnd, out int pid);
    public const int SW_RESTORE   = 9;
    public const int SW_SHOWNA    = 8;
    public const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
    public const uint MOUSEEVENTF_LEFTUP   = 0x0004;
}
"@ -ErrorAction SilentlyContinue

# ── Screenshot helper ─────────────────────────────────────────────────────────
$script:frameIndex = 0
function Take-Screenshot {
    param([string]$DestDir = $framesDir)
    try {
        $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $bmp    = [System.Drawing.Bitmap]::new($bounds.Width, $bounds.Height)
        $gfx    = [System.Drawing.Graphics]::FromImage($bmp)
        $gfx.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
        $idx    = ($script:frameIndex++).ToString("D4")
        $path   = "$DestDir\frame_$idx.png"
        $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
        $gfx.Dispose(); $bmp.Dispose()
        return $path
    } catch {
        return ""
    }
}

# ── UIAutomation: find a button by name in the entire desktop ─────────────────
function Find-Button([string]$Name) {
    try {
        $nc = [System.Windows.Automation.PropertyCondition]::new(
                [System.Windows.Automation.AutomationElement]::NameProperty, $Name)
        $tc = [System.Windows.Automation.PropertyCondition]::new(
                [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
                [System.Windows.Automation.ControlType]::Button)
        $ac = [System.Windows.Automation.AndCondition]::new($nc, $tc)
        return [System.Windows.Automation.AutomationElement]::RootElement.FindFirst(
                   [System.Windows.Automation.TreeScope]::Descendants, $ac)
    } catch { return $null }
}

function Click-AutoElement([System.Windows.Automation.AutomationElement]$el) {
    if ($null -eq $el) { return $false }
    # Try Invoke pattern first
    try {
        $ip = $el.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
        ([System.Windows.Automation.InvokePattern]$ip).Invoke()
        return $true
    } catch {}
    # Fallback: simulate mouse click at element centre
    try {
        $r  = $el.Current.BoundingRectangle
        $cx = [int]($r.X + $r.Width / 2)
        $cy = [int]($r.Y + $r.Height / 2)
        [SentinelWin32]::SetCursorPos($cx, $cy) | Out-Null
        Start-Sleep -Milliseconds 80
        [SentinelWin32]::mouse_event([SentinelWin32]::MOUSEEVENTF_LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
        Start-Sleep -Milliseconds 60
        [SentinelWin32]::mouse_event([SentinelWin32]::MOUSEEVENTF_LEFTUP,   0, 0, 0, [UIntPtr]::Zero)
        return $true
    } catch { return $false }
}

# ── Try to click common installer / UAC-bypass buttons (best-effort) ──────────
# Standard installer button labels across NSIS / Inno / MSI / WiX / InstallShield
$INSTALLER_BUTTONS = @(
    "Next",    "Next >",     "&Next",     "&Next >",
    "Install", "&Install",   "Install Now",
    "Finish",  "&Finish",
    "I Agree", "I &Agree",   "I Accept",  "&I Agree",
    "Accept",  "&Accept",    "Accept and Install",
    "Yes",     "&Yes",
    "OK",      "&OK",
    "Continue","&Continue",
    "Run",     "&Run"
)

function Try-InstallerClick {
    foreach ($label in $INSTALLER_BUTTONS) {
        $btn = Find-Button $label
        if ($null -ne $btn) {
            $clicked = Click-AutoElement $btn
            if ($clicked) {
                Write-Host "UI_RUNNER: Clicked button [$label]"
                return $label
            }
        }
    }
    return $null
}

# ── Behavior record ───────────────────────────────────────────────────────────Write-UiStep "init"$behavior = [ordered]@{
    job_id          = $JobId
    sample_path     = $SamplePath
    started_at      = (Get-Date -Format "o")
    session_id      = -1
    session_active  = $false
    sample_launched = $false
    window_found    = $false
    buttons_clicked = [System.Collections.Generic.List[string]]::new()
    frames_captured = 0
    runtime_seconds = 0
    errors          = [System.Collections.Generic.List[string]]::new()
    inspect_only    = [bool]$InspectOnly
}

# ── Verify we're in an interactive session ────────────────────────────────────
Write-UiStep "session-check"
try {
    $wts = [System.Diagnostics.Process]::GetCurrentProcess().SessionId
    $behavior.session_id = $wts
    if ($wts -ge 1) {
        $behavior.session_active = $true
        Write-Host "UI_RUNNER: Running in session $wts (interactive OK)"
        Write-UiStep "session-active-$wts"
    } else {
        $msg = "Guest desktop session not active (Session 0). Enable auto-login so the VM boots to desktop."
        $behavior.errors.Add($msg)
        Write-Host "UI_RUNNER: ERROR – $msg"
        Write-UiStep "session-not-interactive"
        # Write done file with error so host detects early
        "ERROR: $msg" | Out-File $doneFile -Encoding utf8 -Force
        $behavior | ConvertTo-Json -Depth 5 | Out-File $behavFile -Encoding utf8 -Force
        exit 0
    }
} catch {
    $behavior.errors.Add("Could not determine session ID: $_")
}

# ── Ensure explorer (desktop shell) is running ────────────────────────────────
Write-UiStep "desktop-check"
$explorerRunning = (Get-Process -Name explorer -ErrorAction SilentlyContinue) -ne $null
if (-not $explorerRunning) {
    Write-Host "UI_RUNNER: explorer.exe not running – starting desktop shell"
    Start-Process explorer.exe
    Start-Sleep -Seconds 3
    Write-UiStep "desktop-started"
} else {
    Write-UiStep "desktop-ok"
}

# ── Briefly move the mouse to confirm interaction ─────────────────────────────
try {
    $cx = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width  / 2
    $cy = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height / 2
    [SentinelWin32]::SetCursorPos([int]$cx, [int]$cy) | Out-Null
    Start-Sleep -Milliseconds 300
    [SentinelWin32]::SetCursorPos([int]($cx + 40), [int]($cy + 40)) | Out-Null
    Start-Sleep -Milliseconds 200
    [SentinelWin32]::SetCursorPos([int]$cx, [int]$cy) | Out-Null
    Write-UiStep "mouse-moved"
} catch {
    Write-Host "UI_RUNNER: mouse_event error: $_"
}

# ── Baseline screenshot ───────────────────────────────────────────────────────Write-UiStep "baseline-screenshot"$baseFrame = Take-Screenshot
Write-Host "UI_RUNNER: Baseline frame → $baseFrame"

$startTime  = Get-Date
$deadline   = $startTime.AddSeconds($MonitorSeconds + 10)
$lastCapture = $startTime

# ── Launch sample ─────────────────────────────────────────────────────────────
$process = $null
Write-UiStep "launch-start"
if (-not (Test-Path $SamplePath)) {
    $behavior.errors.Add("Sample not found: $SamplePath")
    Write-Host "UI_RUNNER: ERROR – sample not found: $SamplePath"
    Write-UiStep "launch-sample-missing"
} else {
    try {
        $ext = [System.IO.Path]::GetExtension($SamplePath).ToLower()
        $psi = [System.Diagnostics.ProcessStartInfo]::new()
        $psi.UseShellExecute = $true
        $psi.WindowStyle     = [System.Diagnostics.ProcessWindowStyle]::Normal

        if ($ext -eq ".msi") {
            # Launch via msiexec so it shows the MSI UI
            $psi.FileName  = "msiexec.exe"
            $psi.Arguments = "/i `"$SamplePath`""
        } elseif ($ext -in @(".bat", ".cmd")) {
            $psi.FileName  = "cmd.exe"
            $psi.Arguments = "/c `"$SamplePath`""
        } elseif ($ext -in @(".ps1")) {
            $psi.FileName  = "powershell.exe"
            $psi.Arguments = "-ExecutionPolicy Bypass -File `"$SamplePath`""
        } elseif ($ext -in @(".vbs", ".js")) {
            $psi.FileName  = "wscript.exe"
            $psi.Arguments = "`"$SamplePath`""
        } else {
            # .exe and everything else
            $psi.FileName  = $SamplePath
            $psi.Arguments = ""
        }

        $process = [System.Diagnostics.Process]::Start($psi)
        $behavior.sample_launched = $true
        Write-Host "UI_RUNNER: Launched sample PID=$($process.Id) – $SamplePath"
        Write-UiStep "launch-ok-pid-$($process.Id)"
        Take-Screenshot | Out-Null   # capture immediately after launch
    } catch {
        $behavior.errors.Add("Launch failed: $_")
        Write-Host "UI_RUNNER: Launch error – $_"
        Write-UiStep "launch-failed"
    }
}

# ── Wait for sample window and capture loop ───────────────────────────────────
$windowFound      = $false
$windowFindDeadline = (Get-Date).AddSeconds(30)
$clickCooldown    = [DateTime]::MinValue  # don't click faster than every 3 s
$maxClicks        = 20
$clicksMade       = 0

while ((Get-Date) -lt $deadline) {

    # 1. Capture frame (throttle to ~1 fps)
    if (((Get-Date) - $lastCapture).TotalSeconds -ge 1.0) {
        $f = Take-Screenshot
        if ($f -ne "") { $behavior.frames_captured++ }
        $lastCapture = Get-Date
    }

    # 2. Detect sample window (once, in first 30 s)
    if (-not $windowFound -and $null -ne $process -and (Get-Date) -lt $windowFindDeadline) {
        try {
            $process.Refresh()
            if (-not $process.HasExited -and $process.MainWindowHandle -ne [IntPtr]::Zero) {
                [SentinelWin32]::ShowWindow($process.MainWindowHandle, [SentinelWin32]::SW_RESTORE) | Out-Null
                [SentinelWin32]::SetForegroundWindow($process.MainWindowHandle)                      | Out-Null
                $windowFound = $true
                $behavior.window_found = $true
                Write-Host "UI_RUNNER: Window found, HWND=$($process.MainWindowHandle)"
                Write-UiStep "window-found"
                Take-Screenshot | Out-Null
            }
        } catch {}
    }

    # 3. Attempt installer button clicks (execute mode, throttled)
    if (-not $InspectOnly -and $clicksMade -lt $maxClicks -and ((Get-Date) - $clickCooldown).TotalSeconds -ge 3) {
        $clicked = Try-InstallerClick
        if ($null -ne $clicked) {
            $behavior.buttons_clicked.Add($clicked)
            $clicksMade++
            $clickCooldown = Get-Date
            Write-UiStep "click-$($clicked -replace '[^a-zA-Z0-9]','-')"
            Start-Sleep -Milliseconds 600   # let UI settle
            Take-Screenshot | Out-Null      # capture the result
        }
    }

    # 4. Short sleep to keep CPU reasonable
    Start-Sleep -Milliseconds 400

    # 5. If sample has exited, run for up to $MonitorSeconds total then break
    if ($null -ne $process) {
        try {
            $process.Refresh()
            if ($process.HasExited -and ((Get-Date) - $startTime).TotalSeconds -gt 5) {
                Write-Host "UI_RUNNER: Process exited (code $($process.ExitCode))"
                # Capture a few more frames for post-exit state
                1..3 | ForEach-Object { Start-Sleep -Milliseconds 500; Take-Screenshot | Out-Null }
                break
            }
        } catch {}
    }
}

# ── Final screenshot ───────────────────────────────────────────────────────────Write-UiStep "final-screenshot"Take-Screenshot | Out-Null

# ── Finalize behavior record ──────────────────────────────────────────────────
$behavior.runtime_seconds = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 1)
$behavior.finished_at     = (Get-Date -Format "o")

# Summarize frame delta (simple: count non-baseline frames with different sizes)
$allFrames = Get-ChildItem -Path $framesDir -Filter "frame_*.png" -ErrorAction SilentlyContinue
$behavior.frames_captured = ($allFrames | Measure-Object).Count

# ── Detect if frames actually changed (compare file sizes as a fast proxy) ────
$framesSizes = $allFrames | Select-Object -ExpandProperty Length
$uniqueSizes  = ($framesSizes | Select-Object -Unique | Measure-Object).Count
$behavior.frames_changed = ($uniqueSizes -gt 1)

if (-not $behavior.frames_changed) {
    $behavior.errors.Add("WARNING: All frames appear identical – automation may have run non-interactively.")
    Write-Host "UI_RUNNER: WARNING – no visible frame changes detected"
}

# ── Collect ui_step marker list ────────────────────────────────────────────────
$stepFiles = Get-ChildItem -Path $outDir -Filter "ui_step_*.txt" -ErrorAction SilentlyContinue |
             Sort-Object Name
$uiSteps = $stepFiles | ForEach-Object { (Get-Content $_.FullName -ErrorAction SilentlyContinue) -join "" }
$behavior.ui_steps = [System.Collections.Generic.List[string]]$uiSteps

# ── Write behavior.json ────────────────────────────────────────────────────────
try {
    $behavior | ConvertTo-Json -Depth 5 | Out-File -FilePath $behavFile -Encoding utf8 -Force
    Write-Host "UI_RUNNER: behavior.json written → $behavFile"
} catch {
    Write-Host "UI_RUNNER: Could not write behavior.json: $_"
}

# ── Write sentinel (done) file ─────────────────────────────────────────────────
Write-UiStep "complete"
"done:$($behavior.runtime_seconds)s frames:$($behavior.frames_captured)" |
    Out-File -FilePath $doneFile -Encoding utf8 -Force

Write-Host "UI_RUNNER: Complete. $($behavior.frames_captured) frames, $($behavior.buttons_clicked.Count) clicks, $($behavior.runtime_seconds)s"
exit 0
