param(
    [string]$SourceRoot = (Join-Path $PSScriptRoot "..\.."),
    [string]$Destination = (Join-Path $PSScriptRoot "..\..\archive\graduationp_linux_build.zip")
)

$source = (Resolve-Path $SourceRoot).Path
$staging = Join-Path ([System.IO.Path]::GetTempPath()) "sentinel_linux_pack"

if (Test-Path $Destination) {
    Remove-Item $Destination -Force
}
if (Test-Path $staging) {
    Remove-Item $staging -Recurse -Force
}
New-Item -ItemType Directory -Path $staging | Out-Null

$skipDirs = @(
    ".git", ".github", ".vscode",
    "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    ".venv", "venv", "env",
    "dist", "build", "build_artifacts",
    "artifacts", "archive", "_cleanup_archive",
    ".gemini", ".cursor", ".claude",
    "sandbox_output", "sandbox_temp",
    "node_modules"
)

$skipFiles = @(
    "_fix_inline_flags.py", "_fix_subprocess.py",
    "graduationp_linux_build.zip",
    "_diag.py", "_diag.txt",
    "crash_traceback.txt"
)

$skipExts = @(".db", ".sqlite", ".cache", ".log", ".whl", ".egg")

Write-Host "Copying release files to staging..." -ForegroundColor Cyan

Get-ChildItem -Path $source | ForEach-Object {
    if ($_.PSIsContainer) {
        if ($skipDirs -notcontains $_.Name) {
            Copy-Item $_.FullName (Join-Path $staging $_.Name) -Recurse -Force
        }
        return
    }

    $skip = $false
    if ($skipFiles -contains $_.Name) { $skip = $true }
    if ($skipExts -contains $_.Extension) { $skip = $true }
    if ($_.Name -like "_diag*") { $skip = $true }
    if ($_.Name -like "crash_log*") { $skip = $true }
    if (-not $skip) {
        Copy-Item $_.FullName (Join-Path $staging $_.Name) -Force
    }
}

Get-ChildItem $staging -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $staging -Recurse -File -Filter "*.pyc" |
    Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem $staging -Recurse -File | Where-Object {
    $skipExts -contains $_.Extension
} | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "Creating Linux source archive..." -ForegroundColor Cyan
Compress-Archive -Path "$staging\*" -DestinationPath $Destination -Force

Remove-Item $staging -Recurse -Force

$sizeMb = [math]::Round((Get-Item $Destination).Length / 1MB, 1)
Write-Host ""
Write-Host "[OK] Created: $Destination ($sizeMb MB)" -ForegroundColor Green
Write-Host "Transfer to Linux and run: ./run_linux.sh" -ForegroundColor Yellow
