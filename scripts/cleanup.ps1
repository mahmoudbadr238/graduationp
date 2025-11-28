#!/usr/bin/env powershell
# Sentinel Project Cleanup Script
# This script organizes and archives unused files

param(
    [switch]$Preview = $false,
    [switch]$Execute = $false
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Sentinel Project Cleanup Utility" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (-not $Preview -and -not $Execute) {
    Write-Host "Usage: .\cleanup.ps1 -Preview    # Show what would be cleaned" -ForegroundColor Yellow
    Write-Host "       .\cleanup.ps1 -Execute    # Actually clean up files" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Run with -Preview first to see what will be cleaned!" -ForegroundColor Green
    exit
}

$archiveRoot = ".\\_cleanup_archive"
$items = @(
    # Log files to move
    @{
        Source = "app_console.log"
        Destination = "_cleanup_archive\\logs\\app_console.log"
        Type = "Log"
        Description = "Console output log"
    },
    @{
        Source = "app_errors.log"
        Destination = "_cleanup_archive\\logs\\app_errors.log"
        Type = "Log"
        Description = "Error log"
    },
    @{
        Source = "app_final_err.txt"
        Destination = "_cleanup_archive\\logs\\app_final_err.txt"
        Type = "Log"
        Description = "Final error output"
    },
    @{
        Source = "app_final.txt"
        Destination = "_cleanup_archive\\logs\\app_final.txt"
        Type = "Log"
        Description = "Final output"
    },
    @{
        Source = "output.txt"
        Destination = "_cleanup_archive\\test_data\\output.txt"
        Type = "Test Data"
        Description = "Generic output file"
    },
    
    # Test/diagnostic data
    @{
        Source = "diags_test.json"
        Destination = "_cleanup_archive\\test_data\\diags_test.json"
        Type = "Test Data"
        Description = "Diagnostic test results"
    },
    @{
        Source = "bandit_results.json"
        Destination = "_cleanup_archive\\test_data\\bandit_results.json"
        Type = "Test Data"
        Description = "Security scan results"
    },
    
    # QA Reports to move
    @{
        Source = "APP_TESTING_REPORT.md"
        Destination = "_cleanup_archive\\reports\\APP_TESTING_REPORT.md"
        Type = "Report"
        Description = "QA testing report"
    },
    @{
        Source = "QA_REVIEW_SUMMARY.md"
        Destination = "_cleanup_archive\\reports\\QA_REVIEW_SUMMARY.md"
        Type = "Report"
        Description = "QA review summary"
    },
    @{
        Source = "QA_REVIEW_DOCUMENTATION_INDEX.md"
        Destination = "_cleanup_archive\\reports\\QA_REVIEW_DOCUMENTATION_INDEX.md"
        Type = "Report"
        Description = "QA documentation index"
    },
    @{
        Source = "QA_REVIEW_EXECUTIVE_SUMMARY.txt"
        Destination = "_cleanup_archive\\reports\\QA_REVIEW_EXECUTIVE_SUMMARY.txt"
        Type = "Report"
        Description = "QA executive summary"
    },
    @{
        Source = "QA_PRODUCTION_HARDENING_REVIEW.md"
        Destination = "_cleanup_archive\\reports\\QA_PRODUCTION_HARDENING_REVIEW.md"
        Type = "Report"
        Description = "QA production hardening review"
    },
    @{
        Source = "GUI_REVIEW_COMPLETE.md"
        Destination = "_cleanup_archive\\reports\\GUI_REVIEW_COMPLETE.md"
        Type = "Report"
        Description = "GUI review complete"
    },
    @{
        Source = "GUI_RESPONSIVENESS_REVIEW.md"
        Destination = "_cleanup_archive\\reports\\GUI_RESPONSIVENESS_REVIEW.md"
        Type = "Report"
        Description = "GUI responsiveness review"
    },
    @{
        Source = "RELEASE_CHECKLIST.md"
        Destination = "_cleanup_archive\\reports\\RELEASE_CHECKLIST.md"
        Type = "Report"
        Description = "Release checklist"
    },
    @{
        Source = "RELEASE_DECISION.md"
        Destination = "_cleanup_archive\\reports\\RELEASE_DECISION.md"
        Type = "Report"
        Description = "Release decision"
    },
    @{
        Source = "RELEASE_READY.md"
        Destination = "_cleanup_archive\\reports\\RELEASE_READY.md"
        Type = "Report"
        Description = "Release ready confirmation"
    },
    
    # Old documentation to move
    @{
        Source = "COMPREHENSIVE_DIFFS.md"
        Destination = "_cleanup_archive\\old_docs\\COMPREHENSIVE_DIFFS.md"
        Type = "Old Doc"
        Description = "Comprehensive diffs (historical)"
    },
    @{
        Source = "CLEANUP_SUMMARY.md"
        Destination = "_cleanup_archive\\old_docs\\CLEANUP_SUMMARY.md"
        Type = "Old Doc"
        Description = "Cleanup summary (historical)"
    },
    @{
        Source = "DELIVERY_SUMMARY.md"
        Destination = "_cleanup_archive\\old_docs\\DELIVERY_SUMMARY.md"
        Type = "Old Doc"
        Description = "Delivery summary (historical)"
    },
    @{
        Source = "HOTFIX_SQLITEREPO.md"
        Destination = "_cleanup_archive\\old_docs\\HOTFIX_SQLITEREPO.md"
        Type = "Old Doc"
        Description = "SQLite repo hotfix (historical)"
    },
    @{
        Source = "ISSUE_P0_GPU_PACKAGE_VALIDATION.md"
        Destination = "_cleanup_archive\\old_docs\\ISSUE_P0_GPU_PACKAGE_VALIDATION.md"
        Type = "Old Doc"
        Description = "GPU package validation issue (resolved)"
    },
    @{
        Source = "ISSUE_P1_HIGH_PRIORITY_FIXES.md"
        Destination = "_cleanup_archive\\old_docs\\ISSUE_P1_HIGH_PRIORITY_FIXES.md"
        Type = "Old Doc"
        Description = "High priority fixes (resolved)"
    },
    @{
        Source = "PROJECT_STRUCTURE.md"
        Destination = "_cleanup_archive\\old_docs\\PROJECT_STRUCTURE.md"
        Type = "Old Doc"
        Description = "Project structure (superseded by FILE_ORGANIZATION_GUIDE.md)"
    },
    @{
        Source = "RESPONSIVE_UI_CHANGES.md"
        Destination = "_cleanup_archive\\old_docs\\RESPONSIVE_UI_CHANGES.md"
        Type = "Old Doc"
        Description = "Responsive UI changes (historical)"
    },
    @{
        Source = "QML_FIXES_SUMMARY.md"
        Destination = "_cleanup_archive\\old_docs\\QML_FIXES_SUMMARY.md"
        Type = "Old Doc"
        Description = "QML fixes summary (historical)"
    },
    @{
        Source = "FINAL_FIX_SUMMARY.md"
        Destination = "_cleanup_archive\\old_docs\\FINAL_FIX_SUMMARY.md"
        Type = "Old Doc"
        Description = "Final fix summary (historical)"
    }
)

Write-Host "Files to Archive:" -ForegroundColor Green
Write-Host "=====================" -ForegroundColor Green
Write-Host ""

$byType = @{}
$totalSize = 0

foreach ($item in $items) {
    if (Test-Path $item.Source) {
        $file = Get-Item $item.Source
        $size = $file.Length
        $totalSize += $size
        
        if (-not $byType.ContainsKey($item.Type)) {
            $byType[$item.Type] = @()
        }
        $byType[$item.Type] += @{
            Source = $item.Source
            Destination = $item.Destination
            Description = $item.Description
            Size = $size
        }
    }
}

foreach ($type in $byType.Keys | Sort-Object) {
    Write-Host "$type Files:" -ForegroundColor Cyan
    $typeItems = $byType[$type]
    foreach ($item in $typeItems) {
        $sizeKB = [math]::Round($item.Size / 1KB, 2)
        Write-Host "  • $($item.Source)" -ForegroundColor White
        Write-Host "    Description: $($item.Description)" -ForegroundColor Gray
        Write-Host "    Size: $sizeKB KB" -ForegroundColor Gray
        Write-Host "    → $($item.Destination)" -ForegroundColor Yellow
    }
    Write-Host ""
}

$totalSizeMB = [math]::Round($totalSize / 1MB, 2)
Write-Host "Total Size to Archive: $totalSizeMB MB" -ForegroundColor Cyan
Write-Host ""

if ($Preview) {
    Write-Host "Preview Mode: No files were moved" -ForegroundColor Yellow
    Write-Host "Run with -Execute to actually move these files" -ForegroundColor Yellow
}

if ($Execute) {
    Write-Host "Executing cleanup..." -ForegroundColor Green
    Write-Host ""
    
    # Ensure archive directories exist
    if (-not (Test-Path $archiveRoot)) {
        New-Item -ItemType Directory -Path $archiveRoot -Force | Out-Null
    }
    if (-not (Test-Path "$archiveRoot\\logs")) {
        New-Item -ItemType Directory -Path "$archiveRoot\\logs" -Force | Out-Null
    }
    if (-not (Test-Path "$archiveRoot\\reports")) {
        New-Item -ItemType Directory -Path "$archiveRoot\\reports" -Force | Out-Null
    }
    if (-not (Test-Path "$archiveRoot\\test_data")) {
        New-Item -ItemType Directory -Path "$archiveRoot\\test_data" -Force | Out-Null
    }
    if (-not (Test-Path "$archiveRoot\\old_docs")) {
        New-Item -ItemType Directory -Path "$archiveRoot\\old_docs" -Force | Out-Null
    }
    
    # Move files
    $movedCount = 0
    foreach ($item in $items) {
        if (Test-Path $item.Source) {
            Move-Item -Path $item.Source -Destination $item.Destination -Force
            Write-Host "✓ Moved: $($item.Source)" -ForegroundColor Green
            $movedCount++
        }
    }
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Cleanup Complete!" -ForegroundColor Green
    Write-Host "Files moved: $movedCount" -ForegroundColor Green
    Write-Host "Total archived: $totalSizeMB MB" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "Additional Cleanup Available:" -ForegroundColor Yellow
    Write-Host "• Delete build artifacts: Remove 'dist/' and 'build/' directories" -ForegroundColor Gray
    Write-Host "• Clear cache: Remove '.pytest_cache/', '.ruff_cache/', '__pycache__/'" -ForegroundColor Gray
    Write-Host "• See FILE_ORGANIZATION_GUIDE.md for complete details" -ForegroundColor Gray
}

Write-Host ""

