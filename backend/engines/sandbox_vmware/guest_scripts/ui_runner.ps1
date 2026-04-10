# Sentinel – Unified Guest UI Runner v2
# ─────────────────────────────────────────────────────────────────────────────
# Entry-point script deployed by the host into the guest VM.
# Runs via vmrun runProgramInGuest (Session 0).
#
# Responsibilities:
#   A) PREREQUISITE CHECKS  (always run)
#      1. query user  → verify ACTIVE session for the configured user
#      2. tasklist    → verify explorer.exe is running; start it if not
#      3. Read PromptOnSecureDesktop (UAC secure desktop) → write to out
#
#   B) INSPECT mode  (-Mode inspect)
#      - Do NOT execute the sample
#      - Open file properties / signature info, write metadata JSON, exit 0
#
#   C) EXECUTE mode  (-Mode execute)
#      - Delegate visible automation to the Session-1 runner
#        (ui_runner\launch_interactive.ps1  →  ui_runner\ui_runner.ps1)
#      - Capture desktop frames every 1s during MonitorSeconds
#      - Write behavior.json + ui_transcript.txt
#
# Exit codes:
#   0  – success or advisory failure (sample missing, UAC warning, etc.)
#   1  – infrastructure failure (cannot write OutDir, cannot write behavior.json)
# ─────────────────────────────────────────────────────────────────────────────
param(
    [Parameter(Mandatory=$true)] [string]$SamplePath,
    [string]$OutDir          = "C:\Sandbox\out",
    [string]$Mode            = "inspect",          # "inspect" | "execute"
    [int]   $MonitorSeconds  = 30,
    [string]$GuestUser       = "",
    [string]$GuestPass       = "",
    [string]$JobId           = "unknown"
)

Set-StrictMode -Off
$ErrorActionPreference = "Continue"

# ── Ensure OutDir exists ──────────────────────────────────────────────────────
try {
    New-Item -ItemType Directory -Force -Path $OutDir -ErrorAction Stop | Out-Null
} catch {
    Write-Host "FATAL: Cannot create OutDir $OutDir : $_"
    exit 1
}

# ── Transcript ────────────────────────────────────────────────────────────────
$transcriptFile = "$OutDir\ui_transcript.txt"
try {
    Start-Transcript -Path $transcriptFile -Append -Force -ErrorAction SilentlyContinue | Out-Null
} catch {}

$runStart = Get-Date
Write-Host "ui_runner.ps1 starting  mode=$Mode  sample=$SamplePath  job=$JobId"
Write-Host "OutDir=$OutDir  MonitorSeconds=$MonitorSeconds  User=$GuestUser"

# ── Assemblies (best-effort) ──────────────────────────────────────────────────
Add-Type -AssemblyName System.Drawing          -ErrorAction SilentlyContinue
Add-Type -AssemblyName System.Windows.Forms    -ErrorAction SilentlyContinue

# ── Result object ─────────────────────────────────────────────────────────────
$result = [ordered]@{
    job_id                  = $JobId
    mode                    = $Mode
    sample_path             = $SamplePath
    started_at              = ($runStart | Get-Date -Format "o")
    # Prerequisite section
    prereq_session_active   = $false
    prereq_session_info     = ""
    prereq_explorer_running = $false
    prereq_explorer_started = $false
    prereq_uac_secure_desktop = $null    # null=unknown, 0=disabled, 1=enabled (blocker)
    # Inspect / Execute section
    inspect_signature       = ""
    inspect_metadata        = @{}
    sample_launched         = $false
    sample_pid              = 0
    window_titles_seen      = [System.Collections.Generic.List[string]]::new()
    frames_count            = 0
    frames_dir              = ""
    buttons_clicked         = [System.Collections.Generic.List[string]]::new()
    automation_visible      = $false
    notes                   = [System.Collections.Generic.List[string]]::new()
    warnings                = [System.Collections.Generic.List[string]]::new()
    errors                  = [System.Collections.Generic.List[string]]::new()
    exit_code               = 0
    finished_at             = ""
    runtime_seconds         = 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# A) PREREQUISITE CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

Write-Host ""
Write-Host "━━━━  A) PREREQUISITE CHECKS  ━━━━"

# ── A1: query user → active session ──────────────────────────────────────────
Write-Host "[A1] Checking for active desktop session (query user)…"
try {
    $quResult  = query user 2>&1
    $quText    = ($quResult | Out-String).Trim()
    $result.prereq_session_info = $quText
    Write-Host "  query user output:`n$quText"

    $activeLines = $quText -split "`n" | Where-Object { $_ -match "Active" }
    if ($activeLines.Count -gt 0) {
        $result.prereq_session_active = $true
        Write-Host "[A1] ✔ Active session found: $($activeLines[0].Trim())"
    } else {
        $result.prereq_session_active = $false
        $msg = "No ACTIVE desktop session found for any user. Enable auto-login in the guest VM (netplwiz) so it boots directly to the desktop. Visible GUI automation requires an active logged-in session."
        $result.errors.Add("PREREQ FAILED: $msg")
        Write-Host "[A1] ✘ $msg"
        $result.notes.Add("GUI automation will be skipped — no interactive desktop.")
    }
} catch {
    $result.warnings.Add("Could not run 'query user': $_")
    Write-Host "[A1] WARNING: Could not determine session state: $_"
}

# ── A2: explorer.exe check ────────────────────────────────────────────────────
Write-Host "[A2] Checking for explorer.exe (desktop shell)…"
try {
    $explorerList = (cmd /c 'tasklist /FI "IMAGENAME eq explorer.exe" /NH' 2>&1) | Out-String
    if ($explorerList -match "explorer.exe") {
        $result.prereq_explorer_running = $true
        Write-Host "[A2] ✔ explorer.exe is running"
    } else {
        $result.prereq_explorer_running = $false
        Write-Host "[A2] explorer.exe not found — attempting to start desktop shell…"
        try {
            Start-Process explorer.exe -ErrorAction Stop
            Start-Sleep -Seconds 3
            $result.prereq_explorer_started = $true
            Write-Host "[A2] ✔ explorer.exe started"
        } catch {
            $result.warnings.Add("Could not start explorer.exe: $_")
            Write-Host "[A2] WARNING: Could not start explorer.exe: $_"
        }
    }
} catch {
    $result.warnings.Add("explorer.exe check failed: $_")
    Write-Host "[A2] WARNING: explorer.exe check error: $_"
}

# ── A3: UAC secure desktop check ─────────────────────────────────────────────
Write-Host "[A3] Checking UAC PromptOnSecureDesktop…"
try {
    $regPath  = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
    $regValue = (Get-ItemProperty -Path $regPath -Name "PromptOnSecureDesktop" -ErrorAction Stop).PromptOnSecureDesktop
    $result.prereq_uac_secure_desktop = $regValue
    if ($regValue -eq 1) {
        $warnMsg = "UAC secure desktop is ENABLED (PromptOnSecureDesktop=1). UAC prompts will appear on a secure desktop that automation cannot interact with. To allow visible automation of UAC prompts inside the sandbox VM, run: reg add `"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System`" /v PromptOnSecureDesktop /t REG_DWORD /d 0 /f"
        $result.warnings.Add($warnMsg)
        Write-Host "[A3] ⚠ $warnMsg"
    } else {
        Write-Host "[A3] ✔ PromptOnSecureDesktop=$regValue (secure desktop disabled — UAC prompts are automatable)"
    }
} catch {
    $result.prereq_uac_secure_desktop = $null
    $result.warnings.Add("Could not read PromptOnSecureDesktop: $_")
    Write-Host "[A3] WARNING: Could not read UAC registry key: $_"
}

# ── Write prereq_results.json ─────────────────────────────────────────────────
$prereqJson = [ordered]@{
    session_active        = $result.prereq_session_active
    session_info          = $result.prereq_session_info
    explorer_running      = $result.prereq_explorer_running
    explorer_started      = $result.prereq_explorer_started
    uac_secure_desktop    = $result.prereq_uac_secure_desktop
    warnings              = @($result.warnings)
    errors                = @($result.errors)
}
try {
    $prereqJson | ConvertTo-Json -Depth 3 | Out-File "$OutDir\prereq_results.json" -Encoding utf8 -Force
    Write-Host "[A] prereq_results.json written"
} catch {
    Write-Host "[A] WARNING: Could not write prereq_results.json: $_"
}

# ═══════════════════════════════════════════════════════════════════════════════
# B / C) MODE DISPATCH
# ═══════════════════════════════════════════════════════════════════════════════

if ($Mode -eq "inspect") {
    # ─────────────────────────────────────────────────────────────────────────
    # B) INSPECT MODE — No execution; gather metadata only
    # ─────────────────────────────────────────────────────────────────────────
    Write-Host ""
    Write-Host "━━━━  B) INSPECT MODE  ━━━━"

    if (-not (Test-Path $SamplePath)) {
        $result.errors.Add("Inspect: sample file not found: $SamplePath")
        Write-Host "[B] Sample not found: $SamplePath"
    } else {
        # File metadata
        try {
            $fi = Get-Item $SamplePath -ErrorAction Stop
            $result.inspect_metadata = [ordered]@{
                name         = $fi.Name
                size_bytes   = $fi.Length
                created_utc  = ($fi.CreationTimeUtc | Get-Date -Format "o")
                modified_utc = ($fi.LastWriteTimeUtc | Get-Date -Format "o")
                extension    = $fi.Extension
                attributes   = $fi.Attributes.ToString()
            }
            Write-Host "[B] File metadata: $($fi.Name) ($($fi.Length) bytes)"
        } catch {
            $result.warnings.Add("Could not read file metadata: $_")
        }

        # Authenticode signature
        try {
            $sig = Get-AuthenticodeSignature $SamplePath -ErrorAction Stop
            $signerSubject    = if ($sig.SignerCertificate) { $sig.SignerCertificate.Subject }    else { "" }
            $signerThumbprint = if ($sig.SignerCertificate) { $sig.SignerCertificate.Thumbprint } else { "" }
            $result.inspect_signature = "$($sig.Status) — $signerSubject"
            Write-Host "[B] Signature: $($result.inspect_signature)"
            $result.inspect_metadata.signature_status  = $sig.Status.ToString()
            $result.inspect_metadata.signer_subject    = $signerSubject
            $result.inspect_metadata.signer_thumbprint = $signerThumbprint
        } catch {
            $result.inspect_signature = "unavailable: $_"
            Write-Host "[B] Signature check failed: $_"
        }

        # First 20 strings (rudimentary)
        try {
            $bytes   = [System.IO.File]::ReadAllBytes($SamplePath)
            $ascii   = [System.Text.Encoding]::ASCII.GetString($bytes)
            $stringMatches = ([regex]"[\x20-\x7E]{6,}").Matches($ascii) | Select-Object -First 20 | ForEach-Object { $_.Value }
            $result.inspect_metadata.top_strings = @($stringMatches)
        } catch {}

        $result.notes.Add("Inspect mode: sample was NOT executed.")
        Write-Host "[B] Inspect complete. Sample was not executed."
    }

} elseif ($Mode -eq "execute") {
    # ─────────────────────────────────────────────────────────────────────────
    # C) EXECUTE MODE — Visible desktop automation
    # ─────────────────────────────────────────────────────────────────────────
    Write-Host ""
    Write-Host "━━━━  C) EXECUTE MODE  ━━━━"

    if (-not $result.prereq_session_active) {
        $result.errors.Add("Cannot execute: guest not logged in interactively. Enable auto-login and revert VM.")
        Write-Host "[C] EARLY EXIT: guest not logged in. Skipping execution."
    } elseif (-not (Test-Path $SamplePath)) {
        $result.errors.Add("Execute: sample file not found: $SamplePath")
        Write-Host "[C] Sample not found: $SamplePath"
    } else {
        # ── Determine path to launch_interactive.ps1 ─────────────────────────
        $scriptDir        = Split-Path -Parent $MyInvocation.MyCommand.Path
        $launchInteractive = "$scriptDir\ui_runner\launch_interactive.ps1"
        $fallbackLaunch   = "C:\Sandbox\jobs\$JobId\tools\ui_runner\launch_interactive.ps1"

        # Prefer sibling ui_runner\ dir; fall back to per-job tools dir
        if (-not (Test-Path $launchInteractive)) {
            $launchInteractive = $fallbackLaunch
        }

        if (Test-Path $launchInteractive) {
            Write-Host "[C] Using launch_interactive.ps1: $launchInteractive"
            # Delegate to the interactive session launcher
            $launchArgs = @(
                "-ExecutionPolicy", "Bypass",
                "-File", $launchInteractive,
                "-GuestUser",      $GuestUser,
                "-GuestPass",      $GuestPass,
                "-SamplePath",     $SamplePath,
                "-JobId",          $JobId,
                "-MonitorSeconds", $MonitorSeconds
            )
            try {
                Write-Host "[C] Launching interactive runner…"
                $launchProc = Start-Process powershell.exe -ArgumentList $launchArgs -PassThru -Wait -ErrorAction Stop
                Write-Host "[C] launch_interactive exit code: $($launchProc.ExitCode)"
                $result.notes.Add("launch_interactive.ps1 exit code: $($launchProc.ExitCode)")
            } catch {
                $result.errors.Add("launch_interactive.ps1 failed: $_")
                Write-Host "[C] ERROR: launch_interactive failed: $_"
            }
        } else {
            # Fallback: direct execution with inline frame capture
            Write-Host "[C] launch_interactive.ps1 not found – using direct execution fallback"
            $result.notes.Add("Direct execution fallback (launch_interactive.ps1 not available)")

            $framesDir = "$OutDir\frames"
            New-Item -ItemType Directory -Force -Path $framesDir -ErrorAction SilentlyContinue | Out-Null
            $result.frames_dir = $framesDir

            # Frame capture helper
            $frameIdx = 0
            function CaptureFrame {
                try {
                    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
                    $bmp    = [System.Drawing.Bitmap]::new($bounds.Width, $bounds.Height)
                    $gfx    = [System.Drawing.Graphics]::FromImage($bmp)
                    $gfx.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
                    $idx    = $script:frameIdx.ToString("D4"); $script:frameIdx++
                    $path   = "$framesDir\frame_$idx.png"
                    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
                    $gfx.Dispose(); $bmp.Dispose()
                    return $path
                } catch { return "" }
            }

            # Launch
            try {
                $ext = [System.IO.Path]::GetExtension($SamplePath).ToLower()
                $psi = [System.Diagnostics.ProcessStartInfo]::new()
                $psi.UseShellExecute = $true
                $psi.WindowStyle     = [System.Diagnostics.ProcessWindowStyle]::Normal
                if ($ext -eq ".msi")                    { $psi.FileName = "msiexec.exe"; $psi.Arguments = "/i `"$SamplePath`"" }
                elseif ($ext -in @(".bat",".cmd"))      { $psi.FileName = "cmd.exe";     $psi.Arguments = "/c `"$SamplePath`"" }
                elseif ($ext -in @(".ps1"))             { $psi.FileName = "powershell.exe"; $psi.Arguments = "-ExecutionPolicy Bypass -File `"$SamplePath`"" }
                elseif ($ext -in @(".vbs",".js"))       { $psi.FileName = "wscript.exe"; $psi.Arguments = "`"$SamplePath`"" }
                else                                    { $psi.FileName = $SamplePath }
                $proc = [System.Diagnostics.Process]::Start($psi)
                $result.sample_launched = $true
                $result.sample_pid      = $proc.Id
                Write-Host "[C] Launched PID=$($proc.Id)"
            } catch {
                $result.errors.Add("Launch failed: $_")
                Write-Host "[C] Launch error: $_"
            }

            # Capture loop
            $deadline   = (Get-Date).AddSeconds($MonitorSeconds)
            $lastCap    = [DateTime]::MinValue
            while ((Get-Date) -lt $deadline) {
                if (((Get-Date) - $lastCap).TotalSeconds -ge 1.0) {
                    $f = CaptureFrame
                    if ($f) { $result.frames_count++ }
                    $lastCap = Get-Date
                }
                # Collect window titles (best-effort)
                try {
                    if ($null -ne $proc -and -not $proc.HasExited) {
                        $proc.Refresh()
                        $t = $proc.MainWindowTitle
                        if ($t -and $t -ne "" -and -not $result.window_titles_seen.Contains($t)) {
                            $result.window_titles_seen.Add($t)
                        }
                    }
                } catch {}
                Start-Sleep -Milliseconds 300
            }
        }

        # ── Collect frames written by ui_runner.ps1 (session 1) ───────────────
        $guestFramesDir = "$OutDir\frames"
        if (Test-Path $guestFramesDir) {
            $fc = (Get-ChildItem -Path $guestFramesDir -Filter "frame_*.png" -ErrorAction SilentlyContinue | Measure-Object).Count
            $result.frames_count  = $fc
            $result.frames_dir    = $guestFramesDir
            $result.automation_visible = ($fc -gt 3)
            Write-Host "[C] Frames collected: $fc (automation_visible=$($result.automation_visible))"
        }
    }
} else {
    $result.errors.Add("Unknown mode: $Mode. Expected 'inspect' or 'execute'.")
    Write-Host "ERROR: Unknown mode '$Mode'"
}

# ═══════════════════════════════════════════════════════════════════════════════
# FINALIZE
# ═══════════════════════════════════════════════════════════════════════════════

$result.finished_at     = (Get-Date -Format "o")
$result.runtime_seconds = [math]::Round(((Get-Date) - $runStart).TotalSeconds, 1)
Write-Host ""
Write-Host "ui_runner.ps1 finished  mode=$Mode  runtime=$($result.runtime_seconds)s  frames=$($result.frames_count)"

# ── Write behavior.json ───────────────────────────────────────────────────────
try {
    $result | ConvertTo-Json -Depth 6 | Out-File "$OutDir\behavior.json" -Encoding utf8 -Force
    Write-Host "behavior.json written → $OutDir\behavior.json"
} catch {
    Write-Host "FATAL: Cannot write behavior.json: $_"
    try { Stop-Transcript -ErrorAction SilentlyContinue } catch {}
    exit 1
}

# ── Write ui_runner_done.txt (host polls this) ────────────────────────────────
try {
    "done:$($result.runtime_seconds)s mode:$Mode frames:$($result.frames_count)" |
        Out-File "$OutDir\ui_runner_done.txt" -Encoding utf8 -Force
} catch {
    Write-Host "WARNING: Cannot write ui_runner_done.txt: $_"
}

try { Stop-Transcript -ErrorAction SilentlyContinue } catch {}
exit 0
