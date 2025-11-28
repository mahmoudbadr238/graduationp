# 📁 Sentinel Project - Folder Structure Guide

## Complete Project Organization

This document describes the new, optimized folder structure for the Sentinel endpoint security suite project.

---

## 🏗️ Project Root Structure

```
sentinel/
├── app/                         # 🐍 Python backend (core logic)
├── qml/                         # 🎨 Qt/QML frontend (UI)
├── scripts/                     # 🔧 Automation & build scripts
├── tools/                       # 🛠️ Development utilities
├── docs/                        # 📚 Main documentation
├── config/                      # ⚙️ Configuration files
├── build_artifacts/             # 🏗️ Build outputs
├── archive/                     # 📦 Historical/superseded files
├── main.py                      # 🎬 Application entry point
├── requirements.txt             # 📋 Python dependencies
├── README.md                    # 📖 Project overview
└── .gitignore                   # 🚫 Git ignore patterns
```

---

## 📁 Detailed Folder Breakdown

### 1. `app/` - Python Backend
**Purpose**: Core business logic, services, and system integration  
**Visibility**: Internal (backend only)

```
app/
├── __main__.py                  # Alternative entry point
├── __version__.py               # Version information
├── application.py               # Qt app initialization
├── config/                      # Configuration module
│   ├── __init__.py
│   └── settings.py              # App settings/preferences
├── core/                        # Core services & infrastructure
│   ├── __init__.py
│   ├── config.py                # Configuration management
│   ├── container.py             # Dependency injection
│   ├── errors.py                # Custom exceptions
│   ├── interfaces.py            # Service interfaces
│   ├── logging_setup.py         # Logging configuration
│   ├── result_cache.py          # Caching layer
│   ├── startup_orchestrator.py  # Startup sequence
│   ├── types.py                 # Type definitions
│   └── workers.py               # Background workers
├── gpu/                         # GPU monitoring
│   ├── __init__.py
│   └── telemetry_worker.py      # GPU telemetry collection
├── infra/                       # System infrastructure
│   ├── __init__.py
│   ├── events_windows.py        # Windows event monitoring
│   ├── file_scanner.py          # File system scanning
│   ├── integrations.py          # Third-party integrations
│   ├── nmap_cli.py              # Network scanning
│   ├── privileges.py            # Privilege management
│   ├── sqlite_repo.py           # SQLite repository
│   ├── system_monitor_psutil.py # System metrics
│   ├── url_scanner.py           # URL analysis
│   └── vt_client.py             # VirusTotal API client
├── ui/                          # UI bridges/models
│   └── [model files]
├── utils/                       # Utility functions
│   └── [helper modules]
└── tests/                       # Unit tests
    ├── __init__.py
    ├── test_container.py
    ├── test_core.py
    ├── test_repos.py
    └── [other tests]
```

### 2. `qml/` - Qt/QML Frontend
**Purpose**: User interface, visual components, and interactions  
**Visibility**: Frontend (UI layer)

```
qml/
├── main.qml                     # Root window & page router
├── pages/                       # Main application pages
│   ├── qmldir                   # QML module definition
│   ├── EventViewer.qml          # Event viewing page
│   ├── SystemSnapshot.qml       # System snapshot page
│   ├── GPUMonitoring.qml        # GPU monitoring
│   ├── ScanHistory.qml          # Scan history
│   ├── NetworkScan.qml          # Network scanning
│   ├── ScanTool.qml             # File scanning tool
│   ├── DataLossPrevention.qml   # DLP page
│   ├── Settings.qml             # Settings page
│   └── snapshot/                # System snapshot sub-pages
│       ├── OverviewPage.qml
│       ├── HardwarePage.qml
│       └── NetworkPage.qml
├── components/                  # Reusable UI components
│   ├── qmldir
│   ├── Theme.qml                # Global theme singleton
│   ├── AppSurface.qml           # Page wrapper
│   ├── Card.qml                 # Card container
│   ├── Panel.qml                # Panel component
│   ├── SectionHeader.qml        # Section titles
│   ├── SidebarNav.qml           # Sidebar navigation
│   ├── Button.qml               # Custom button
│   └── [other components]
├── theme/                       # Theming system
│   ├── qmldir
│   ├── Colors.qml               # Color palette
│   ├── Typography.qml           # Font styles
│   ├── Spacing.qml              # Spacing constants
│   └── Icons.qml                # Icon definitions
├── ui/                          # UI utilities & helpers
│   └── [UI support files]
└── ux/                          # UX patterns & animations
    └── [animation/transition files]
```

### 3. `scripts/` - Automation & Build
**Purpose**: Project automation, building, and deployment  
**Visibility**: Development tools

```
scripts/
├── run.ps1                      # Quick start script
├── build/                       # Build scripts
│   ├── build_exe.ps1            # Windows executable builder
│   ├── build_installer.ps1      # Installer builder
│   └── [other builders]
└── dev/                         # Development scripts
    ├── dev_setup.ps1            # Development environment setup
    ├── lint_check.ps1           # Code linting
    └── [other dev scripts]
```

### 4. `tools/` - Development Utilities
**Purpose**: Helper tools for development and testing  
**Visibility**: Development only

```
tools/
├── auto_fix_qml.py              # QML auto-fixer
├── gui_probe.py                 # GUI debugging tool
├── qml_lint.py                  # QML linter
└── [other utilities]
```

### 5. `docs/` - Documentation
**Purpose**: Complete documentation hub  
**Visibility**: Public (users + developers)

```
docs/
├── README.md                    # Documentation index
├── QUICKSTART.md                # Quick start guide
├── SECURITY.md                  # Security policies
├── PRIVACY.md                   # Privacy information
├── CHANGELOG.md                 # Release notes
├── CONTRIBUTING.md              # Contribution guidelines
├── LICENSE                      # License file
├── user/                        # User-facing docs
│   ├── USER_MANUAL.md           # User manual
│   ├── QUICK_REFERENCE.md       # Quick reference
│   └── [other user guides]
├── api/                         # Developer/API docs
│   ├── README_BACKEND.md        # Backend overview
│   ├── API_INTEGRATION_GUIDE.md # API documentation
│   ├── PERFORMANCE.md           # Performance guide
│   ├── AMD_GPU_MONITORING.md    # GPU documentation
│   ├── GPU_SUBPROCESS_README.md # GPU subprocess
│   ├── GPU_TELEMETRY_SUBPROCESS.md
│   └── [other API docs]
├── guides/                      # Setup & organization guides
│   ├── FILE_ORGANIZATION_GUIDE.md # This project structure
│   ├── CLEANUP_INSTRUCTIONS.md  # Cleanup procedures
│   ├── README_CLEANUP.md        # Cleanup reference
│   └── ORGANIZATION_COMPLETE.md # Organization checklist
├── archive/                     # Old documentation
│   ├── COMPREHENSIVE_DIFFS.md
│   ├── DELIVERY_SUMMARY.md
│   ├── HOTFIX_SQLITEREPO.md
│   ├── ISSUE_P0_GPU_PACKAGE_VALIDATION.md
│   ├── ISSUE_P1_HIGH_PRIORITY_FIXES.md
│   ├── PROJECT_STRUCTURE.md
│   ├── RESPONSIVE_UI_CHANGES.md
│   ├── QML_FIXES_SUMMARY.md
│   ├── FINAL_FIX_SUMMARY.md
│   └── [other archived docs]
└── development/                 # Technical references
    └── [development docs]
```

### 6. `config/` - Configuration Files
**Purpose**: Project configuration and build settings  
**Visibility**: Project level

```
config/
├── pyproject.toml               # Python project config
├── pytest.ini                   # Test configuration
├── sentinel.spec                # PyInstaller spec file
├── .env.example                 # Environment template
├── .pre-commit-config.yaml      # Pre-commit hooks
└── [other config files]
```

### 7. `build_artifacts/` - Build Outputs
**Purpose**: Compiled outputs, distributions, and build artifacts  
**Visibility**: Generated (not committed)

```
build_artifacts/
├── sentinel/                    # Build directory
│   └── [compiled files]
├── dist/                        # Distribution files
│   ├── sentinel.exe             # Windows executable
│   ├── sentinel-installer.msi   # Windows installer
│   └── [other distributions]
└── artifacts/                   # Build artifacts
    └── [gui resources]
```

### 8. `archive/` - Historical Files
**Purpose**: Old, superseded, or historical project files  
**Visibility**: Historical reference only

```
archive/
├── reports/                     # QA & test reports
│   ├── APP_TESTING_REPORT.md
│   ├── QA_REVIEW_SUMMARY.md
│   ├── QA_REVIEW_DOCUMENTATION_INDEX.md
│   ├── QA_REVIEW_EXECUTIVE_SUMMARY.txt
│   ├── QA_PRODUCTION_HARDENING_REVIEW.md
│   ├── GUI_REVIEW_COMPLETE.md
│   ├── GUI_RESPONSIVENESS_REVIEW.md
│   ├── RELEASE_CHECKLIST.md
│   ├── RELEASE_DECISION.md
│   └── RELEASE_READY.md
├── logs/                        # Historical logs
│   ├── app_console.log
│   ├── app_errors.log
│   ├── app_final.txt
│   ├── app_final_err.txt
│   └── output.txt
├── test_data/                   # Test and diagnostic data
│   ├── diags_test.json
│   └── bandit_results.json
└── docs/                        # Superseded documentation
    ├── COMPREHENSIVE_DIFFS.md
    ├── DELIVERY_SUMMARY.md
    ├── HOTFIX_SQLITEREPO.md
    ├── ISSUE_P0_GPU_PACKAGE_VALIDATION.md
    ├── ISSUE_P1_HIGH_PRIORITY_FIXES.md
    ├── PROJECT_STRUCTURE.md
    ├── RESPONSIVE_UI_CHANGES.md
    ├── QML_FIXES_SUMMARY.md
    └── FINAL_FIX_SUMMARY.md
```

---

## 📋 File Categories & Organization

### Root Level (Keep Minimal)

**✅ Required at Root**:
- `main.py` - Entry point
- `README.md` - Project overview
- `requirements.txt` - Dependencies
- `.gitignore` - Git configuration
- `LICENSE` - License file

**📁 Organized Away**:
- Configuration → `config/`
- Documentation → `docs/`
- Reports/logs → `archive/`
- Build outputs → `build_artifacts/`

### Documentation Categorization

| Category | Location | Audience | Purpose |
|----------|----------|----------|---------|
| **User Guides** | `docs/user/` | End users | How to use the application |
| **API/Developer** | `docs/api/` | Developers | Technical implementation details |
| **Setup Guides** | `docs/guides/` | Developers | Project setup and organization |
| **Core Docs** | `docs/` | Everyone | README, licenses, policies |
| **Historical** | `archive/` | Reference | Old versions, superseded docs |

### Backend Module Organization

| Module | Location | Responsibility |
|--------|----------|-----------------|
| **Core** | `app/core/` | DI, logging, startup, caching |
| **Infrastructure** | `app/infra/` | System integration, scanning, APIs |
| **GPU** | `app/gpu/` | GPU telemetry & monitoring |
| **UI** | `app/ui/` | UI bridges & view models |
| **Utilities** | `app/utils/` | Helper functions |
| **Tests** | `app/tests/` | Unit test suite |

### Frontend Component Organization

| Category | Location | Purpose |
|----------|----------|---------|
| **Pages** | `qml/pages/` | Main application pages (routable) |
| **Components** | `qml/components/` | Reusable UI building blocks |
| **Theme** | `qml/theme/` | Centralized styling & design tokens |
| **UI Support** | `qml/ui/` | UI utility functions |
| **UX Patterns** | `qml/ux/` | Animation & transition patterns |

---

## 🚀 Migration Checklist

When moving to this structure, ensure:

- [ ] All imports updated to reflect new paths
- [ ] Config files moved to `config/` folder
- [ ] Documentation reorganized by category
- [ ] Historical files archived in `archive/`
- [ ] Build outputs directed to `build_artifacts/`
- [ ] `.gitignore` updated for new structure
- [ ] CI/CD configs updated if needed
- [ ] README.md updated with new paths
- [ ] Developer guide updated

---

## 📌 Key Principles

1. **Clear Separation** - Backend (app/), Frontend (qml/), Tools (scripts/, tools/)
2. **Hierarchical** - Sub-folders organize by function, not just type
3. **Accessible** - Core docs and entry point at root, easy to find
4. **Scalable** - Easy to add new modules/pages without clutter
5. **Maintainable** - Related files grouped logically
6. **Documented** - Each folder has a clear purpose
7. **Version Control** - Generated files don't clutter git history

---

## 🔧 Using the Organization Script

Run the organization script to automatically move files:

```powershell
# Preview proposed changes
.\organize.ps1 -Preview

# Execute the organization
.\organize.ps1 -Execute
```

The script will:
- ✅ Create necessary directories
- ✅ Move files to appropriate folders
- ✅ Preserve file history
- ✅ Report success/errors
- ✅ Provide statistics

---

## 📖 Next Steps

1. **Review** this structure carefully
2. **Run** `organize.ps1 -Preview` to see proposed changes
3. **Verify** the preview looks correct
4. **Execute** `organize.ps1 -Execute` to organize files
5. **Test** the application runs correctly
6. **Commit** changes to git with a message: "refactor: reorganize project structure"

---

*Last Updated: 2024*  
*Sentinel Endpoint Security Suite*
