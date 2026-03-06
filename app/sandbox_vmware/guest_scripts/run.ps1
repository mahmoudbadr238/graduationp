# Sentinel Sandbox – File Detonation & Inspection Monitor (v2)
# Deployed to guest at runtime. Do NOT edit manually in the guest.
#
# Behaviour by file type:
#   .exe .bat .com .scr       → Run with timeout + monitor process/net/files
#   .msi .js .vbs .ps1 .wsf   → Inspect-only (metadata + strings) UNLESS -AllowRun
#   .zip                      → Extract with Expand-Archive + inspect
#   .rar .7z                  → Extract if 7-Zip installed, else warn + inspect
#   .pdf .doc .docx .xls .xlsx .ppt .pptx → Inspect metadata + strings + URLs
#   * (unknown)               → Inspect strings only
param(
    [Parameter(Mandatory=$true)][string]$SamplePath,
    [int]$MonitorSeconds    = 30,
    [switch]$DisableNetwork,
    [switch]$KillOnFinish,
    [switch]$AllowRun        # allow executing scripts / MSI / installers
)
$ErrorActionPreference = "Continue"   # non-critical analysis errors stay in $report.errors, never exit 1
$outDir = "C:\Sandbox\out"
try {
    New-Item -ItemType Directory -Force -Path $outDir -ErrorAction Stop | Out-Null
} catch {
    # Cannot even create the output directory — hard infrastructure failure
    Write-Host "FATAL: Cannot create outDir '$outDir': $_"
    # Try a fallback to TEMP
    $outDir = "$env:TEMP\SentinelSandbox"
    try { New-Item -ItemType Directory -Force -Path $outDir -ErrorAction Stop | Out-Null }
    catch {
        Write-Host "FATAL: Cannot create fallback outDir '$outDir': $_"
        exit 1
    }
}

# ── Start transcript immediately so every line is captured ───────────────────
$transcriptPath = "$outDir\guest_transcript.txt"
Start-Transcript -Path $transcriptPath -Force -ErrorAction SilentlyContinue

# ── Immediately log paths for diagnostics (visible in transcript + steps) ──────
Write-Host "SENTINEL_DIAG: SamplePath='$SamplePath' outDir='$outDir' ts=$(Get-Date -Format 'o')"

# ── Helper: write incremental step to steps.jsonl ────────────────────────────
$stepsFile = "$outDir\steps.jsonl"
function Write-Step([string]$Status, [string]$Message) {
    $entry = @{ time = (Get-Date -Format "o"); status = $Status; message = $Message }
    $entry | ConvertTo-Json -Compress | Out-File -FilePath $stepsFile -Append -Encoding utf8
}

#region ── Report skeleton ─────────────────────────────────────────────────────
$report = [ordered]@{
    sample              = $SamplePath
    started_at          = (Get-Date -Format "o")
    monitor_seconds     = $MonitorSeconds
    file_type_detected  = ""
    analysis_mode       = "inspect"    # "run" | "inspect" | "extract" | "static_only"
    executed            = $false
    alerts              = [System.Collections.Generic.List[string]]::new()
    processes           = [System.Collections.Generic.List[object]]::new()
    spawned_processes   = [System.Collections.Generic.List[object]]::new()
    files_created       = [System.Collections.Generic.List[string]]::new()
    extracted_files     = [System.Collections.Generic.List[string]]::new()
    registry_modified   = [System.Collections.Generic.List[string]]::new()
    network_connections = [System.Collections.Generic.List[string]]::new()
    dns_queries         = [System.Collections.Generic.List[string]]::new()
    strings_found       = [System.Collections.Generic.List[string]]::new()
    urls_found          = [System.Collections.Generic.List[string]]::new()
    iocs                = [ordered]@{ ips = @(); domains = @(); urls = @(); registry = @() }
    errors              = [System.Collections.Generic.List[string]]::new()
    highlights          = [System.Collections.Generic.List[string]]::new()
    metadata            = [ordered]@{}
}
#endregion

# ── Verify sample exists before proceeding ────────────────────────────────────
if (-not (Test-Path $SamplePath)) {
    $parentDir = Split-Path $SamplePath -Parent
    $dirListing = ""
    try {
        $dirListing = (Get-ChildItem -Path $parentDir -Force -ErrorAction SilentlyContinue |`
            Select-Object -Property Mode,LastWriteTime,Length,Name |`
            Format-Table -AutoSize | Out-String).Trim()
    } catch { $dirListing = "(Get-ChildItem failed: $_)" }
    $errDetail  = "FATAL: Sample not found at '$SamplePath' (outDir='$outDir') `— verify host→guest copy succeeded and guest_in_dir is correct`nParent folder listing of '$parentDir':`n$dirListing"
    Add-Content "$outDir\guest_error.txt" $errDetail -ErrorAction SilentlyContinue
    Write-Host $errDetail
    Write-Step "Failed" "Sample missing: $SamplePath — inspect Failure Details for folder listing"
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}
Write-Step "OK" "Sample confirmed: '$SamplePath' exists in guest"

try {

Write-Step "Running" "Starting analysis of $SamplePath"

# ── Detect file type ──────────────────────────────────────────────────────────
$ext = [System.IO.Path]::GetExtension($SamplePath).ToLower()
$header = $null
try {
    $bytes = [System.IO.File]::ReadAllBytes($SamplePath)
    if ($bytes.Length -ge 4) { $header = $bytes[0..3] }
} catch { $report.errors.Add("Could not read file header: $_") }

$fileType = "unknown"
if ($header) {
    if ($header[0] -eq 0x4D -and $header[1] -eq 0x5A) { $fileType = "PE" }
    elseif ($header[0] -eq 0x50 -and $header[1] -eq 0x4B) { $fileType = "ZIP" }
    elseif ($header[0] -eq 0x52 -and $header[1] -eq 0x61 -and $header[2] -eq 0x72) { $fileType = "RAR" }
    elseif ($header[0] -eq 0x37 -and $header[1] -eq 0x7A) { $fileType = "7Z" }
    elseif ($header[0] -eq 0x25 -and $header[1] -eq 0x50 -and $header[2] -eq 0x44 -and $header[3] -eq 0x46) { $fileType = "PDF" }
    elseif ($header[0] -eq 0xD0 -and $header[1] -eq 0xCF) { $fileType = "OLE2" }  # MSI, DOC, XLS, PPT
}
# Override by extension if header is ambiguous
if ($fileType -eq "unknown") {
    switch ($ext) {
        ".exe"   { $fileType = "PE" }
        ".bat"   { $fileType = "SCRIPT_BATCH" }
        ".ps1"   { $fileType = "SCRIPT_PS" }
        ".vbs"   { $fileType = "SCRIPT_VBS" }
        ".js"    { $fileType = "SCRIPT_JS" }
        ".wsf"   { $fileType = "SCRIPT_WSF" }
        ".msi"   { $fileType = "MSI" }
        ".zip"   { $fileType = "ZIP" }
        ".rar"   { $fileType = "RAR" }
        ".7z"    { $fileType = "7Z" }
        ".pdf"   { $fileType = "PDF" }
        ".doc"   { $fileType = "OLE2" }
        ".docx"  { $fileType = "OOXML" }
        ".xls"   { $fileType = "OLE2" }
        ".xlsx"  { $fileType = "OOXML" }
        ".ppt"   { $fileType = "OLE2" }
        ".pptx"  { $fileType = "OOXML" }
        default  { $fileType = "UNKNOWN" }
    }
}
$report.file_type_detected = $fileType
Write-Step "OK" "Detected file type: $fileType"

# ── Disable network if requested ──────────────────────────────────────────────
if ($DisableNetwork) {
    try {
        Get-NetAdapter | Disable-NetAdapter -Confirm:$false -ErrorAction SilentlyContinue
        $report.alerts.Add("Network adapters disabled before analysis.")
        Write-Step "OK" "Network disabled"
    } catch { $report.errors.Add("Could not disable network: $_") }
}

# ── Windows UI automation helper (for interactive runs) ──────────────────────
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class UIHelper2 {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, int x, int y, uint d, int e);
    public const uint LDOWN=0x02, LUP=0x04;
    public static void Click(int x, int y) {
        SetCursorPos(x, y); System.Threading.Thread.Sleep(110);
        mouse_event(LDOWN,0,0,0,0); System.Threading.Thread.Sleep(55);
        mouse_event(LUP,0,0,0,0);   System.Threading.Thread.Sleep(190);
    }
}
"@ -ErrorAction SilentlyContinue

# ── Helper: extract printable strings from binary ────────────────────────────
function Get-PrintableStrings([string]$Path, [int]$MinLen = 5, [int]$MaxCount = 200) {
    $result = [System.Collections.Generic.List[string]]::new()
    try {
        $raw = [System.IO.File]::ReadAllBytes($Path)
        $sb  = [System.Text.StringBuilder]::new()
        foreach ($b in $raw) {
            if ($b -ge 0x20 -and $b -lt 0x7F) { [void]$sb.Append([char]$b) }
            else {
                if ($sb.Length -ge $MinLen) { [void]$result.Add($sb.ToString()) }
                [void]$sb.Clear()
                if ($result.Count -ge $MaxCount) { break }
            }
        }
        if ($sb.Length -ge $MinLen) { [void]$result.Add($sb.ToString()) }
    } catch {}
    return ,$result
}

# ── Helper: extract IOCs from string list ─────────────────────────────────────
function Get-Iocs([System.Collections.Generic.List[string]]$Strings) {
    $ipRe      = [regex]::new('\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b')
    $urlRe     = [regex]::new('https?://[^\s"''<>]{4,200}', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    $domainRe  = [regex]::new('\b(?:[a-zA-Z0-9\-]{1,63}\.)+(?:com|net|org|info|io|ru|cn|biz|xyz)\b', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    $privateIp = [regex]::new('^(10\.|127\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|0\.0\.0\.0)')

    $ips = [System.Collections.Generic.HashSet[string]]::new()
    $urls= [System.Collections.Generic.HashSet[string]]::new()
    $domains=[System.Collections.Generic.HashSet[string]]::new()
    $blob = $Strings -join " "

    $ipRe.Matches($blob)     | ForEach-Object { if(-not $privateIp.IsMatch($_.Value)){[void]$ips.Add($_.Value)} }
    $urlRe.Matches($blob)    | ForEach-Object { [void]$urls.Add($_.Value) }
    $domainRe.Matches($blob) | ForEach-Object { [void]$domains.Add($_.Value) }

    return [ordered]@{
        ips     = @($ips     | Select-Object -First 30)
        urls    = @($urls    | Select-Object -First 20)
        domains = @($domains | Select-Object -First 30)
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Branch by file type
# ─────────────────────────────────────────────────────────────────────────────
$baseProcs    = @(Get-Process | Select-Object -ExpandProperty Id)
$monitorStart = Get-Date
$procHandle   = $null  # the launched process (if any)

switch -Regex ($fileType) {

    # ── Executable: RUN + monitor ─────────────────────────────────────────────
    "^(PE|SCRIPT_BATCH)$" {
        $report.analysis_mode = "run"
        Write-Step "Running" "Launching sample in interactive session: $SamplePath"

        # ── P/Invoke for mouse and cursor (visible activity) ──────────────────
        Add-Type -TypeDefinition @"
using System;using System.Runtime.InteropServices;
public class _Mse {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f,int x,int y,uint d,int e);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    public const uint LD=0x0002, LU=0x0004;
}
"@ -ErrorAction SilentlyContinue

        # ── Helper: smooth cursor movement (anti-evasion + visible activity) ──
        function Move-CursorSmooth([int]$tx,[int]$ty,[int]$steps=18) {
            try {
                $pos = [System.Windows.Forms.Cursor]::Position
                $cx  = $pos.X; $cy = $pos.Y
                for ($i=1; $i -le $steps; $i++) {
                    $frac = $i / $steps
                    [_Mse]::SetCursorPos([int]($cx+($tx-$cx)*$frac), [int]($cy+($ty-$cy)*$frac)) | Out-Null
                    Start-Sleep -Milliseconds 16
                }
            } catch {}
        }

        # ── Pre-launch: Desktop sweep (defeats sandbox-aware malware) ─────────
        try {
            Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
            $sw = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width
            $sh = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height
            Move-CursorSmooth ([int]($sw/2)) ([int]($sh/2))
            Start-Sleep -Milliseconds 200
            Move-CursorSmooth ([int]($sw*0.2)) ([int]($sh*0.2))
            Move-CursorSmooth ([int]($sw*0.8)) ([int]($sh*0.2))
            Move-CursorSmooth ([int]($sw*0.8)) ([int]($sh*0.8))
            Move-CursorSmooth ([int]($sw*0.2)) ([int]($sh*0.8))
            Move-CursorSmooth ([int]($sw/2)) ([int]($sh/2))
            Write-Step "OK" "Desktop sweep complete (anti-evasion)"
        } catch {
            Write-Step "Running" "Desktop sweep skipped: $_"
        }

        try {
            # ── Strategy 1: UseShellExecute with visible window ───────────────
            # This is the most reliable way to launch visibly in Session 1 because
            # ShellExecute honours the current desktop session.
            $psi = [System.Diagnostics.ProcessStartInfo]::new()
            $psi.UseShellExecute = $true
            $psi.WindowStyle     = [System.Diagnostics.ProcessWindowStyle]::Normal
            if ($fileType -eq "SCRIPT_BATCH") {
                $psi.FileName  = "cmd.exe"
                $psi.Arguments = "/c `"$SamplePath`""
            } else {
                $psi.FileName  = $SamplePath
                $psi.Arguments = ""
            }
            $procHandle = [System.Diagnostics.Process]::Start($psi)
            $report.executed = $true
            $report.highlights.Add("Sample executed (visible): $([System.IO.Path]::GetFileName($SamplePath))")
            Write-Step "OK" "Sample launched via ShellExecute PID=$($procHandle.Id)"

            # Give the process a moment to appear then track it
            Start-Sleep -Seconds 3

            # Bring sample window to foreground
            if ($procHandle -and -not $procHandle.HasExited) {
                try {
                    $procHandle.Refresh()
                    if ($procHandle.MainWindowHandle -ne [IntPtr]::Zero) {
                        [_Mse]::ShowWindow($procHandle.MainWindowHandle, 9) | Out-Null  # SW_RESTORE
                        [_Mse]::SetForegroundWindow($procHandle.MainWindowHandle)        | Out-Null
                        Write-Step "OK" "Sample window brought to foreground"
                    }
                } catch {}
            }

            $report.processes.Add([PSCustomObject]@{
                pid  = $procHandle.Id
                name = $procHandle.ProcessName
                path = $SamplePath
                action = "started"
            })
            Write-Step "OK" "Process tracked PID=$($procHandle.Id)"
        } catch {
            # ── Strategy 2: Fallback to scheduled task with INTERACTIVE SID ───
            Write-Step "Running" "ShellExecute failed ($_), falling back to schtasks INTERACTIVE"
            try {
                $taskId = "SentinelRun_" + [guid]::NewGuid().ToString("N").Substring(0,8)
                if ($fileType -eq "SCRIPT_BATCH") {
                    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$SamplePath`""
                } else {
                    $action = New-ScheduledTaskAction -Execute $SamplePath
                }
                $trigger   = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddSeconds(2))
                $settings  = New-ScheduledTaskSettingsSet `
                                 -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
                                 -DeleteExpiredTaskAfter (New-TimeSpan -Minutes 2) `
                                 -StartWhenAvailable
                $principal = New-ScheduledTaskPrincipal -GroupId "S-1-5-4" -RunLevel Highest
                Register-ScheduledTask -TaskName $taskId -Action $action -Trigger $trigger `
                    -Settings $settings -Principal $principal -Force -ErrorAction Stop | Out-Null
                Start-Sleep -Milliseconds 2500
                Start-ScheduledTask -TaskName $taskId -ErrorAction SilentlyContinue
                $report.executed = $true
                $report.highlights.Add("Sample executed (interactive via schtasks): $([System.IO.Path]::GetFileName($SamplePath))")
                Write-Step "OK" "Sample launched via interactive scheduled task [$taskId]"
                Start-Sleep -Seconds 3
                $procHandle = Get-Process -ErrorAction SilentlyContinue | Where-Object {
                    try { $_.Path -like "*$([System.IO.Path]::GetFileName($SamplePath))*" } catch { $false }
                } | Sort-Object StartTime -Descending | Select-Object -First 1
                if ($procHandle) {
                    $report.processes.Add([PSCustomObject]@{
                        pid  = $procHandle.Id
                        name = $procHandle.ProcessName
                        path = $SamplePath
                        action = "started"
                    })
                    Write-Step "OK" "Process tracked PID=$($procHandle.Id)"
                }
            } catch {
                $report.errors.Add("Failed to launch (both strategies): $_")
                Write-Step "Failed" "Launch failed: $_"
            }
        }

        # ── Optional: Launch AHK detonation helper (if AutoHotkey v2 is installed) ──
        # The AHK script provides smoother human-like mouse simulation, faster
        # UAC prompt handling, and native window control interaction. It runs in
        # parallel with the PowerShell UIA clicker below — belt and suspenders.
        $ahkProc = $null
        try {
            $ahkPaths = @(
                "C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe",
                "C:\Program Files\AutoHotkey\AutoHotkey64.exe",
                "C:\Program Files\AutoHotkey\v2\AutoHotkey.exe",
                "C:\Program Files\AutoHotkey\AutoHotkey.exe"
            )
            $ahkExe = $null
            foreach ($p in $ahkPaths) { if (Test-Path $p) { $ahkExe = $p; break } }
            if ($ahkExe) {
                # Look for detonate.ahk in the same directory as run.ps1, or in tools subdir
                $ahkScript = $null
                $candidates = @(
                    (Join-Path $PSScriptRoot "detonate.ahk"),
                    (Join-Path $PSScriptRoot "tools\detonate.ahk"),
                    "C:\Sandbox\tools\detonate.ahk"
                )
                foreach ($c in $candidates) { if (Test-Path $c) { $ahkScript = $c; break } }
                if ($ahkScript) {
                    $ahkArgs = "`"$ahkScript`" `"$SamplePath`" `"$outDir`" $MonitorSeconds"
                    $ahkProc = Start-Process -FilePath $ahkExe -ArgumentList $ahkArgs -PassThru -WindowStyle Normal -ErrorAction Stop
                    Write-Step "OK" "AHK detonation helper launched PID=$($ahkProc.Id)"
                } else {
                    Write-Step "Running" "AHK helper: detonate.ahk not found — skipping"
                }
            } else {
                Write-Step "Running" "AHK helper: AutoHotkey not found in guest — skipping"
            }
        } catch {
            Write-Step "Running" "AHK helper: failed to launch ($_ ) — continuing without"
        }

        # UIA button-clicker wrapped in try-catch — failure is non-critical and must not
        # propagate to the outer catch (which would abort the entire analysis run).
        $autoRS = $null; $autoPS = $null
        $autoHandle = $null
        try {
        $autoRS = [System.Management.Automation.Runspaces.RunspaceFactory]::CreateRunspace()
        $autoRS.ApartmentState = [System.Threading.ApartmentState]::STA
        $autoRS.ThreadOptions  = [System.Management.Automation.Runspaces.PSThreadOptions]::ReuseThread
        $autoRS.Open()
        $autoRS.SessionStateProxy.SetVariable('_SecsMon', $MonitorSeconds)
        $autoPS = [System.Management.Automation.PowerShell]::Create()
        $autoPS.Runspace = $autoRS
        [void]$autoPS.AddScript({
            Add-Type -AssemblyName UIAutomationClient -ErrorAction SilentlyContinue
            Add-Type -AssemblyName UIAutomationTypes  -ErrorAction SilentlyContinue
            # Expanded button-name list including UAC-specific labels, ampersand
            # accelerator forms ("&Yes"), and common installer/wizard buttons
            $accept = @('ok','next','yes','&yes','i agree','accept','install','finish',
                         'continue','allow','agree','run','apply','proceed','confirm',
                         'skip','close','open','got it','later','not now','remind me later',
                         'i accept','setup','extract','unzip','launch','start','execute')
            $deadline = [datetime]::Now.AddSeconds($_SecsMon + 15)
            while ([datetime]::Now -lt $deadline) {
                try {
                    $cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
                    $root = [System.Windows.Automation.AutomationElement]::RootElement
                    $btns = $root.FindAll([System.Windows.Automation.TreeScope]::Subtree, $cond)
                    foreach ($b in $btns) {
                        try {
                            $n = ($b.GetCurrentPropertyValue([System.Windows.Automation.AutomationElement]::NameProperty) -as [string]).Trim().ToLower()
                            if (-not $n) { continue }
                            $hit = $false
                            foreach ($a in $accept) { if ($n -like "*$a*") { $hit=$true; break } }
                            if (-not $hit) { continue }
                            # Use InvokePattern — works cross-session without mouse_event (which
                            # only affects the calling session's desktop). Fall back to legacy
                            # SetCursorPos/mouse_event only if InvokePattern is unsupported.
                            $invPat = $null
                            try {
                                $invPat = $b.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
                            } catch {}
                            if ($invPat) {
                                $invPat.Invoke()
                                Start-Sleep -Milliseconds 600
                            } else {
                                $r2 = $b.GetCurrentPropertyValue([System.Windows.Automation.AutomationElement]::BoundingRectangleProperty)
                                if (-not $r2 -or $r2.Width -le 0) { continue }
                                $cx=[int]($r2.Left+$r2.Width/2); $cy=[int]($r2.Top+$r2.Height/2)
                                Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class _MC2{[DllImport("user32.dll")]public static extern bool SetCursorPos(int x,int y);[DllImport("user32.dll")]public static extern void mouse_event(uint f,int x,int y,uint d,int e);}' -ErrorAction SilentlyContinue
                                [_MC2]::SetCursorPos($cx,$cy); Start-Sleep -Milliseconds 150
                                [_MC2]::mouse_event(0x02,0,0,0,0); Start-Sleep -Milliseconds 55; [_MC2]::mouse_event(0x04,0,0,0,0)
                                Start-Sleep -Milliseconds 500
                            }
                        } catch {}
                    }
                } catch {}
                [System.Threading.Thread]::Sleep(2000)
            }
        })
        $autoHandle = $autoPS.BeginInvoke()
        } catch {
            $report.errors.Add("UIA automation setup failed (non-critical): $_") | Out-Null
            Write-Step "Failed" "UIA automation unavailable: $_ — analysis continues without UI interaction"
            $autoHandle = $null
        }

        # Monitoring loop — track spawned processes, network connections, and
        # periodically jitter the mouse cursor to defeat sandbox-aware malware
        # that checks for human interaction patterns.
        $seenPids  = [System.Collections.Generic.HashSet[int]]::new()
        $seenConns = [System.Collections.Generic.HashSet[string]]::new()
        $jitterRng = [System.Random]::new()
        $jitterIdx = 0
        while ((New-TimeSpan -Start $monitorStart -End (Get-Date)).TotalSeconds -lt $MonitorSeconds) {
            Start-Sleep -Seconds 2

            # ── Periodic mouse jitter (every ~6 seconds) ──────────────────────
            $jitterIdx++
            if ($jitterIdx % 3 -eq 0) {
                try {
                    $pos = [System.Windows.Forms.Cursor]::Position
                    $dx  = $jitterRng.Next(-40, 41)
                    $dy  = $jitterRng.Next(-30, 31)
                    $nx  = [Math]::Max(10, [Math]::Min($sw - 10, $pos.X + $dx))
                    $ny  = [Math]::Max(10, [Math]::Min($sh - 10, $pos.Y + $dy))
                    Move-CursorSmooth $nx $ny 8
                } catch {}
            }

            Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Id -notin $baseProcs -and $seenPids.Add($_.Id) } | ForEach-Object {
                $report.spawned_processes.Add([PSCustomObject]@{ pid=$_.Id; name=$_.ProcessName; path=(try{$_.Path}catch{""}) })
                if ($_.ProcessName -match "(?i)cmd|powershell|wscript|cscript|regsvr32|rundll32|mshta|certutil|bitsadmin") {
                    $report.alerts.Add("Suspicious child process: $($_.ProcessName) (PID $($_.Id))")
                }
            }
            try {
                Get-NetTCPConnection -State Established -EA SilentlyContinue |
                    Where-Object { $_.OwningProcess -notin $baseProcs } |
                    ForEach-Object { $k="$($_.RemoteAddress):$($_.RemotePort)"; if($seenConns.Add($k)){$report.network_connections.Add($k)} }
            } catch {}
        }
        if ($null -ne $autoHandle) {
            try { $autoPS.Stop(); $autoPS.Dispose(); $autoRS.Close(); $autoRS.Dispose() } catch {}
        }
        # Stop AHK helper if it's still running
        if ($null -ne $ahkProc -and -not $ahkProc.HasExited) {
            try { $ahkProc.Kill(); Write-Step "OK" "AHK helper stopped" } catch {}
        }
        Write-Step "OK" "Monitoring complete"
    }

    # ── Scripts (PS1/VBS/JS/WSF) + MSI: inspect unless -AllowRun ─────────────
    "^(SCRIPT_PS|SCRIPT_VBS|SCRIPT_JS|SCRIPT_WSF|MSI)$" {
        if ($AllowRun) {
            $report.analysis_mode = "run"
            Write-Step "Running" "AllowRun set — executing $fileType: $SamplePath"
            try {
                # Use UseShellExecute so the process runs visibly in the current desktop session
                $psi = [System.Diagnostics.ProcessStartInfo]::new()
                $psi.UseShellExecute = $true
                $psi.WindowStyle     = [System.Diagnostics.ProcessWindowStyle]::Normal
                switch ($fileType) {
                    "SCRIPT_PS"  { $psi.FileName = "powershell.exe"; $psi.Arguments = "-ExecutionPolicy Bypass -File `"$SamplePath`"" }
                    "SCRIPT_VBS" { $psi.FileName = "wscript.exe";    $psi.Arguments = "`"$SamplePath`"" }
                    "SCRIPT_JS"  { $psi.FileName = "wscript.exe";    $psi.Arguments = "`"$SamplePath`"" }
                    "SCRIPT_WSF" { $psi.FileName = "wscript.exe";    $psi.Arguments = "`"$SamplePath`"" }
                    "MSI"        { $psi.FileName = "msiexec.exe";    $psi.Arguments = "/i `"$SamplePath`" /norestart" }
                }
                $procHandle = [System.Diagnostics.Process]::Start($psi)
                $report.executed = $true
                Write-Step "OK" "Running PID=$($procHandle.Id)"
                Start-Sleep -Seconds ([Math]::Min($MonitorSeconds, 60))
            } catch {
                $report.errors.Add("Failed to run: $_")
                Write-Step "Failed" "Run failed: $_"
            }
        } else {
            $report.analysis_mode = "inspect"
            Write-Step "OK" "$fileType detected — inspect-only mode (use -AllowRun to execute)"
            $report.highlights.Add("$fileType file — not executed (use -AllowRun to enable execution)")
        }
        # Always extract strings
        $strs = Get-PrintableStrings $SamplePath
        foreach ($s in $strs) { [void]$report.strings_found.Add($s) }
        $iocMap = Get-Iocs $report.strings_found
        $report.iocs = $iocMap
        Write-Step "OK" "Extracted $($report.strings_found.Count) strings, $($iocMap.urls.Count) URLs"
    }

    # ── ZIP: extract + inspect ─────────────────────────────────────────────────
    "^ZIP$" {
        $report.analysis_mode = "extract"
        $extractDir = "$outDir\extracted"
        New-Item -ItemType Directory -Force -Path $extractDir | Out-Null
        Write-Step "Running" "Expanding ZIP archive"
        try {
            Expand-Archive -Path $SamplePath -DestinationPath $extractDir -Force -ErrorAction Stop
            $all = Get-ChildItem -Path $extractDir -Recurse -File -ErrorAction SilentlyContinue
            foreach ($f in $all) {
                $report.extracted_files.Add($f.FullName)
                $fExt = $f.Extension.ToLower()
                if ($fExt -in @('.exe','.dll','.bat','.ps1','.vbs','.js','.msi','.scr','.com')) {
                    $report.alerts.Add("Executable inside archive: $($f.Name)")
                }
                # Strings from each extracted file
                $strs = Get-PrintableStrings $f.FullName -MaxCount 100
                foreach ($s in $strs) { [void]$report.strings_found.Add($s) }
            }
            Write-Step "OK" "Extracted $($report.extracted_files.Count) file(s)"
        } catch {
            $report.errors.Add("ZIP extraction failed: $_")
            Write-Step "Failed" "ZIP extraction failed: $_"
        }
        $iocMap = Get-Iocs $report.strings_found
        $report.iocs = $iocMap
    }

    # ── RAR / 7Z: use 7-Zip if available ──────────────────────────────────────
    "^(RAR|7Z)$" {
        $report.analysis_mode = "extract"
        $sevenz = $null
        foreach ($candidate in @("C:\Program Files\7-Zip\7z.exe","C:\Program Files (x86)\7-Zip\7z.exe")) {
            if (Test-Path $candidate) { $sevenz = $candidate; break }
        }
        if ($null -eq $sevenz) {
            $report.analysis_mode = "inspect"
            $report.errors.Add("7-Zip not installed; $fileType extraction skipped — inspecting header only.")
            $report.highlights.Add("$fileType archive: 7-Zip not installed in guest — install to enable extraction.")
            Write-Step "Failed" "7-Zip not found; skipping extraction"
        } else {
            $extractDir = "$outDir\extracted"
            New-Item -ItemType Directory -Force -Path $extractDir | Out-Null
            Write-Step "Running" "Extracting $fileType with 7-Zip"
            $r = & $sevenz x "$SamplePath" "-o$extractDir" -y 2>&1
            if ($LASTEXITCODE -eq 0) {
                $all = Get-ChildItem -Path $extractDir -Recurse -File -ErrorAction SilentlyContinue
                foreach ($f in $all) {
                    $report.extracted_files.Add($f.FullName)
                    if ($f.Extension.ToLower() -in @('.exe','.dll','.bat','.ps1','.vbs','.msi')) {
                        $report.alerts.Add("Executable inside $fileType archive: $($f.Name)")
                    }
                    $strs = Get-PrintableStrings $f.FullName -MaxCount 100
                    foreach ($s in $strs) { [void]$report.strings_found.Add($s) }
                }
                Write-Step "OK" "Extracted $($report.extracted_files.Count) file(s)"
            } else {
                $report.errors.Add("7-Zip failed (exit $LASTEXITCODE): $r")
                Write-Step "Failed" "7-Zip extraction failed"
            }
            $iocMap = Get-Iocs $report.strings_found
            $report.iocs = $iocMap
        }
    }

    # ── PDF: metadata + strings + URLs ────────────────────────────────────────
    "^PDF$" {
        $report.analysis_mode = "inspect"
        Write-Step "Running" "Inspecting PDF"
        $strs = Get-PrintableStrings $SamplePath
        foreach ($s in $strs) { [void]$report.strings_found.Add($s) }
        # PDF-specific: extract /URI values
        $pdfText = [System.Text.Encoding]::ASCII.GetString([System.IO.File]::ReadAllBytes($SamplePath))
        $uriRe = [regex]::new('/URI\s*\(([^)]+)\)', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        $uriRe.Matches($pdfText) | ForEach-Object { $report.urls_found.Add($_.Groups[1].Value) }
        # JS in PDF
        if ($pdfText -match '/JavaScript') { $report.alerts.Add("PDF contains embedded JavaScript") }
        if ($pdfText -match '/Launch')     { $report.alerts.Add("PDF contains /Launch action (may open external program)") }
        if ($pdfText -match '/AA\b')       { $report.alerts.Add("PDF contains automatic action (/AA)") }
        $iocMap = Get-Iocs $report.strings_found
        $report.iocs = $iocMap
        Write-Step "OK" "PDF inspection complete — $($report.strings_found.Count) strings, $($report.urls_found.Count) URIs"
    }

    # ── OLE2 (DOC/XLS/PPT/MSI via magic header) ───────────────────────────────
    "^OLE2$" {
        $report.analysis_mode = "inspect"
        Write-Step "Running" "Inspecting OLE2 compound document"
        $strs = Get-PrintableStrings $SamplePath
        foreach ($s in $strs) { [void]$report.strings_found.Add($s) }
        # Check for macros (rough heuristic)
        $raw = [System.IO.File]::ReadAllBytes($SamplePath)
        $macroSig = [byte[]]@(0x56, 0x42, 0x41, 0x20)  # "VBA "
        $hasMacro = $false
        for ($i = 0; $i -lt $raw.Length - 4; $i++) {
            if ($raw[$i] -eq $macroSig[0] -and $raw[$i+1] -eq $macroSig[1] -and $raw[$i+2] -eq $macroSig[2]) {
                $hasMacro = $true; break
            }
        }
        if ($hasMacro) { $report.alerts.Add("OLE2 document contains VBA macros") }
        $iocMap = Get-Iocs $report.strings_found
        $report.iocs = $iocMap
        Write-Step "OK" "OLE2 inspection complete — macros=$(if($hasMacro){'YES'}else{'no'})"
    }

    # ── OOXML (DOCX/XLSX/PPTX — these are ZIP internally) ────────────────────
    "^OOXML$" {
        $report.analysis_mode = "extract"
        $extractDir = "$outDir\ooxml_extracted"
        New-Item -ItemType Directory -Force -Path $extractDir | Out-Null
        Write-Step "Running" "Expanding OOXML (ZIP-based Office document)"
        try {
            Expand-Archive -Path $SamplePath -DestinationPath $extractDir -Force -EA Stop
            # Scan XML content for macros and external links
            $xmlFiles = Get-ChildItem -Path $extractDir -Recurse -Filter "*.xml" -ErrorAction SilentlyContinue
            foreach ($xf in $xmlFiles) {
                $xml = Get-Content $xf.FullName -Raw -ErrorAction SilentlyContinue
                if ($xml -match 'macroEnabled|vbaProject') { $report.alerts.Add("OOXML: macro-enabled content detected") }
                $urlRe2 = [regex]::new('https?://[^\s"''<>]{4,200}', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
                $urlRe2.Matches($xml) | ForEach-Object { $report.urls_found.Add($_.Value) }
            }
            # Check for vbaProject.bin
            $vba = Get-ChildItem -Path $extractDir -Recurse -Filter "vbaProject.bin" -ErrorAction SilentlyContinue
            if ($vba) { $report.alerts.Add("OOXML: vbaProject.bin found (embedded VBA macro)") }
        } catch {
            $report.errors.Add("OOXML extraction failed: $_")
            Write-Step "Failed" "OOXML expansion failed: $_"
        }
        $strs = Get-PrintableStrings $SamplePath
        foreach ($s in $strs) { [void]$report.strings_found.Add($s) }
        $iocMap = Get-Iocs $report.strings_found
        $report.iocs = $iocMap
        Write-Step "OK" "OOXML inspection complete"
    }

    # ── Default: strings + IOCs ───────────────────────────────────────────────
    default {
        $report.analysis_mode = "inspect"
        Write-Step "Running" "Unknown/generic file — strings + IOC extraction only"
        $strs = Get-PrintableStrings $SamplePath
        foreach ($s in $strs) { [void]$report.strings_found.Add($s) }
        $iocMap = Get-Iocs $report.strings_found
        $report.iocs = $iocMap
        Write-Step "OK" "Generic inspection complete"
    }
}

# ── Dropped files (all modes) ─────────────────────────────────────────────────
$scanDirs = @("C:\Windows\Temp", "C:\Sandbox\out", "C:\Users\Public", (Split-Path $SamplePath -Parent))
$scanDirs | Where-Object { $_ } | ForEach-Object {
    try {
        Get-ChildItem -Path $_ -Recurse -Force -ErrorAction SilentlyContinue |
            Where-Object { -not $_.PSIsContainer -and $_.CreationTime -gt $monitorStart } |
            Select-Object -First 100 |
            ForEach-Object { $report.files_created.Add($_.FullName) }
    } catch {}
}

# ── Registry persistence check (all modes) ────────────────────────────────────
@(
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run",
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce",
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce"
) | ForEach-Object {
    $regPath = $_
    try {
        $vals = Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue
        if ($vals) {
            $vals.PSObject.Properties | Where-Object { $_.Name -notmatch "^PS" } | ForEach-Object {
                $report.registry_modified.Add("$regPath\$($_.Name) = $($_.Value)")
                $report.alerts.Add("Persistence key written: $($_.Name)")
            }
        }
    } catch {}
}

# ── Kill processes if requested ───────────────────────────────────────────────
if ($KillOnFinish) {
    if ($procHandle) { try { $procHandle | Stop-Process -Force -EA SilentlyContinue } catch {} }
    $report.spawned_processes | ForEach-Object { try { Stop-Process -Id $_.pid -Force -EA SilentlyContinue } catch {} }
}

# ── Re-enable network ─────────────────────────────────────────────────────────
if ($DisableNetwork) {
    try { Get-NetAdapter | Enable-NetAdapter -Confirm:$false -ErrorAction SilentlyContinue } catch {}
}

# ── Finalise scores / highlights ─────────────────────────────────────────────
if ($report.alerts.Count -gt 0)           { $report.highlights.Add("$($report.alerts.Count) alert(s) raised during analysis") }
if ($report.network_connections.Count -gt 0) { $report.highlights.Add("$($report.network_connections.Count) outbound network connection(s)") }
if ($report.spawned_processes.Count -gt 0)   { $report.highlights.Add("$($report.spawned_processes.Count) child process(es) spawned") }
if ($report.registry_modified.Count -gt 0)  { $report.highlights.Add("Registry persistence key(s) added") }
if ($report.iocs.ips.Count -gt 0)            { $report.highlights.Add("$($report.iocs.ips.Count) external IP(s) found in file") }

$report.finished_at = (Get-Date -Format "o")
Write-Step "OK" "Analysis finished — mode=$($report.analysis_mode) alerts=$($report.alerts.Count)"

# ── Write report.json ────────────────────────────────────────────────────────
# This is a true infrastructure step — failure here exits 1.
try {
    $json = $report | ConvertTo-Json -Depth 12
    [System.IO.File]::WriteAllText("$outDir\report.json", $json, [System.Text.Encoding]::UTF8)
    Write-Step "OK" "report.json written"
} catch {
    $writeErr = "FATAL: Cannot write report.json — $_"
    Write-Host $writeErr
    Add-Content "$outDir\guest_error.txt" $writeErr -ErrorAction SilentlyContinue
    Write-Step "Failed" $writeErr
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1  # writing the report is critical infrastructure
}

} catch {
    # ── Fallback for any unhandled analysis exception ─────────────────────────
    # Write diagnostics and attempt a partial report, then EXIT 0 so the host
    # pipeline continues to collect whatever artifacts exist.  Only the three
    # explicit infra failures above (sample missing / outDir / report.json) exit 1.
    $fatalMsg = "SCRIPT_ERROR: $_`n$($_.ScriptStackTrace)"
    Write-Host $fatalMsg
    Add-Content "$outDir\guest_error.txt" $fatalMsg -ErrorAction SilentlyContinue
    try {
        $report.errors.Add($fatalMsg) | Out-Null
        $report.finished_at = (Get-Date -Format "o")
        $partialJson = $report | ConvertTo-Json -Depth 12
        [System.IO.File]::WriteAllText("$outDir\report.json", $partialJson, [System.Text.Encoding]::UTF8)
    } catch {}
    # exit 0 — host will score the partial report and surface errors[]
} finally {
    Stop-Transcript -ErrorAction SilentlyContinue
}
