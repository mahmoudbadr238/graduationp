@echo off
REM Sentinel Project - File Organization Script
REM This script organizes files into their proper folders

setlocal enabledelayedexpansion

echo.
echo ======================================================
echo   SENTINEL PROJECT FILE ORGANIZATION
echo   Complete Restructuring Tool
echo ======================================================
echo.

if "%1"=="" (
    echo Usage:
    echo   organize.bat preview     - See proposed changes
    echo   organize.bat execute     - Execute organization
    echo.
    echo Warning: Always run PREVIEW first to verify changes!
    exit /b
)

REM Define file movements
setlocal

REM Create directories if they don't exist
if not exist "config" mkdir config
if not exist "docs\guides" mkdir docs\guides
if not exist "docs\user" mkdir docs\user
if not exist "docs\api" mkdir docs\api
if not exist "archive\reports" mkdir archive\reports
if not exist "archive\logs" mkdir archive\logs
if not exist "archive\test_data" mkdir archive\test_data
if not exist "archive\docs" mkdir archive\docs

echo.
echo ^[1/4^] CONFIG FILES
echo ==================
if "%1"=="preview" (
    echo [PREVIEW] pyproject.toml ^-^> config/
    echo [PREVIEW] pytest.ini ^-^> config/
    echo [PREVIEW] sentinel.spec ^-^> config/
) else if "%1"=="execute" (
    if exist "pyproject.toml" move /Y "pyproject.toml" "config\" 
    if exist "pytest.ini" move /Y "pytest.ini" "config\"
    if exist "sentinel.spec" move /Y "sentinel.spec" "config\"
    echo MOVED: Config files
)

echo.
echo ^[2/4^] DOCUMENTATION
echo ====================
if "%1"=="preview" (
    echo [PREVIEW] FILE_ORGANIZATION_GUIDE.md ^-^> docs/guides/
    echo [PREVIEW] CLEANUP_INSTRUCTIONS.md ^-^> docs/guides/
    echo [PREVIEW] README_CLEANUP.md ^-^> docs/guides/
) else if "%1"=="execute" (
    if exist "FILE_ORGANIZATION_GUIDE.md" move /Y "FILE_ORGANIZATION_GUIDE.md" "docs\guides\"
    if exist "CLEANUP_INSTRUCTIONS.md" move /Y "CLEANUP_INSTRUCTIONS.md" "docs\guides\"
    if exist "README_CLEANUP.md" move /Y "README_CLEANUP.md" "docs\guides\"
    if exist "ORGANIZATION_COMPLETE.md" move /Y "ORGANIZATION_COMPLETE.md" "docs\guides\"
    if exist "docs\USER_MANUAL.md" move /Y "docs\USER_MANUAL.md" "docs\user\"
    if exist "docs\QUICK_REFERENCE.md" move /Y "docs\QUICK_REFERENCE.md" "docs\user\"
    if exist "docs\API_INTEGRATION_GUIDE.md" move /Y "docs\API_INTEGRATION_GUIDE.md" "docs\api\"
    if exist "docs\README_BACKEND.md" move /Y "docs\README_BACKEND.md" "docs\api\"
    if exist "docs\PERFORMANCE.md" move /Y "docs\PERFORMANCE.md" "docs\api\"
    if exist "docs\AMD_GPU_MONITORING.md" move /Y "docs\AMD_GPU_MONITORING.md" "docs\api\"
    if exist "docs\GPU_SUBPROCESS_README.md" move /Y "docs\GPU_SUBPROCESS_README.md" "docs\api\"
    if exist "docs\GPU_TELEMETRY_SUBPROCESS.md" move /Y "docs\GPU_TELEMETRY_SUBPROCESS.md" "docs\api\"
    if exist "docs\README_RELEASE_NOTES.md" move /Y "docs\README_RELEASE_NOTES.md" "docs\api\"
    echo MOVED: Documentation files
)

echo.
echo ^[3/4^] ARCHIVE - REPORTS ^& LOGS
echo ==================================
if "%1"=="preview" (
    echo [PREVIEW] APP_TESTING_REPORT.md ^-^> archive/reports/
    echo [PREVIEW] QA_REVIEW_*.md ^-^> archive/reports/
    echo [PREVIEW] app_*.txt / *.log ^-^> archive/logs/
) else if "%1"=="execute" (
    if exist "APP_TESTING_REPORT.md" move /Y "APP_TESTING_REPORT.md" "archive\reports\"
    if exist "QA_REVIEW_SUMMARY.md" move /Y "QA_REVIEW_SUMMARY.md" "archive\reports\"
    if exist "QA_REVIEW_DOCUMENTATION_INDEX.md" move /Y "QA_REVIEW_DOCUMENTATION_INDEX.md" "archive\reports\"
    if exist "QA_REVIEW_EXECUTIVE_SUMMARY.txt" move /Y "QA_REVIEW_EXECUTIVE_SUMMARY.txt" "archive\reports\"
    if exist "QA_PRODUCTION_HARDENING_REVIEW.md" move /Y "QA_PRODUCTION_HARDENING_REVIEW.md" "archive\reports\"
    if exist "GUI_REVIEW_COMPLETE.md" move /Y "GUI_REVIEW_COMPLETE.md" "archive\reports\"
    if exist "GUI_RESPONSIVENESS_REVIEW.md" move /Y "GUI_RESPONSIVENESS_REVIEW.md" "archive\reports\"
    if exist "RELEASE_CHECKLIST.md" move /Y "RELEASE_CHECKLIST.md" "archive\reports\"
    if exist "RELEASE_DECISION.md" move /Y "RELEASE_DECISION.md" "archive\reports\"
    if exist "RELEASE_READY.md" move /Y "RELEASE_READY.md" "archive\reports\"
    if exist "app_final.txt" move /Y "app_final.txt" "archive\logs\"
    if exist "app_final_err.txt" move /Y "app_final_err.txt" "archive\logs\"
    if exist "output.txt" move /Y "output.txt" "archive\logs\"
    echo MOVED: Reports and logs
)

echo.
echo ^[4/4^] ARCHIVE - OLD DOCUMENTATION
echo =====================================
if "%1"=="preview" (
    echo [PREVIEW] COMPREHENSIVE_DIFFS.md ^-^> archive/docs/
    echo [PREVIEW] DELIVERY_SUMMARY.md ^-^> archive/docs/
    echo [PREVIEW] HOTFIX_*.md, ISSUE_*.md ^-^> archive/docs/
) else if "%1"=="execute" (
    if exist "COMPREHENSIVE_DIFFS.md" move /Y "COMPREHENSIVE_DIFFS.md" "archive\docs\"
    if exist "DELIVERY_SUMMARY.md" move /Y "DELIVERY_SUMMARY.md" "archive\docs\"
    if exist "HOTFIX_SQLITEREPO.md" move /Y "HOTFIX_SQLITEREPO.md" "archive\docs\"
    if exist "ISSUE_P0_GPU_PACKAGE_VALIDATION.md" move /Y "ISSUE_P0_GPU_PACKAGE_VALIDATION.md" "archive\docs\"
    if exist "ISSUE_P1_HIGH_PRIORITY_FIXES.md" move /Y "ISSUE_P1_HIGH_PRIORITY_FIXES.md" "archive\docs\"
    if exist "PROJECT_STRUCTURE.md" move /Y "PROJECT_STRUCTURE.md" "archive\docs\"
    if exist "RESPONSIVE_UI_CHANGES.md" move /Y "RESPONSIVE_UI_CHANGES.md" "archive\docs\"
    if exist "QML_FIXES_SUMMARY.md" move /Y "QML_FIXES_SUMMARY.md" "archive\docs\"
    if exist "FINAL_FIX_SUMMARY.md" move /Y "FINAL_FIX_SUMMARY.md" "archive\docs\"
    echo MOVED: Old documentation
)

echo.
if "%1"=="preview" (
    echo =============================================
    echo PREVIEW MODE - No changes made
    echo Run with: organize.bat execute
    echo =============================================
) else if "%1"=="execute" (
    echo =============================================
    echo ORGANIZATION COMPLETE!
    echo =============================================
    echo.
    echo New folder structure:
    echo   - config/          Configuration files
    echo   - docs/guides/     Setup and organization guides
    echo   - docs/user/       User manuals
    echo   - docs/api/        Developer and API docs
    echo   - archive/reports/ QA and test reports
    echo   - archive/logs/    Historical log files
    echo   - archive/docs/    Superseded documentation
    echo   - archive/test_data/ Test and diagnostic data
)

echo.
endlocal
