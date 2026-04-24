$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$configDir = Join-Path $projectRoot "config"
$distDir = Join-Path $projectRoot "dist"
$bundleDir = Join-Path $distDir "Sentinel"
$buildDir = Join-Path $projectRoot "build"

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pythonExe = if (Test-Path $venvPython) { $venvPython } else { "python" }

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host $Message -ForegroundColor Yellow
}

function Invoke-PyInstallerSpec {
    param([string]$SpecPath)

    & $pythonExe -m PyInstaller --noconfirm --clean $SpecPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed for $SpecPath"
    }
}

function Assert-File {
    param([string]$PathToCheck)

    if (-not (Test-Path $PathToCheck)) {
        throw "Expected file not found: $PathToCheck"
    }
}

function Copy-IfExists {
    param(
        [string]$SourcePath,
        [string]$DestinationDirectory
    )

    if (Test-Path $SourcePath) {
        Copy-Item $SourcePath $DestinationDirectory -Force
    }
}

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Sentinel Windows Build" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Python: $pythonExe"

Write-Step "[1/6] Cleaning previous build outputs"
Get-Process -Name "Sentinel", "sentinel_gpu_worker", "sentinel_url_detonator" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

foreach ($path in @($buildDir, $distDir)) {
    if (Test-Path $path) {
        $removed = $false
        for ($attempt = 1; $attempt -le 3 -and -not $removed; $attempt++) {
            try {
                Remove-Item $path -Recurse -Force -ErrorAction Stop
                $removed = $true
            }
            catch {
                if ($attempt -eq 3) {
                    throw
                }
                Start-Sleep -Seconds 2
            }
        }
    }
}

Write-Step "[2/6] Building Sentinel GUI bundle"
Invoke-PyInstallerSpec (Join-Path $configDir "sentinel.spec")
Assert-File (Join-Path $bundleDir "Sentinel.exe")

Write-Step "[3/6] Building helper executables"
Invoke-PyInstallerSpec (Join-Path $configDir "sentinel_gpu_worker.spec")
Invoke-PyInstallerSpec (Join-Path $configDir "sentinel_url_detonator.spec")
Assert-File (Join-Path $distDir "sentinel_gpu_worker.exe")
Assert-File (Join-Path $distDir "sentinel_url_detonator.exe")

Write-Step "[4/6] Building sandbox agent"
& $pythonExe (Join-Path $projectRoot "scripts\build_agent.py")
if ($LASTEXITCODE -ne 0) {
    throw "sandbox agent build failed"
}
Assert-File (Join-Path $distDir "sentinel_agent.exe")

Write-Step "[5/6] Assembling Windows app bundle"
Copy-Item (Join-Path $distDir "sentinel_gpu_worker.exe") $bundleDir -Force
Copy-Item (Join-Path $distDir "sentinel_url_detonator.exe") $bundleDir -Force
Copy-Item (Join-Path $distDir "sentinel_agent.exe") $bundleDir -Force

Copy-IfExists (Join-Path $projectRoot ".env.example") $bundleDir
Copy-IfExists (Join-Path $projectRoot "README.md") $bundleDir
Copy-IfExists (Join-Path $projectRoot "LICENSE") $bundleDir

$sentinelExe = Join-Path $bundleDir "Sentinel.exe"
$hash = (Get-FileHash $sentinelExe -Algorithm SHA256).Hash
$hashFile = Join-Path $bundleDir "Sentinel.exe.sha256"
$hash | Out-File -FilePath $hashFile -Encoding ascii

Write-Step "[6/6] Validating packaged executables"
$diagProcess = Start-Process -FilePath $sentinelExe -ArgumentList "--diagnose" -PassThru -Wait -WindowStyle Hidden
if ($diagProcess.ExitCode -ne 0) {
    throw "Packaged Sentinel.exe --diagnose failed with exit code $($diagProcess.ExitCode)"
}

$detonatorExe = Join-Path $bundleDir "sentinel_url_detonator.exe"
$helpProcess = Start-Process -FilePath $detonatorExe -ArgumentList "--help" -PassThru -Wait -WindowStyle Hidden
if ($helpProcess.ExitCode -ne 0) {
    throw "sentinel_url_detonator.exe --help failed with exit code $($helpProcess.ExitCode)"
}

$gpuStdout = Join-Path $buildDir "sentinel_gpu_worker.stdout.log"
$gpuStderr = Join-Path $buildDir "sentinel_gpu_worker.stderr.log"
$gpuWorkerExe = Join-Path $bundleDir "sentinel_gpu_worker.exe"
$gpuProcess = Start-Process -FilePath $gpuWorkerExe -ArgumentList "2000" -PassThru -RedirectStandardOutput $gpuStdout -RedirectStandardError $gpuStderr -WindowStyle Hidden
Start-Sleep -Seconds 10
if (-not $gpuProcess.HasExited) {
    Stop-Process -Id $gpuProcess.Id -Force
    $gpuProcess.WaitForExit()
}

if (-not (Test-Path $gpuStdout)) {
    throw "GPU worker produced no stdout log"
}

$gpuOutput = Get-Content $gpuStdout -Raw
if ($gpuOutput -notmatch '"type":"startup"' -or $gpuOutput -notmatch '"type":"init"') {
    throw "GPU worker did not emit the expected startup/init messages"
}

$zipPath = Join-Path $distDir "Sentinel-Windows-x64.zip"
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}
Compress-Archive -Path (Join-Path $bundleDir "*") -DestinationPath $zipPath

$bundleSizeMb = [math]::Round(((Get-Item $sentinelExe).Length / 1MB), 2)
$zipSizeMb = [math]::Round(((Get-Item $zipPath).Length / 1MB), 2)

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Build Complete" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Bundle:   $bundleDir" -ForegroundColor White
Write-Host "App EXE:  $sentinelExe ($bundleSizeMb MB)" -ForegroundColor White
Write-Host "ZIP:      $zipPath ($zipSizeMb MB)" -ForegroundColor White
Write-Host "SHA256:   $hash" -ForegroundColor White
