param(
    [Parameter(Mandatory = $true)]
    [string]$SamplePath,

    [Parameter(Mandatory = $true)]
    [string]$OutDir,

    [Parameter(Mandatory = $true)]
    [string]$StopFlagPath,

    [string]$DisableNetwork = "false"
)

$ErrorActionPreference = "Stop"

function Test-TrueLike {
    param([string]$Value)
    if ($null -eq $Value) { return $false }
    $v = $Value.Trim().ToLowerInvariant()
    return ($v -eq "true" -or $v -eq "$true" -or $v -eq "1" -or $v -eq "yes")
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [object]$Object
    )

    $json = $Object | ConvertTo-Json -Depth 8
    Set-Content -Path $Path -Value $json -Encoding UTF8
}

function Get-ProcessSnapshot {
    $map = @{}
    try {
        Get-Process -ErrorAction SilentlyContinue | ForEach-Object {
            $map[[int]$_.Id] = [string]$_.ProcessName
        }
    } catch {
    }
    return $map
}

function Get-FileSnapshot {
    param([string[]]$Roots)

    $state = @{}
    foreach ($root in $Roots) {
        if (-not (Test-Path -LiteralPath $root)) { continue }
        try {
            Get-ChildItem -LiteralPath $root -File -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
                $key = [string]$_.FullName
                $state[$key] = "{0}|{1}" -f [string]$_.Length, [string]$_.LastWriteTimeUtc.Ticks
            }
        } catch {
        }
    }
    return $state
}

function Compare-FileSnapshots {
    param(
        [hashtable]$Before,
        [hashtable]$After
    )

    $created = New-Object System.Collections.Generic.List[string]
    $modified = New-Object System.Collections.Generic.List[string]
    $deleted = New-Object System.Collections.Generic.List[string]

    foreach ($k in $After.Keys) {
        if (-not $Before.ContainsKey($k)) {
            $created.Add($k)
        } elseif ($Before[$k] -ne $After[$k]) {
            $modified.Add($k)
        }
    }

    foreach ($k in $Before.Keys) {
        if (-not $After.ContainsKey($k)) {
            $deleted.Add($k)
        }
    }

    return @{
        created = $created
        modified = $modified
        deleted = $deleted
    }
}

function Get-RunKeySnapshot {
    $snapshot = @{}
    $paths = @(
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce",
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run",
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce"
    )

    foreach ($path in $paths) {
        try {
            $item = Get-ItemProperty -Path $path -ErrorAction Stop
            foreach ($prop in $item.PSObject.Properties) {
                if ($prop.Name -in @("PSPath", "PSParentPath", "PSChildName", "PSDrive", "PSProvider")) {
                    continue
                }
                $snapshot["$path::$($prop.Name)"] = [string]$prop.Value
            }
        } catch {
        }
    }

    return $snapshot
}

function Compare-RunKeys {
    param(
        [hashtable]$Before,
        [hashtable]$After
    )

    $changes = New-Object System.Collections.Generic.List[string]

    foreach ($k in $After.Keys) {
        if (-not $Before.ContainsKey($k)) {
            $changes.Add("added $k")
        } elseif ($Before[$k] -ne $After[$k]) {
            $changes.Add("modified $k")
        }
    }

    foreach ($k in $Before.Keys) {
        if (-not $After.ContainsKey($k)) {
            $changes.Add("deleted $k")
        }
    }

    return $changes
}

function Get-NetworkSnapshot {
    $set = New-Object System.Collections.Generic.HashSet[string]
    try {
        Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue | ForEach-Object {
            $remote = "{0}:{1}" -f [string]$_.RemoteAddress, [string]$_.RemotePort
            if ($remote -notmatch "^(0\.0\.0\.0|127\.0\.0\.1|::|\[::1\])") {
                [void]$set.Add($remote)
            }
        }
    } catch {
    }
    return $set
}

$startedAt = Get-Date
$errors = New-Object System.Collections.Generic.List[string]
$alerts = New-Object System.Collections.Generic.List[string]
$highlights = New-Object System.Collections.Generic.List[string]

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$telemetryPath = Join-Path $OutDir "telemetry.json"
$reportPath = Join-Path $OutDir "report.json"
$doneFlagPath = Join-Path $OutDir "done.flag"

$watchRoots = @(
    "C:\Users\Public",
    $env:TEMP,
    "C:\ProgramData"
)

$disableNetworkRequested = Test-TrueLike $DisableNetwork
if ($disableNetworkRequested) {
    $alerts.Add("Network isolation requested for this interactive session.") | Out-Null
}

$baselineProc = Get-ProcessSnapshot
$baselineFiles = Get-FileSnapshot -Roots $watchRoots
$baselineRunKeys = Get-RunKeySnapshot
$baselineNetwork = Get-NetworkSnapshot

$newProcessIdSet = New-Object System.Collections.Generic.HashSet[int]
$newProcessRows = New-Object System.Collections.Generic.List[object]
$createdSet = New-Object System.Collections.Generic.HashSet[string]
$modifiedSet = New-Object System.Collections.Generic.HashSet[string]
$deletedSet = New-Object System.Collections.Generic.HashSet[string]
$registrySet = New-Object System.Collections.Generic.HashSet[string]
$networkSet = New-Object System.Collections.Generic.HashSet[string]

$executed = $false
try {
    if (Test-Path -LiteralPath $SamplePath) {
        $proc = Start-Process -FilePath $SamplePath -PassThru -ErrorAction Stop
        $executed = $true
        if ($null -ne $proc -and $proc.Id -gt 0) {
            [void]$newProcessIdSet.Add([int]$proc.Id)
            $newProcessRows.Add(@{ "name" = $proc.ProcessName; "process_id" = [int]$proc.Id }) | Out-Null
        }
        $highlights.Add("Sample started for manual interaction inside guest.") | Out-Null
    } else {
        $errors.Add("Sample path not found: $SamplePath") | Out-Null
    }
} catch {
    $errors.Add("Failed to start sample: $($_.Exception.Message)") | Out-Null
}

while (-not (Test-Path -LiteralPath $StopFlagPath)) {
    Start-Sleep -Seconds 2

    $elapsed = [int]((Get-Date) - $startedAt).TotalSeconds

    $procNow = Get-ProcessSnapshot
    foreach ($processKey in $procNow.Keys) {
        if (-not $baselineProc.ContainsKey($processKey) -and -not $newProcessIdSet.Contains([int]$processKey)) {
            [void]$newProcessIdSet.Add([int]$processKey)
            $newProcessRows.Add(@{ "name" = [string]$procNow[$processKey]; "process_id" = [int]$processKey }) | Out-Null
        }
    }

    $fileNow = Get-FileSnapshot -Roots $watchRoots
    $fileDiff = Compare-FileSnapshots -Before $baselineFiles -After $fileNow
    foreach ($p in $fileDiff.created)  { [void]$createdSet.Add([string]$p) }
    foreach ($p in $fileDiff.modified) { [void]$modifiedSet.Add([string]$p) }
    foreach ($p in $fileDiff.deleted)  { [void]$deletedSet.Add([string]$p) }

    $runNow = Get-RunKeySnapshot
    $runDiff = Compare-RunKeys -Before $baselineRunKeys -After $runNow
    foreach ($r in $runDiff) { [void]$registrySet.Add([string]$r) }

    $netNow = Get-NetworkSnapshot
    foreach ($n in $netNow) {
        if (-not $baselineNetwork.Contains($n)) {
            [void]$networkSet.Add([string]$n)
        }
    }

    $telemetry = [ordered]@{
        elapsed_seconds = $elapsed
        new_processes = $newProcessIdSet.Count
        files_created = $createdSet.Count
        files_modified = $modifiedSet.Count
        files_deleted = $deletedSet.Count
        registry_changes = $registrySet.Count
        network_connections = $networkSet.Count
        persistence_events = ($registrySet | Where-Object { $_ -match "\\Run(Once)?::" }).Count
    }

    try {
        Write-JsonFile -Path $telemetryPath -Object $telemetry
    } catch {
    }
}

$elapsedFinal = [int]((Get-Date) - $startedAt).TotalSeconds

if ($registrySet.Count -gt 0) {
    $alerts.Add("Registry autorun activity detected.") | Out-Null
}
if ($networkSet.Count -gt 0) {
    $alerts.Add("Outbound network activity observed.") | Out-Null
}
if ($createdSet.Count -gt 30) {
    $alerts.Add("High volume of file creation observed.") | Out-Null
}

$highlights.Add("Session ended by analyst via Stop Analysis.") | Out-Null
$highlights.Add("Collected passive telemetry without automated UI control.") | Out-Null

$finalTelemetry = [ordered]@{
    elapsed_seconds = $elapsedFinal
    new_processes = $newProcessIdSet.Count
    files_created = $createdSet.Count
    files_modified = $modifiedSet.Count
    files_deleted = $deletedSet.Count
    registry_changes = $registrySet.Count
    network_connections = $networkSet.Count
    persistence_events = ($registrySet | Where-Object { $_ -match "\\Run(Once)?::" }).Count
}

$report = [ordered]@{
    analysis_mode = "interactive_session"
    mode = "interactive_session"
    executed = $executed
    sample_path = $SamplePath
    started_at = $startedAt.ToString("o")
    finished_at = (Get-Date).ToString("o")
    elapsed_seconds = $elapsedFinal
    telemetry = $finalTelemetry
    spawned_processes = $newProcessRows
    files_created = @($createdSet)
    files_modified = @($modifiedSet)
    files_deleted = @($deletedSet)
    registry_modified = @($registrySet)
    network_connections = @($networkSet)
    persistence = @($registrySet | Where-Object { $_ -match "\\Run(Once)?::" })
    alerts = @($alerts)
    highlights = @($highlights)
    errors = @($errors)
}

Write-JsonFile -Path $telemetryPath -Object $finalTelemetry
Write-JsonFile -Path $reportPath -Object $report
New-Item -ItemType File -Path $doneFlagPath -Force | Out-Null
