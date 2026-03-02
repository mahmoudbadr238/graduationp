# Sentinel Sandbox – URL Detonation Monitor
# Copied from host at runtime; do not edit manually in the guest.
param(
    [Parameter(Mandatory=$true)][string]$Url,
    [int]$MonitorSeconds = 45,
    [switch]$DisableNetwork,
    [switch]$KillOnFinish
)

$ErrorActionPreference = "Continue"
$outDir = "C:\Sandbox\out"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$report = [ordered]@{
    url             = $Url
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
    http_requests       = [System.Collections.Generic.List[string]]::new()
    errors              = [System.Collections.Generic.List[string]]::new()
}

# ── Baseline ──────────────────────────────────────────────────────────────────
$baseProcs    = @(Get-Process | Select-Object -ExpandProperty Id)
$monitorStart = Get-Date

# ── Open URL ──────────────────────────────────────────────────────────────────
$proc = $null
$openCmd = @(
    { Start-Process "microsoft-edge:$Url" -PassThru -ErrorAction Stop },
    { Start-Process "msedge.exe" -ArgumentList $Url -PassThru -ErrorAction Stop },
    { Start-Process $Url -PassThru -ErrorAction Stop }
)
foreach ($cmd in $openCmd) {
    try { $proc = & $cmd; break } catch {}
}
if (-not $proc) { $report.errors.Add("Could not open URL in any browser.") }

# ── Monitor loop ──────────────────────────────────────────────────────────────
$seenPids  = [System.Collections.Generic.HashSet[int]]::new()
$seenConns = [System.Collections.Generic.HashSet[string]]::new()

while ((New-TimeSpan -Start $monitorStart -End (Get-Date)).TotalSeconds -lt $MonitorSeconds) {
    Start-Sleep -Seconds 2

    Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Id -notin $baseProcs -and $seenPids.Add($_.Id) } | ForEach-Object {
        $report.spawned_processes.Add([PSCustomObject]@{
            pid  = $_.Id
            name = $_.ProcessName
            path = try { $_.Path } catch { "" }
        })
    }

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
@($env:TEMP, $env:APPDATA, "C:\Users\Public") | ForEach-Object {
    try {
        Get-ChildItem -Path $_ -Recurse -Force -ErrorAction SilentlyContinue |
            Where-Object { -not $_.PSIsContainer -and $_.CreationTime -gt $monitorStart } |
            Select-Object -First 100 |
            ForEach-Object {
                $report.files_created.Add($_.FullName)
                $report.alerts.Add("File dropped: $($_.FullName)")
            }
    } catch {}
}

# ── Registry persistence ──────────────────────────────────────────────────────
@(
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run"
) | ForEach-Object {
    $regPath = $_
    try {
        $vals = Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue
        if ($vals) {
            $vals.PSObject.Properties | Where-Object { $_.Name -notmatch "^PS" } | ForEach-Object {
                $report.registry_modified.Add("$regPath\$($_.Name)")
                $report.alerts.Add("Persistence key: $($_.Name)")
            }
        }
    } catch {}
}

# ── Kill browser if requested ─────────────────────────────────────────────────
if ($KillOnFinish -and $proc) {
    try { $proc | Stop-Process -Force -ErrorAction SilentlyContinue } catch {}
}

# ── Write report ──────────────────────────────────────────────────────────────
$report.finished_at = (Get-Date -Format "o")
$json = $report | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText("$outDir\report.json", $json, [System.Text.Encoding]::UTF8)
