# Build Script for Sentinel v1.0.0
# Automates PyInstaller build process with validation

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Sentinel v1.0.0 - Production Build Script" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Verify Python and dependencies
Write-Host "[1/6] Verifying Python environment..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Python not found! Install Python 3.10+ from python.org" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Found: $pythonVersion" -ForegroundColor Green

# Check Python version >= 3.10
$versionMatch = $pythonVersion -match 'Python (\d+)\.(\d+)'
if ($versionMatch) {
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
        Write-Host "✗ Python 3.10+ required. Found: $pythonVersion" -ForegroundColor Red
        exit 1
    }
}

# Step 2: Install/verify PyInstaller
Write-Host ""
Write-Host "[2/6] Checking PyInstaller..." -ForegroundColor Yellow
$pyinstallerVersion = pip show pyinstaller 2>&1 | Select-String -Pattern "Version:"
if (-not $pyinstallerVersion) {
    Write-Host "PyInstaller not found. Installing..." -ForegroundColor Yellow
    pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ PyInstaller installation failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ PyInstaller installed" -ForegroundColor Green
} else {
    Write-Host "✓ $pyinstallerVersion" -ForegroundColor Green
}

# Step 3: Clean previous builds
Write-Host ""
Write-Host "[3/6] Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
    Write-Host "✓ Removed build/ directory" -ForegroundColor Green
}
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
    Write-Host "✓ Removed dist/ directory" -ForegroundColor Green
}
Write-Host "✓ Build directories cleaned" -ForegroundColor Green

# Step 4: Run PyInstaller
Write-Host ""
Write-Host "[4/6] Building executable with PyInstaller..." -ForegroundColor Yellow
Write-Host "This may take 5-10 minutes. Please wait..." -ForegroundColor Cyan

pyinstaller --noconfirm sentinel.spec

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ PyInstaller build failed!" -ForegroundColor Red
    Write-Host "Check the build log above for errors." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path "dist\Sentinel.exe")) {
    Write-Host "✗ Sentinel.exe not found in dist/ directory!" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Build completed successfully" -ForegroundColor Green

# Step 5: Verify executable
Write-Host ""
Write-Host "[5/6] Verifying executable..." -ForegroundColor Yellow

$exeSize = (Get-Item "dist\Sentinel.exe").Length / 1MB
Write-Host "✓ Sentinel.exe size: $([math]::Round($exeSize, 2)) MB" -ForegroundColor Green

# Calculate SHA256 hash
Write-Host "Calculating SHA256 hash..." -ForegroundColor Cyan
$hash = (Get-FileHash "dist\Sentinel.exe" -Algorithm SHA256).Hash
Write-Host "✓ SHA256: $hash" -ForegroundColor Green

# Save hash to file
$hash | Out-File "dist\Sentinel.exe.sha256"
Write-Host "✓ Hash saved to dist\Sentinel.exe.sha256" -ForegroundColor Green

# Step 6: Create release package
Write-Host ""
Write-Host "[6/6] Creating release package..." -ForegroundColor Yellow

# Copy additional files to dist/
Copy-Item ".env.example" "dist\" -ErrorAction SilentlyContinue
Copy-Item "README.md" "dist\" -ErrorAction SilentlyContinue
Copy-Item "LICENSE" "dist\" -ErrorAction SilentlyContinue
Copy-Item "requirements.txt" "dist\" -ErrorAction SilentlyContinue

# Create ZIP archive
$zipName = "Sentinel-v1.0.0-Windows-x64.zip"
if (Test-Path $zipName) {
    Remove-Item $zipName
}

Write-Host "Creating $zipName..." -ForegroundColor Cyan
Compress-Archive -Path "dist\*" -DestinationPath $zipName

if (Test-Path $zipName) {
    $zipSize = (Get-Item $zipName).Length / 1MB
    Write-Host "✓ Release package created: $zipName ($([math]::Round($zipSize, 2)) MB)" -ForegroundColor Green
} else {
    Write-Host "⚠ Warning: Failed to create ZIP archive" -ForegroundColor Yellow
}

# Final summary
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Build Complete! ✅" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Executable:  dist\Sentinel.exe ($([math]::Round($exeSize, 2)) MB)" -ForegroundColor White
Write-Host "SHA256:      $hash" -ForegroundColor White
if (Test-Path $zipName) {
    Write-Host "Package:     $zipName ($([math]::Round($zipSize, 2)) MB)" -ForegroundColor White
}
Write-Host ""
Write-Host "Test the executable:" -ForegroundColor Yellow
Write-Host "  cd dist" -ForegroundColor Cyan
Write-Host "  .\Sentinel.exe" -ForegroundColor Cyan
Write-Host ""
Write-Host "For distribution, upload:" -ForegroundColor Yellow
Write-Host "  - $zipName" -ForegroundColor Cyan
Write-Host "  - dist\Sentinel.exe.sha256 (for integrity verification)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test Sentinel.exe on a fresh Windows 11 machine" -ForegroundColor White
Write-Host "  2. Run for 10 minutes to verify stability" -ForegroundColor White
Write-Host "  3. Check for missing DLLs or 'Qt platform plugin' errors" -ForegroundColor White
Write-Host "  4. If all tests pass, tag release: git tag v1.0.0" -ForegroundColor White
Write-Host "  5. Push to GitHub: git push origin v1.0.0" -ForegroundColor White
Write-Host ""
