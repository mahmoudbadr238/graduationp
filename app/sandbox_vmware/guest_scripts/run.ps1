# Sentinel Sandbox – File Detonation Monitor
# Copied from host at runtime; do not edit manually in the guest.
param(
    [Parameter(Mandatory=$true)][string]$SamplePath,
    [int]$MonitorSeconds = 30,
    [switch]$DisableNetwork,
    [switch]$KillOnFinish
)

$ErrorActionPreference = "Continue"

# ── Windows UI automation helper ─────────────────────────────────────────────
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class UIHelper {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@ -ErrorAction SilentlyContinue
$outDir = "C:\Sandbox\out"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$report = [ordered]@{
    sample          = $SamplePath
    started_at      = (Get-Date -Format "o")
    monitor_seconds = $MonitorSeconds
    alerts              = [System.Collections.Generic.List[string]]::new()
    processes           = [System.Collections.Generic.List[object]]::new()
    spawned_processes   = [System.Collections.Generic.List[object]]::new()
    files_created       = [System.Collections.Generic.List[string]]::new()
    dropped_files       = [System.Collections.Generic.List[string]]::new()
    registry_modified   = [System.Collections.Generic.List[string]]::new()
    network_connections = [System.Collections.Generic.List[string]]::new()
    dns_queries         = [System.Collections.Generic.List[string]]::new()
    errors              = [System.Collections.Generic.List[string]]::new()
}

# ── Baseline ─────────────────────────────────────────────────────────────────
$baseProcs  = @(Get-Process | Select-Object -ExpandProperty Id)
$monitorStart = Get-Date

# ── Disable guest network if requested ───────────────────────────────────────
if ($DisableNetwork) {
    try {
        Get-NetAdapter | Disable-NetAdapter -Confirm:$false -ErrorAction SilentlyContinue
        $report.alerts.Add("Network adapters disabled before detonation.")
    } catch { $report.errors.Add("Could not disable network: $_") }
}

# ── Launch sample ─────────────────────────────────────────────────────────────
$proc = $null
try {
    $proc = Start-Process -FilePath $SamplePath -PassThru -ErrorAction Stop
    $report.processes.Add([PSCustomObject]@{
        pid    = $proc.Id
        name   = $proc.ProcessName
        path   = $SamplePath
        action = "started"
    })
} catch {
    $report.errors.Add("Failed to start sample: $_")
}

# ── Human interaction simulation (background STA runspace) ───────────────────
# Simulates a user accepting wizard dialogs, UAC prompts, and installer screens
$interactRS = [System.Management.Automation.Runspaces.RunspaceFactory]::CreateRunspace()
$interactRS.ApartmentState = [System.Threading.ApartmentState]::STA
$interactRS.ThreadOptions   = [System.Management.Automation.Runspaces.PSThreadOptions]::ReuseThread
$interactRS.Open()
$interactRS.SessionStateProxy.SetVariable('_TargetProc', $proc)
$interactRS.SessionStateProxy.SetVariable('_MonSecs',    $MonitorSeconds)

$interactPS = [System.Management.Automation.PowerShell]::Create()
$interactPS.Runspace = $interactRS
[void]$interactPS.AddScript({
    Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public class _UIH {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
}
"@ -ErrorAction SilentlyContinue

    $deadline = [datetime]::Now.AddSeconds($_MonSecs + 5)
    $keys  = @("{ENTER}", " ", "{ENTER}", "y{ENTER}", "%y", "{TAB}{ENTER}", "{ENTER}")
    $ki    = 0
    $dialogPatterns = @(
        '*Install*','*Setup*','*Wizard*','*Finish*','*Complete*','*Next*',
        '*Accept*','*License*','*Agreement*','*Confirm*','*Warning*','*Alert*',
        '*User Account Control*','*Windows Security*','*Security Warning*','*Run*'
    )
    Start-Sleep -Seconds 2
    while ([datetime]::Now -lt $deadline) {
        try {
            # Focus and send key to target process
            if ($_TargetProc -and -not $_TargetProc.HasExited) {
                $hwnd = $_TargetProc.MainWindowHandle
                if ($hwnd -ne [IntPtr]::Zero) {
                    [_UIH]::ShowWindow($hwnd, 9); [_UIH]::SetForegroundWindow($hwnd)
                    Start-Sleep -Milliseconds 250
                    [System.Windows.Forms.SendKeys]::SendWait($keys[$ki % $keys.Count])
                }
            }
            $ki++
            # Accept any matching dialog window
            Get-Process -ErrorAction SilentlyContinue |
              Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero -and $_.MainWindowTitle -ne '' } |
              ForEach-Object {
                $t = $_.MainWindowTitle
                foreach ($pat in $dialogPatterns) {
                    if ($t -like $pat) {
                        [_UIH]::ShowWindow($_.MainWindowHandle, 9)
                        [_UIH]::SetForegroundWindow($_.MainWindowHandle)
                        Start-Sleep -Milliseconds 200
                        [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
                        break
                    }
                }
              }
        } catch {}
        Start-Sleep -Seconds 2
    }
})
$interactHandle = $interactPS.BeginInvoke()

# ── Monitor loop ──────────────────────────────────────────────────────────────
$seenPids = [System.Collections.Generic.HashSet[int]]::new()
$seenConns = [System.Collections.Generic.HashSet[string]]::new()

while ((New-TimeSpan -Start $monitorStart -End (Get-Date)).TotalSeconds -lt $MonitorSeconds) {
    Start-Sleep -Seconds 2

    # New processes
    Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Id -notin $baseProcs -and $seenPids.Add($_.Id) } | ForEach-Object {
        $entry = [PSCustomObject]@{ pid = $_.Id; name = $_.ProcessName; path = try { $_.Path } catch { "" } }
        $report.spawned_processes.Add($entry)
        if ($_.ProcessName -match "(?i)cmd|powershell|wscript|cscript|regsvr32|rundll32|mshta|certutil|bitsadmin") {
            $report.alerts.Add("Suspicious child process: $($_.ProcessName) (PID $($_.Id))")
        }
    }

    # Network connections
    try {
        Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue |
            Where-Object { $_.OwningProcess -notin $baseProcs } |
            ForEach-Object {
                $key = "$($_.RemoteAddress):$($_.RemotePort)"
                if ($seenConns.Add($key)) { $report.network_connections.Add($key) }
            }
    } catch {}
}

# ── Dropped files ─────────────────────────────────────────────────────────────
$scanDirs = @($env:TEMP, $env:APPDATA, "C:\Users\Public", (Split-Path $SamplePath -Parent))
$scanDirs | ForEach-Object {
    try {
        Get-ChildItem -Path $_ -Recurse -Force -ErrorAction SilentlyContinue |
            Where-Object { -not $_.PSIsContainer -and $_.CreationTime -gt $monitorStart } |
            Select-Object -First 100 |
            ForEach-Object { $report.files_created.Add($_.FullName) }
    } catch {}
}

# ── Registry persistence ──────────────────────────────────────────────────────
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
                $report.alerts.Add("Persistence registry key created: $($_.Name)")
            }
        }
    } catch {}
}

# ── Kill if requested ─────────────────────────────────────────────────────────
if ($KillOnFinish) {
    if ($proc) { try { $proc | Stop-Process -Force -ErrorAction SilentlyContinue } catch {} }
    $report.spawned_processes | ForEach-Object {
        try { Stop-Process -Id $_.pid -Force -ErrorAction SilentlyContinue } catch {}
    }
}

# ── Re-enable network ─────────────────────────────────────────────────────────
if ($DisableNetwork) {
    try { Get-NetAdapter | Enable-NetAdapter -Confirm:$false -ErrorAction SilentlyContinue } catch {}
}

# ── Stop interaction thread ──────────────────────────────────────────────────
try { $interactPS.Stop(); $interactPS.Dispose(); $interactRS.Close(); $interactRS.Dispose() } catch {}

# ── Write report (no BOM) ─────────────────────────────────────────────────────
$report.finished_at = (Get-Date -Format "o")
$json = $report | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText("$outDir\report.json", $json, [System.Text.Encoding]::UTF8)
