# Sentinel Sandbox – File Detonation Monitor
# Copied from host at runtime; do not edit manually in the guest.
param(
    [Parameter(Mandatory=$true)][string]$SamplePath,
    [int]$MonitorSeconds = 30,
    [switch]$DisableNetwork,
    [switch]$KillOnFinish
)

$ErrorActionPreference = "Continue"
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

# ── Write report ──────────────────────────────────────────────────────────────
$report.finished_at = (Get-Date -Format "o")
$json = $report | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText("$outDir\report.json", $json, [System.Text.Encoding]::UTF8)
