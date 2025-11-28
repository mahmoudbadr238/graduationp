#!/usr/bin/env powershell
# Sentinel Project - Complete File Organization Script
# This script reorganizes all files into their proper folders

param(
    [switch]$Preview = $false,
    [switch]$Execute = $false
)

Write-Host "╔════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  SENTINEL PROJECT FILE ORGANIZATION       ║" -ForegroundColor Cyan
Write-Host "║  Complete Restructuring Tool              ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

if (-not $Preview -and -not $Execute) {
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\organize.ps1 -Preview      # See proposed changes" -ForegroundColor White
    Write-Host "  .\organize.ps1 -Execute      # Execute organization" -ForegroundColor White
    Write-Host ""
    Write-Host "⚠️  Always run -Preview first to verify changes!" -ForegroundColor Yellow
    exit
}

# Define file movements
$moves = @(
    # Config files
    @{ Source = "pyproject.toml"; Dest = "config/pyproject.toml"; Type = "Config" },
    @{ Source = "pytest.ini"; Dest = "config/pytest.ini"; Type = "Config" },
    @{ Source = ".env.example"; Dest = "config/.env.example"; Type = "Config" },
    @{ Source = "sentinel.spec"; Dest = "config/sentinel.spec"; Type = "Config" },
    @{ Source = ".pre-commit-config.yaml"; Dest = "config/.pre-commit-config.yaml"; Type = "Config" },
    
    # Documentation - Active
    @{ Source = "README.md"; Dest = "docs/README.md"; Type = "Docs" },
    @{ Source = "QUICKSTART.md"; Dest = "docs/QUICKSTART.md"; Type = "Docs" },
    @{ Source = "SECURITY.md"; Dest = "docs/SECURITY.md"; Type = "Docs" },
    @{ Source = "PRIVACY.md"; Dest = "docs/PRIVACY.md"; Type = "Docs" },
    @{ Source = "CHANGELOG.md"; Dest = "docs/CHANGELOG.md"; Type = "Docs" },
    @{ Source = "CONTRIBUTING.md"; Dest = "docs/CONTRIBUTING.md"; Type = "Docs" },
    @{ Source = "LICENSE"; Dest = "docs/LICENSE"; Type = "Docs" },
    
    # Documentation - Guides
    @{ Source = "FILE_ORGANIZATION_GUIDE.md"; Dest = "docs/guides/FILE_ORGANIZATION_GUIDE.md"; Type = "Guides" },
    @{ Source = "CLEANUP_INSTRUCTIONS.md"; Dest = "docs/guides/CLEANUP_INSTRUCTIONS.md"; Type = "Guides" },
    @{ Source = "README_CLEANUP.md"; Dest = "docs/guides/README_CLEANUP.md"; Type = "Guides" },
    @{ Source = "ORGANIZATION_COMPLETE.md"; Dest = "docs/guides/ORGANIZATION_COMPLETE.md"; Type = "Guides" },
    
    # Documentation - User
    @{ Source = "docs/USER_MANUAL.md"; Dest = "docs/user/USER_MANUAL.md"; Type = "User Docs" },
    @{ Source = "docs/QUICK_REFERENCE.md"; Dest = "docs/user/QUICK_REFERENCE.md"; Type = "User Docs" },
    
    # Documentation - API/Developer
    @{ Source = "docs/API_INTEGRATION_GUIDE.md"; Dest = "docs/api/API_INTEGRATION_GUIDE.md"; Type = "API Docs" },
    @{ Source = "docs/README_BACKEND.md"; Dest = "docs/api/README_BACKEND.md"; Type = "API Docs" },
    @{ Source = "docs/PERFORMANCE.md"; Dest = "docs/api/PERFORMANCE.md"; Type = "API Docs" },
    @{ Source = "docs/AMD_GPU_MONITORING.md"; Dest = "docs/api/AMD_GPU_MONITORING.md"; Type = "API Docs" },
    @{ Source = "docs/GPU_SUBPROCESS_README.md"; Dest = "docs/api/GPU_SUBPROCESS_README.md"; Type = "API Docs" },
    @{ Source = "docs/GPU_TELEMETRY_SUBPROCESS.md"; Dest = "docs/api/GPU_TELEMETRY_SUBPROCESS.md"; Type = "API Docs" },
    @{ Source = "docs/README_RELEASE_NOTES.md"; Dest = "docs/api/README_RELEASE_NOTES.md"; Type = "API Docs" },
    
    # Archive - Reports
    @{ Source = "APP_TESTING_REPORT.md"; Dest = "archive/reports/APP_TESTING_REPORT.md"; Type = "Reports" },
    @{ Source = "QA_REVIEW_SUMMARY.md"; Dest = "archive/reports/QA_REVIEW_SUMMARY.md"; Type = "Reports" },
    @{ Source = "QA_REVIEW_DOCUMENTATION_INDEX.md"; Dest = "archive/reports/QA_REVIEW_DOCUMENTATION_INDEX.md"; Type = "Reports" },
    @{ Source = "QA_REVIEW_EXECUTIVE_SUMMARY.txt"; Dest = "archive/reports/QA_REVIEW_EXECUTIVE_SUMMARY.txt"; Type = "Reports" },
    @{ Source = "QA_PRODUCTION_HARDENING_REVIEW.md"; Dest = "archive/reports/QA_PRODUCTION_HARDENING_REVIEW.md"; Type = "Reports" },
    @{ Source = "GUI_REVIEW_COMPLETE.md"; Dest = "archive/reports/GUI_REVIEW_COMPLETE.md"; Type = "Reports" },
    @{ Source = "GUI_RESPONSIVENESS_REVIEW.md"; Dest = "archive/reports/GUI_RESPONSIVENESS_REVIEW.md"; Type = "Reports" },
    @{ Source = "RELEASE_CHECKLIST.md"; Dest = "archive/reports/RELEASE_CHECKLIST.md"; Type = "Reports" },
    @{ Source = "RELEASE_DECISION.md"; Dest = "archive/reports/RELEASE_DECISION.md"; Type = "Reports" },
    @{ Source = "RELEASE_READY.md"; Dest = "archive/reports/RELEASE_READY.md"; Type = "Reports" },
    
    # Archive - Logs
    @{ Source = "app_console.log"; Dest = "archive/logs/app_console.log"; Type = "Logs" },
    @{ Source = "app_errors.log"; Dest = "archive/logs/app_errors.log"; Type = "Logs" },
    @{ Source = "app_final.txt"; Dest = "archive/logs/app_final.txt"; Type = "Logs" },
    @{ Source = "app_final_err.txt"; Dest = "archive/logs/app_final_err.txt"; Type = "Logs" },
    @{ Source = "output.txt"; Dest = "archive/logs/output.txt"; Type = "Logs" },
    
    # Archive - Test Data
    @{ Source = "diags_test.json"; Dest = "archive/test_data/diags_test.json"; Type = "Test Data" },
    @{ Source = "bandit_results.json"; Dest = "archive/test_data/bandit_results.json"; Type = "Test Data" },
    
    # Archive - Old Documentation
    @{ Source = "COMPREHENSIVE_DIFFS.md"; Dest = "archive/docs/COMPREHENSIVE_DIFFS.md"; Type = "Old Docs" },
    @{ Source = "DELIVERY_SUMMARY.md"; Dest = "archive/docs/DELIVERY_SUMMARY.md"; Type = "Old Docs" },
    @{ Source = "HOTFIX_SQLITEREPO.md"; Dest = "archive/docs/HOTFIX_SQLITEREPO.md"; Type = "Old Docs" },
    @{ Source = "ISSUE_P0_GPU_PACKAGE_VALIDATION.md"; Dest = "archive/docs/ISSUE_P0_GPU_PACKAGE_VALIDATION.md"; Type = "Old Docs" },
    @{ Source = "ISSUE_P1_HIGH_PRIORITY_FIXES.md"; Dest = "archive/docs/ISSUE_P1_HIGH_PRIORITY_FIXES.md"; Type = "Old Docs" },
    @{ Source = "PROJECT_STRUCTURE.md"; Dest = "archive/docs/PROJECT_STRUCTURE.md"; Type = "Old Docs" },
    @{ Source = "RESPONSIVE_UI_CHANGES.md"; Dest = "archive/docs/RESPONSIVE_UI_CHANGES.md"; Type = "Old Docs" },
    @{ Source = "QML_FIXES_SUMMARY.md"; Dest = "archive/docs/QML_FIXES_SUMMARY.md"; Type = "Old Docs" },
    @{ Source = "FINAL_FIX_SUMMARY.md"; Dest = "archive/docs/FINAL_FIX_SUMMARY.md"; Type = "Old Docs" }
)

# Display summary
Write-Host "📊 ORGANIZATION PLAN:" -ForegroundColor Cyan
Write-Host ""

$byType = @{}
$totalSize = 0
$fileCount = 0

foreach ($move in $moves) {
    if (Test-Path $move.Source) {
        $file = Get-Item $move.Source
        $size = $file.Length
        $totalSize += $size
        $fileCount++
        
        if (-not $byType.ContainsKey($move.Type)) {
            $byType[$move.Type] = @()
        }
        $byType[$move.Type] += $move
    }
}

foreach ($type in $byType.Keys | Sort-Object) {
    Write-Host "📁 $type ($(($byType[$type] | Measure-Object).Count) files)" -ForegroundColor Green
    foreach ($move in $byType[$type]) {
        Write-Host "   ├─ $($move.Source)" -ForegroundColor Gray
        Write-Host "   └─→ $($move.Dest)" -ForegroundColor Yellow
    }
    Write-Host ""
}

Write-Host "📊 STATISTICS:" -ForegroundColor Cyan
$totalSizeMB = [math]::Round($totalSize / 1MB, 2)
Write-Host "   • Files to organize: $fileCount" -ForegroundColor White
Write-Host "   • Total size: $totalSizeMB MB" -ForegroundColor White
Write-Host "   • Categories: $(($byType.Keys | Measure-Object).Count)" -ForegroundColor White
Write-Host ""

if ($Preview) {
    Write-Host "ℹ️  PREVIEW MODE - No changes made" -ForegroundColor Yellow
    Write-Host "Run with -Execute to perform the organization" -ForegroundColor Yellow
}

if ($Execute) {
    Write-Host "🔄 EXECUTING ORGANIZATION..." -ForegroundColor Green
    Write-Host ""
    
    $successCount = 0
    $errorCount = 0
    
    foreach ($move in $moves) {
        if (Test-Path $move.Source) {
            try {
                # Create destination directory if it doesn't exist
                $destDir = Split-Path -Parent $move.Dest
                if (-not (Test-Path $destDir)) {
                    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
                }
                
                # Move file
                Move-Item -Path $move.Source -Destination $move.Dest -Force -ErrorAction Stop
                Write-Host "✓ Moved: $($move.Source) → $($move.Dest)" -ForegroundColor Green
                $successCount++
            }
            catch {
                Write-Host "✗ Error moving $($move.Source): $($_.Exception.Message)" -ForegroundColor Red
                $errorCount++
            }
        }
    }
    
    Write-Host ""
    Write-Host "╔════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║           ORGANIZATION COMPLETE!           ║" -ForegroundColor Green
    Write-Host "╚════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    Write-Host "✅ Successfully moved: $successCount files" -ForegroundColor Green
    if ($errorCount -gt 0) {
        Write-Host "❌ Errors: $errorCount files" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "📁 New folder structure:" -ForegroundColor Cyan
    Write-Host "   • config/          - Configuration files" -ForegroundColor White
    Write-Host "   • docs/            - Active documentation" -ForegroundColor White
    Write-Host "   • docs/guides/     - Setup & organization guides" -ForegroundColor White
    Write-Host "   • docs/user/       - User manuals" -ForegroundColor White
    Write-Host "   • docs/api/        - API & developer docs" -ForegroundColor White
    Write-Host "   • archive/         - Historical files & reports" -ForegroundColor White
}

Write-Host ""

