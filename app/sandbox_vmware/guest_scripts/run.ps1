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

# ── Human interaction simulation (background STA runspace, real mouse + UIA) ──
# Uses Win32 SetCursorPos/mouse_event for physical mouse clicks and
# System.Windows.Automation to locate accept/next buttons by control name.
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class MouseOps {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, int dx, int dy, uint data, int extra);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    public const uint LEFTDOWN = 0x0002;
    public const uint LEFTUP   = 0x0004;
    public static void Click(int x, int y) {
        SetCursorPos(x, y);
        System.Threading.Thread.Sleep(110);
        mouse_event(LEFTDOWN, 0, 0, 0, 0);
        System.Threading.Thread.Sleep(55);
        mouse_event(LEFTUP, 0, 0, 0, 0);
        System.Threading.Thread.Sleep(190);
    }
    public static void Drift(int x, int y) { SetCursorPos(x, y); System.Threading.Thread.Sleep(40); }
}
"@ -ErrorAction SilentlyContinue

$interactRS = [System.Management.Automation.Runspaces.RunspaceFactory]::CreateRunspace()
$interactRS.ApartmentState = [System.Threading.ApartmentState]::STA
$interactRS.ThreadOptions   = [System.Management.Automation.Runspaces.PSThreadOptions]::ReuseThread
$interactRS.Open()
$interactRS.SessionStateProxy.SetVariable('_TargetProc', $proc)
$interactRS.SessionStateProxy.SetVariable('_MonSecs',    $MonitorSeconds)

$interactPS = [System.Management.Automation.PowerShell]::Create()
$interactPS.Runspace = $interactRS
[void]$interactPS.AddScript({
    Add-Type -AssemblyName UIAutomationClient -ErrorAction SilentlyContinue
    Add-Type -AssemblyName UIAutomationTypes  -ErrorAction SilentlyContinue
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public class _Mouse {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, int x, int y, uint d, int e);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
    public const uint DOWN=0x02, UP=0x04;
    public static void Click(int x, int y) {
        SetCursorPos(x, y); System.Threading.Thread.Sleep(110);
        mouse_event(DOWN, 0, 0, 0, 0); System.Threading.Thread.Sleep(55);
        mouse_event(UP, 0, 0, 0, 0);   System.Threading.Thread.Sleep(190);
    }
    public static void Drift(int x, int y) { SetCursorPos(x, y); System.Threading.Thread.Sleep(40); }
}
"@ -ErrorAction SilentlyContinue

    $rng = New-Object System.Random
    $deadline = [datetime]::Now.AddSeconds($_MonSecs + 10)
    # Button names that indicate user acceptance / progression
    $acceptNames = @('ok','next','yes','i agree','accept','install','finish',
                     'continue','allow','agree','run','execute','apply',
                     'proceed','confirm','skip','close','open')

    Start-Sleep -Seconds 3

    while ([datetime]::Now -lt $deadline) {
        try {
            $buttonCondition = New-Object System.Windows.Automation.PropertyCondition(
                [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
                [System.Windows.Automation.ControlType]::Button
            )
            $root    = [System.Windows.Automation.AutomationElement]::RootElement
            $buttons = $root.FindAll([System.Windows.Automation.TreeScope]::Subtree, $buttonCondition)

            foreach ($btn in $buttons) {
                try {
                    $nameRaw = $btn.GetCurrentPropertyValue(
                        [System.Windows.Automation.AutomationElement]::NameProperty)
                    $btnName = ($nameRaw -as [string]).Trim().ToLower()
                    if (-not $btnName) { continue }
                    $isAccept = $false
                    foreach ($a in $acceptNames) {
                        if ($btnName -like "*$a*") { $isAccept = $true; break }
                    }
                    if (-not $isAccept) { continue }

                    $rect = $btn.GetCurrentPropertyValue(
                        [System.Windows.Automation.AutomationElement]::BoundingRectangleProperty)
                    if (-not $rect -or $rect.Width -le 0 -or $rect.Height -le 0) { continue }
                    if ($rect.Left -lt 0 -or $rect.Top -lt 0) { continue }

                    $cx = [int]($rect.Left + $rect.Width  / 2)
                    $cy = [int]($rect.Top  + $rect.Height / 2)

                    # Bring parent window to foreground
                    try {
                        $walker  = [System.Windows.Automation.TreeWalker]::ControlViewWalker
                        $hwndProp = [System.Windows.Automation.AutomationElement]::NativeWindowHandleProperty
                        $node = $walker.GetParent($btn)
                        while ($node -ne $null) {
                            $h = $node.GetCurrentPropertyValue($hwndProp)
                            if ($h -and $h -ne 0) {
                                [_Mouse]::ShowWindow([IntPtr]([int]$h), 9)
                                [_Mouse]::SetForegroundWindow([IntPtr]([int]$h))
                                break
                            }
                            $node = $walker.GetParent($node)
                        }
                    } catch {}

                    Start-Sleep -Milliseconds 200

                    # Smooth mouse glide to button (5 intermediate waypoints)
                    $startX = $rng.Next(300, 900); $startY = $rng.Next(200, 600)
                    for ($s = 1; $s -le 5; $s++) {
                        $ix = [int]($startX + ($cx - $startX) * $s / 5)
                        $iy = [int]($startY + ($cy - $startY) * $s / 5)
                        [_Mouse]::Drift($ix, $iy)
                    }
                    [_Mouse]::Click($cx, $cy)

                    # Also invoke via UIA pattern as a fallback
                    try {
                        $invoke = $btn.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
                        $invoke.Invoke()
                    } catch {}

                    Start-Sleep -Milliseconds 500
                } catch {}
            }
        } catch {}

        # Natural mouse drift between scan cycles
        [_Mouse]::Drift($rng.Next(200, 1400), $rng.Next(150, 800))
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
