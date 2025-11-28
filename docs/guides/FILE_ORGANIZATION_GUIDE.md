# Sentinel Project File Organization Guide

## Directory Structure Overview

### Root Level - Production Files (Keep in Root)
```
d:\graduationp\
├── main.py                          # Application entry point
├── requirements.txt                 # Python dependencies
├── pyproject.toml                   # Project configuration
├── pytest.ini                       # Test configuration
├── sentinel.spec                    # PyInstaller specification
├── run_as_admin.bat                 # Windows batch script for admin mode
├── LICENSE                          # Project license
├── README.md                        # Main project documentation
├── SECURITY.md                      # Security policies
├── PRIVACY.md                       # Privacy information
└── QUICKSTART.md                    # Quick start guide
```

### app/ - Python Backend (Production)
```
app/
├── __main__.py                      # Package entry point
├── __version__.py                   # Version information
├── application.py                   # Qt application initialization
├── config/                          # Configuration management
│   ├── __init__.py
│   └── settings.py
├── core/                            # Core application logic
│   ├── __init__.py
│   ├── config.py
│   ├── container.py                 # Dependency injection
│   ├── errors.py
│   ├── interfaces.py
│   ├── logging_setup.py
│   ├── result_cache.py
│   ├── startup_orchestrator.py
│   ├── types.py
│   └── workers.py
├── gpu/                             # GPU telemetry
│   ├── __init__.py
│   └── telemetry_worker.py
├── infra/                           # Infrastructure/system integration
│   ├── __init__.py
│   ├── events_windows.py            # Windows event log integration
│   ├── file_scanner.py
│   ├── integrations.py
│   ├── nmap_cli.py
│   ├── privileges.py
│   ├── sqlite_repo.py
│   ├── system_monitor_psutil.py
│   ├── url_scanner.py
│   └── vt_client.py
├── ui/                              # UI/QML bridge
│   ├── __init__.py
│   ├── backend_bridge.py
│   ├── gpu_backend.py
│   └── gpu_service.py
├── utils/                           # Utility functions
│   ├── __init__.py
│   ├── admin.py
│   └── ...
└── tests/                           # Unit tests
    ├── __init__.py
    ├── test_container.py
    ├── test_core.py
    ├── test_repos.py
    ├── test_services.py
    └── test_smoke.py
```

### qml/ - Frontend UI (Production)
```
qml/
├── main.qml                         # Main window
├── components/                      # Reusable UI components
│   ├── qmldir
│   ├── AppSurface.qml
│   ├── AnimatedCard.qml
│   ├── Card.qml
│   ├── Panel.qml
│   ├── Button components...
│   └── ... (15+ shared components)
├── pages/                           # Application pages/screens
│   ├── qmldir
│   ├── EventViewer.qml
│   ├── SystemSnapshot.qml
│   ├── GPUMonitoringNew.qml
│   ├── ScanHistory.qml
│   ├── NetworkScan.qml
│   ├── ScanTool.qml
│   ├── DataLossPrevention.qml
│   ├── Settings.qml
│   └── snapshot/
│       ├── OverviewPage.qml
│       ├── HardwarePage.qml
│       ├── NetworkPage.qml
│       ├── OSInfoPage.qml
│       └── SecurityPage.qml
├── theme/                           # Theming system
│   ├── qmldir
│   └── Theme.qml                    # Global theme (colors, spacing, typography)
└── ... (ux/, ui/ folders with additional components)
```

### Documentation - Organized by Type

#### Active Documentation (Keep in Root)
- **README.md** - Project overview
- **QUICKSTART.md** - Getting started guide
- **SECURITY.md** - Security policies
- **PRIVACY.md** - Privacy information
- **CHANGELOG.md** - Version history
- **LICENSE** - Project license

#### Developer Documentation (Keep in docs/)
```
docs/
├── README.md                        # Documentation index
├── USER_MANUAL.md                   # End-user documentation
├── README_BACKEND.md                # Backend architecture
├── API_INTEGRATION_GUIDE.md         # API integration documentation
├── PERFORMANCE.md                   # Performance optimization guide
├── QUICK_REFERENCE.md               # Quick reference for developers
├── AMD_GPU_MONITORING.md            # AMD GPU-specific documentation
├── GPU_SUBPROCESS_README.md         # GPU subprocess architecture
├── GPU_TELEMETRY_SUBPROCESS.md      # GPU telemetry details
├── README_RELEASE_NOTES.md          # Release notes template
├── releases/                        # Release archives
│   └── v1.0.0/                      # Previous versions
└── archive/                         # Older documentation
└── development/                     # Development guides
```

#### Archived/Cleanup Files (Move to _cleanup_archive/)
```
_cleanup_archive/
├── logs/                            # Log files
│   ├── app_console.log
│   ├── app_errors.log
│   └── app_final_err.txt
├── reports/                         # QA/Testing reports
│   ├── APP_TESTING_REPORT.md
│   ├── QA_REVIEW_SUMMARY.md
│   ├── QA_REVIEW_DOCUMENTATION_INDEX.md
│   ├── QA_REVIEW_EXECUTIVE_SUMMARY.txt
│   ├── QA_PRODUCTION_HARDENING_REVIEW.md
│   ├── GUI_REVIEW_COMPLETE.md
│   ├── GUI_RESPONSIVENESS_REVIEW.md
│   ├── RELEASE_CHECKLIST.md
│   ├── RELEASE_DECISION.md
│   ├── RELEASE_READY.md
│   └── report.json
├── test_data/                       # Test data and diagnostics
│   ├── diags_test.json
│   ├── bandit_results.json
│   ├── system_detection_test.json
│   └── output.txt
└── old_docs/                        # Superseded documentation
    ├── COMPREHENSIVE_DIFFS.md
    ├── CLEANUP_SUMMARY.md
    ├── DELIVERY_SUMMARY.md
    ├── HOTFIX_SQLITEREPO.md
    ├── ISSUE_P0_GPU_PACKAGE_VALIDATION.md
    ├── ISSUE_P1_HIGH_PRIORITY_FIXES.md
    ├── PROJECT_STRUCTURE.md
    ├── RESPONSIVE_UI_CHANGES.md
    ├── QML_FIXES_SUMMARY.md
    ├── FINAL_FIX_SUMMARY.md
    └── app_final.txt
```

## Files to Clean Up

### Log Files (Safe to Delete)
- `app_console.log`
- `app_errors.log`
- `app_final.txt`
- `app_final_err.txt`
- `output.txt`

### Test/Diagnostic Data (Archive or Delete)
- `diags_test.json`
- `bandit_results.json`

### Build Artifacts (Can be Regenerated)
- `dist/` - Distribution builds
- `build/` - Build artifacts
- `.pytest_cache/` - Pytest cache
- `.ruff_cache/` - Ruff cache
- `__pycache__/` - Python cache directories

### QA/Testing Reports (Archive - Historical Value)
- `APP_TESTING_REPORT.md`
- `QA_REVIEW_*.md`
- `GUI_REVIEW_*.md`
- `RELEASE_*.md`

## Recommended Cleanup Steps

### Step 1: Archive Historical Documentation
Move the following to `_cleanup_archive/old_docs/`:
```
COMPREHENSIVE_DIFFS.md
CLEANUP_SUMMARY.md
DELIVERY_SUMMARY.md
HOTFIX_SQLITEREPO.md
ISSUE_P0_GPU_PACKAGE_VALIDATION.md
ISSUE_P1_HIGH_PRIORITY_FIXES.md
PROJECT_STRUCTURE.md
RESPONSIVE_UI_CHANGES.md
QML_FIXES_SUMMARY.md
FINAL_FIX_SUMMARY.md
```

### Step 2: Archive QA/Testing Reports
Move to `_cleanup_archive/reports/`:
```
APP_TESTING_REPORT.md
QA_REVIEW_SUMMARY.md
QA_REVIEW_DOCUMENTATION_INDEX.md
QA_REVIEW_EXECUTIVE_SUMMARY.txt
QA_PRODUCTION_HARDENING_REVIEW.md
GUI_REVIEW_COMPLETE.md
GUI_RESPONSIVENESS_REVIEW.md
RELEASE_CHECKLIST.md
RELEASE_DECISION.md
RELEASE_READY.md
```

### Step 3: Archive Logs and Test Data
Move to `_cleanup_archive/logs/` and `_cleanup_archive/test_data/`:
```
app_console.log → logs/
app_errors.log → logs/
app_final.txt → logs/
app_final_err.txt → logs/
output.txt → test_data/
diags_test.json → test_data/
bandit_results.json → test_data/
```

### Step 4: Clean Build Artifacts
These are auto-generated and can be deleted safely:
```
dist/
build/
.pytest_cache/
.ruff_cache/
__pycache__/
.venv/__pycache__/
```

### Step 5: Organize .github/
The `.github/copilot-instructions.md` is kept for reference.

## Final Root Directory Structure (Clean)

```
graduationp/
├── app/                             # Backend source code
├── qml/                             # Frontend QML code
├── docs/                            # Official documentation
├── scripts/                         # Build and development scripts
├── tests/                           # Integration tests
├── tools/                           # Development tools
├── _cleanup_archive/                # Archived files (optional)
├── .github/                         # GitHub configuration
├── .venv/                           # Virtual environment
├── .git/                            # Git repository
├── main.py                          # Entry point
├── pyproject.toml                   # Project config
├── requirements.txt                 # Dependencies
├── sentinel.spec                    # PyInstaller spec
├── README.md                        # Main documentation
├── QUICKSTART.md                    # Getting started
├── SECURITY.md                      # Security info
├── PRIVACY.md                       # Privacy info
├── CHANGELOG.md                     # Version history
└── LICENSE                          # Project license
```

## Git Configuration

Add to `.gitignore` (already configured):
```
__pycache__/
.pytest_cache/
.ruff_cache/
dist/
build/
*.egg-info/
.venv/
```

The `_cleanup_archive/` directory can either be:
1. **Kept locally** for reference (not committed to git)
2. **Committed to git** for historical tracking (mark in .gitignore to skip)
3. **Uploaded to GitHub Releases** with version tags

## Storage Estimate

- **Active Code**: ~15 MB
- **Documentation**: ~5 MB
- **Archive**: ~10 MB (optional)
- **Total with Archive**: ~30 MB

---

**This organization improves**:
✅ Project clarity and maintainability
✅ Onboarding for new developers
✅ CI/CD pipeline efficiency
✅ Git repository size management
✅ Production deployment readiness

