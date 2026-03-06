#Requires -Version 5.1
<#
.SYNOPSIS
    Sentinel VMware Sandbox Guest Agent — defensive malware analysis.

.DESCRIPTION
    Runs inside the guest VM (Windows 10/11). Collects before/after snapshots
    of processes, network connections, and filesystem changes, executes the
    suspicious sample, then writes structured artifacts to the job folder.

    Artifacts written to -JobDir:
      summary.json          — final structured report
      steps.jsonl           — per-step timeline (line-delimited JSON)
      processes_before.json — process list before execution
      processes_after.json  — process list after execution
      connections.txt       — netstat -ano output
      new_files.json        — new/modified files in monitored dirs
      errors.txt            — any errors encountered

.PARAMETER JobId
    Unique job identifier (set by host analyzer_dynamic.py).

.PARAMETER SamplePath
    Full path to the sample in the guest (e.g. C:\Sentinel\Jobs\<id>\sample.exe).

.PARAMETER JobDir
    Full path to the job directory in the guest.

.PARAMETER MonitorSeconds
    How many seconds to run the sample before forcibly terminating it.
    Default: 30.

.PARAMETER DisableNetwork
    If set, disable all network adapters before execution.

.NOTES
    SAFETY: This agent does NOT implement anti-VM tricks, evasion, or
    exfiltration. It is DEFENSIVE-only. Network is blocked by default
    (offline detonation). The caller (analyzer_dynamic.py) ensures the
    VM is reverted to a clean snapshot before AND after each run.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$JobId,
    [Parameter(Mandatory=$true)][string]$SamplePath,
    [Parameter(Mandatory=$true)][string]$JobDir,
    [int]$MonitorSeconds = 30,
    [switch]$DisableNetwork
)

Set-StrictMode -Off
$ErrorActionPreference = "Continue"

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

$Script:Steps = [System.Collections.Generic.List[string]]::new()
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

# ═══════════════════════════════════════════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════════════════════════════════════════

Write-Step "Running" "Agent started — Job: $JobId"

# Ensure job directory exists
try {
    New-Item -ItemType Directory -Force -Path $JobDir | Out-Null
    Write-Step "OK" "Job directory ready: $JobDir"
} catch {
    # If we cannot write, we still attempt to run
    Write-SandboxError "Could not ensure JobDir exists: $_"
}

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 10 — BASELINE SNAPSHOT
# ═══════════════════════════════════════════════════════════════════════════════

Write-Step "Running" "[10] Collecting pre-execution baseline"

# Process snapshot (before)
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

# Network connections (netstat) — capture once before
try {
    $netBefore = (netstat -ano 2>&1)
    $netBefore | Out-File -Encoding UTF8 -FilePath (Join-Path $JobDir "connections.txt")
    Write-Step "OK" "Network baseline captured"
} catch {
    Write-SandboxError "Network baseline failed: $_"
}

# File system baseline for monitored dirs
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
Write-Step "OK" "File system baseline collected for $($MonitoredDirs.Count) directories"

# ═══════════════════════════════════════════════════════════════════════════════
# Network disable (if requested)
# ═══════════════════════════════════════════════════════════════════════════════

if ($DisableNetwork) {
    try {
        Get-NetAdapter | Disable-NetAdapter -Confirm:$false -ErrorAction SilentlyContinue
        Write-Step "OK" "Network adapters disabled before detonation"
    } catch {
        Write-SandboxError "Could not disable network adapters: $_"
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 11 — EXECUTE SAMPLE
# ═══════════════════════════════════════════════════════════════════════════════

Write-Step "Running" "[11] Executing sample: $SamplePath"

$executed    = $false
$exitCode    = $null
$durationSec = 0.0
$proc        = $null
$startTime   = Get-Date

# Only execute EXE and SCR (script); other types get static-only
$ext = [IO.Path]::GetExtension($SamplePath).ToLower()
$runnable = $ext -in @('.exe', '.scr', '.com')

if (-not (Test-Path $SamplePath)) {
    Write-SandboxError "Sample not found in guest: $SamplePath"
} elseif (-not $runnable) {
    Write-Step "Running" "Non-executable extension '$ext' — skipping execution, static analysis only"
} else {
    try {
        $proc = Start-Process -FilePath $SamplePath -PassThru -ErrorAction Stop
        $executed = $true
        Write-Step "OK" "Sample started — PID $($proc.Id)"

        # Wait up to MonitorSeconds, then terminate
        $deadline = $startTime.AddSeconds($MonitorSeconds)
        while ((Get-Date) -lt $deadline) {
            if ($proc.HasExited) {
                $exitCode = $proc.ExitCode
                Write-Step "OK" "Sample exited naturally — exit code: $exitCode"
                break
            }
            Start-Sleep -Milliseconds 500
        }

        if (-not $proc.HasExited) {
            Write-Step "Running" "Monitor timeout reached — terminating sample"
            try {
                $proc.Kill()
                $proc.WaitForExit(5000) | Out-Null
                $exitCode = -1
                Write-Step "OK" "Sample terminated after timeout"
            } catch {
                Write-SandboxError "Could not terminate sample process: $_"
            }
        }

        $durationSec = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 2)
        Write-Step "OK" "Execution duration: ${durationSec}s"

    } catch {
        Write-SandboxError "Failed to start sample: $_"
    }
}

# Short dwell time to let child processes settle
Start-Sleep -Seconds 3

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 12 — POST-EXECUTION SNAPSHOT
# ═══════════════════════════════════════════════════════════════════════════════

Write-Step "Running" "[12] Collecting post-execution state"

# Process snapshot (after)
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
    Write-SandboxError "Post-execution process snapshot failed: $_"
}

# Diff: new processes
$pidsBefore = $procsBefore | ForEach-Object { $_.pid }
$newProcs = @($procsAfter | Where-Object { $_.pid -notin $pidsBefore })

# File system diff
$newFiles    = [System.Collections.Generic.List[object]]::new()
$modFiles    = [System.Collections.Generic.List[object]]::new()

foreach ($dir in $MonitoredDirs) {
    try {
        $currentFiles = Get-ChildItem -Path $dir -Recurse -Force -ErrorAction SilentlyContinue |
            Select-Object FullName, LastWriteTimeUtc, Length

        $baselineMap = @{}
        if ($fsBaseline.ContainsKey($dir)) {
            foreach ($f in $fsBaseline[$dir]) {
                if ($f.FullName) { $baselineMap[$f.FullName] = $f }
            }
        }

        foreach ($f in $currentFiles) {
            if (-not $f.FullName) { continue }
            if ($baselineMap.ContainsKey($f.FullName)) {
                $base = $baselineMap[$f.FullName]
                if ($f.LastWriteTimeUtc -gt $base.LastWriteTimeUtc) {
                    $modFiles.Add([PSCustomObject]@{
                        path   = $f.FullName
                        action = "modified"
                        size   = $f.Length
                    })
                }
            } else {
                $newFiles.Add([PSCustomObject]@{
                    path   = $f.FullName
                    action = "created"
                    size   = $f.Length
                })
            }
        }
    } catch {
        Write-SandboxError "File diff failed for ${dir}: $_"
    }
}

Save-Json -Path (Join-Path $JobDir "new_files.json") -Data @($newFiles + $modFiles)
Write-Step "OK" "File diff: $($newFiles.Count) new, $($modFiles.Count) modified"

# Alert heuristics
$alerts = [System.Collections.Generic.List[string]]::new()

foreach ($p in $newProcs) {
    $alerts.Add("New process spawned: $($p.name) [PID $($p.pid)]")
}
if ($newFiles.Count -gt 0) {
    $alerts.Add("$($newFiles.Count) new file(s) created in monitored directories")
}
if ($modFiles.Count -gt 0) {
    $alerts.Add("$($modFiles.Count) file(s) modified in monitored directories")
}
if ($exitCode -eq -1) {
    $alerts.Add("Sample was forcibly terminated after ${MonitorSeconds}s timeout")
}

Write-Step "OK" "Alert check: $($alerts.Count) alert(s)"

# ═══════════════════════════════════════════════════════════════════════════════
# WRITE SUMMARY.JSON
# ═══════════════════════════════════════════════════════════════════════════════

Write-Step "Running" "Writing summary.json"

$summary = [ordered]@{
    job_id                   = $JobId
    sample_name              = [IO.Path]::GetFileName($SamplePath)
    executed                 = $executed
    exit_code                = $exitCode
    duration_sec             = $durationSec
    started_at               = $startTime.ToUniversalTime().ToString("o")
    finished_at              = (Get-Date).ToUniversalTime().ToString("o")
    monitor_seconds          = $MonitorSeconds
    network_disabled         = [bool]$DisableNetwork
    new_processes            = @($newProcs)
    new_files                = @($newFiles)
    modified_files           = @($modFiles)
    new_connections          = @()        # placeholder for future netstat diff
    process_snapshot_before  = @($procsBefore | Select-Object -First 100)
    process_snapshot_after   = @($procsAfter  | Select-Object -First 100)
    alerts                   = @($alerts)
    errors                   = @($Script:Errors)
}

Save-Json -Path (Join-Path $JobDir "summary.json") -Data $summary

Write-Step "OK" "summary.json written — executed=$executed, alerts=$($alerts.Count), errors=$($Script:Errors.Count)"

# Save errors.txt for quick inspection
if ($Script:Errors.Count -gt 0) {
    $Script:Errors | Out-File -Encoding UTF8 -FilePath (Join-Path $JobDir "errors.txt")
}

Write-Step "OK" "Guest agent finished"

exit 0
