# Sentinel - Project Structure

## 📁 Root Directory

```
graduationp/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── pyproject.toml         # Python project configuration
├── sentinel.spec          # PyInstaller build specification
├── run_as_admin.bat       # Windows admin launcher
├── README.md              # Project overview
├── QUICKSTART.md          # Quick start guide
├── CHANGELOG.md           # Version history
├── CONTRIBUTING.md        # Contribution guidelines
└── LICENSE                # License information
```

## 📦 Application Code (`app/`)

```
app/
├── __init__.py
├── __version__.py         # Version string
├── application.py         # Main Qt application class
│
├── core/                  # Core business logic
│   ├── container.py       # Dependency injection
│   ├── interfaces.py      # Abstract interfaces
│   ├── types.py          # Type definitions
│   ├── errors.py         # Custom exceptions
│   └── startup_orchestrator.py  # Deferred initialization
│
├── infra/                 # Infrastructure implementations
│   ├── system_monitor_psutil.py  # System metrics
│   ├── events_windows.py          # Windows Event Log
│   ├── file_scanner.py           # VirusTotal file scanning
│   ├── url_scanner.py            # VirusTotal URL scanning
│   ├── nmap_cli.py              # Network scanning (Nmap)
│   └── sqlite_repo.py           # SQLite persistence
│
├── ui/                    # Qt/QML bridge layer
│   ├── backend_bridge.py  # Main QML ↔ Python bridge
│   ├── gpu_service.py     # GPU metrics service (QProcess)
│   └── gpu_backend.py     # Legacy GPU backend (deprecated)
│
├── gpu/                   # GPU monitoring subsystem
│   └── telemetry_worker.py  # Subprocess GPU worker
│
├── utils/                 # Utilities
│   ├── admin.py          # Admin privilege checks
│   └── gpu_manager.py    # GPU abstraction layer
│
├── config/                # Configuration
│   └── settings.py       # App settings
│
└── tests/                 # Unit tests
    ├── test_container.py
    ├── test_repos.py
    └── test_services.py
```

## 🎨 QML UI (`qml/`)

```
qml/
├── main.qml              # Root window, navigation, global state
│
├── components/           # Reusable UI components
│   ├── qmldir           # Component registry
│   ├── AppSurface.qml   # Page wrapper
│   ├── Card.qml         # Hover card
│   ├── LiveMetricTile.qml  # Animated metric display
│   ├── Panel.qml        # Content panel
│   ├── PageHeader.qml   # Page title/subtitle
│   ├── SidebarNav.qml   # Navigation sidebar
│   ├── TopStatusBar.qml # Top bar with system info
│   ├── ToastManager.qml # Toast notification system
│   └── ...              # Other components
│
├── pages/                # Application pages
│   ├── EventViewer.qml
│   ├── SystemSnapshot.qml
│   ├── GPUMonitoringNew.qml
│   ├── ScanHistory.qml
│   ├── NetworkScan.qml
│   ├── ScanTool.qml
│   ├── DataLossPrevention.qml
│   ├── Settings.qml
│   │
│   └── snapshot/         # System Snapshot sub-pages
│       ├── OverviewPage.qml
│       ├── OSInfoPage.qml
│       ├── HardwarePage.qml
│       ├── NetworkPage.qml
│       └── SecurityPage.qml
│
├── theme/                # Design system
│   ├── qmldir
│   └── Theme.qml         # Singleton with colors, spacing, typography
│
└── ui/                   # Legacy UI utilities
    ├── qmldir
    └── ThemeManager.qml  # Legacy theme (use theme/Theme.qml instead)
```

## 📜 Scripts (`scripts/`)

```
scripts/
├── run.ps1               # Run application (main launcher)
│
├── build/
│   └── build.ps1         # PyInstaller build script
│
├── dev/
│   ├── lint.ps1          # Ruff linting
│   ├── profile_startup.ps1  # Startup profiling
│   └── commit_changes.ps1   # Git commit helper
│
└── tests/
    ├── test.ps1          # Run pytest
    ├── test_disk_calc.py
    ├── test_disk_snapshot.py
    ├── test_fast_snapshot.py
    ├── profile_snapshot.py
    └── system_detection_test.json
```

## 📚 Documentation (`docs/`)

```
docs/
├── README.md                     # Documentation index
├── USER_MANUAL.md               # End-user guide
├── API_INTEGRATION_GUIDE.md     # VirusTotal/Nmap integration
├── README_BACKEND.md            # Backend architecture
├── README_RELEASE_NOTES.md      # Release notes
├── GPU_SUBPROCESS_README.md     # GPU monitoring architecture
├── GPU_TELEMETRY_SUBPROCESS.md
├── AMD_GPU_MONITORING.md        # AMD GPU support
├── PERFORMANCE.md               # Performance optimization notes
├── QUICK_REFERENCE.md           # Developer quick reference
│
├── development/                  # Development docs
│   └── ...                      # Build guides, commit messages, etc.
│
├── releases/                     # Release documentation
│   └── ...
│
└── archive/                      # Historical documentation
    ├── CHANGELOG_OLD.md
    ├── PHASE1_COMPLETE.md
    ├── PHASE2_COMPLETE.md
    ├── PERFORMANCE_FIX_2025-10-26.md
    └── ...                       # Old status reports, fix summaries
```

## 🔨 Build Artifacts

```
build/                    # PyInstaller build cache
dist/                     # Compiled executables
.venv/                    # Python virtual environment
.pytest_cache/            # Pytest cache
.ruff_cache/             # Ruff linter cache
__pycache__/             # Python bytecode cache
```

## 🎯 Key Design Patterns

### Backend Architecture
- **Dependency Injection**: `app/core/container.py` (DI container)
- **Interface Segregation**: `app/core/interfaces.py` (abstract base classes)
- **Deferred Init**: `app/core/startup_orchestrator.py` (fast startup)

### Frontend Architecture
- **Component-Based UI**: Reusable QML components in `qml/components/`
- **Design System**: Centralized theme tokens in `qml/theme/Theme.qml`
- **Page Navigation**: StackView-based routing in `qml/main.qml`

### GPU Monitoring
- **Subprocess Architecture**: `app/gpu/telemetry_worker.py` runs in separate process
- **QProcess Bridge**: `app/ui/gpu_service.py` manages subprocess communication
- **Circuit Breaker**: Automatic restart on worker failure

### Performance Optimizations
- **Snapshot Caching**: 10s cache for expensive WMI queries
- **Async Operations**: QThreadPool for background tasks
- **Lazy Loading**: Deferred service initialization (300ms after UI)

## 🚀 Usage

### Development
```powershell
# Run application
.\scripts\run.ps1

# Lint code
.\scripts\dev\lint.ps1

# Run tests
.\scripts\tests\test.ps1

# Profile startup
.\scripts\dev\profile_startup.ps1
```

### Production Build
```powershell
.\scripts\build\build.ps1
```

Output: `dist/sentinel.exe`

## 📝 Notes

- **GPU Metrics**: System snapshot does NOT include GPU (uses GPUService instead)
- **Disk Detection**: Uses `disks.length` not `Array.isArray()` (QVariantList compat)
- **Update Intervals**:
  - Backend snapshot: 3 seconds
  - GPU service: 2 seconds (configurable)
  - Security cache: 30 seconds
  - GPU cache: 10 seconds

## 🔗 Quick Links

- [Quick Start](QUICKSTART.md)
- [User Manual](docs/USER_MANUAL.md)
- [API Integration Guide](docs/API_INTEGRATION_GUIDE.md)
- [Performance Notes](docs/PERFORMANCE.md)
- [Contributing](CONTRIBUTING.md)
