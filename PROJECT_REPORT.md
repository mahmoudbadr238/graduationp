# Sentinel — Comprehensive Project Report

> **Project Type:** Graduation / Advanced Engineering Project  
> **Report Date:** 2026-05-13  
> **Version:** 1.0.0  
> **License:** MIT

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement & Motivation](#2-problem-statement--motivation)
3. [Tech Stack](#3-tech-stack)
4. [High-Level Architecture](#4-high-level-architecture)
5. [Project Directory Structure](#5-project-directory-structure)
6. [Backend System — Deep Dive](#6-backend-system--deep-dive)
   - 6.1 [Application Startup & Entry Point](#61-application-startup--entry-point)
   - 6.2 [Dependency Injection Container](#62-dependency-injection-container)
   - 6.3 [Core Services](#63-core-services)
   - 6.4 [Platform Abstraction Layer](#64-platform-abstraction-layer)
   - 6.5 [Infrastructure Layer](#65-infrastructure-layer)
   - 6.6 [API / Bridge Layer](#66-api--bridge-layer)
7. [Security Engines — Feature Breakdown](#7-security-engines--feature-breakdown)
   - 7.1 [Real-Time Protection (RTP)](#71-real-time-protection-rtp)
   - 7.2 [Multi-Engine Scan Center (11-Stage Pipeline)](#72-multi-engine-scan-center-11-stage-pipeline)
   - 7.3 [Dynamic Sandbox Lab](#73-dynamic-sandbox-lab)
   - 7.4 [AI Security Assistant](#74-ai-security-assistant)
   - 7.5 [GPU & Hardware Telemetry](#75-gpu--hardware-telemetry)
   - 7.6 [Event Viewer & AI Event Explainer](#76-event-viewer--ai-event-explainer)
   - 7.7 [Network Scanner](#77-network-scanner)
   - 7.8 [File Function: Secure Delete & Forensic Carving](#78-file-function-secure-delete--forensic-carving)
   - 7.9 [Security Posture Assessment (System Snapshot)](#79-security-posture-assessment-system-snapshot)
   - 7.10 [History & Quarantine Management](#710-history--quarantine-management)
   - 7.11 [URL Scanner & Detonator](#711-url-scanner--detonator)
8. [Frontend — QML User Interface](#8-frontend--qml-user-interface)
   - 8.1 [Layout & Navigation](#81-layout--navigation)
   - 8.2 [Pages Overview](#82-pages-overview)
   - 8.3 [Theme System](#83-theme-system)
9. [Payload: Sandbox Agent (In-VM)](#9-payload-sandbox-agent-in-vm)
10. [Data Persistence — SQLite](#10-data-persistence--sqlite)
11. [Cross-Platform Support Matrix](#11-cross-platform-support-matrix)
12. [Graceful Degradation Model](#12-graceful-degradation-model)
13. [Testing & Quality Assurance](#13-testing--quality-assurance)
14. [Build & Packaging](#14-build--packaging)
15. [Configuration & Environment Variables](#15-configuration--environment-variables)
16. [Security Design Decisions](#16-security-design-decisions)
17. [Limitations & Known Boundaries](#17-limitations--known-boundaries)
18. [CI/CD Pipeline](#18-cicd-pipeline)
19. [BackendBridge — Complete Signal & Slot Reference](#19-backendbridge--complete-signal--slot-reference)
20. [SettingsService — Complete Property & Slot Reference](#20-settingsservice--complete-property--slot-reference)
21. [QML Pages — Internal Wiring Details](#21-qml-pages--internal-wiring-details)
22. [Release History (CHANGELOG)](#22-release-history-changelog)

---

## 1. Executive Summary

**Sentinel** is an advanced, cross-platform Endpoint Detection & Response (EDR) suite built as a graduation project in Python with a PySide6/QML graphical interface. It integrates more than a dozen discrete security modules into a single unified application — covering real-time process monitoring, multi-engine file analysis, live malware detonation in VMware, GPU hardware telemetry, AI-assisted threat explanation, network scanning, forensic file carving, secure deletion, and security posture assessment.

The application runs natively on both **Windows** and **Linux**, using deep, platform-specific OS integrations (WMI on Windows, sysfs/journalctl on Linux) rather than generic cross-platform wrappers. Heavy workloads are isolated in subprocesses with IPC to guarantee a fluid, never-frozen UI. AI assistance is powered by the **Groq Cloud API** (Llama-3.3-70b-versatile) and is carefully designed so that AI hallucinations can never trigger destructive enforcement actions — a deterministic scoring engine holds the final authority.

---

## 2. Problem Statement & Motivation

**The Problem:**

Existing endpoint security tooling suffers from two extreme failure modes:
1. **Commercial black-boxes** (e.g., corporate EDR suites) that hide their telemetry from analysts and are not extensible.
2. **Fragmented CLI tools** (Nmap, ClamAV, `nvidia-smi`, Event Viewer, `journalctl`) that each operate in isolation with no shared investigative context.

Cross-platform tools often use "lazy OS wrappers" that provide the lowest common denominator of platform intelligence.

**The Solution:**

Sentinel consolidates all security operations into a single pane of glass. It:
- Uses **platform-native integrations** (WMI, `sysfs`, `journalctl`, `Win32_Process`) instead of generic wrappers.
- **Never fabricates data** — missing capabilities are reported as `Unavailable`, `Permission Required`, or `Unsupported` with specific reasons.
- Isolates heavy tasks in subprocesses to keep the UI fully responsive even during 100% CPU scans.
- Combines **deterministic scoring** with **AI assistance** so analysts get human-readable threat explanations without false-positive enforcement.

---

## 3. Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **GUI Framework** | PySide6 (Qt 6.6+), QML | Declarative UI with GPU-accelerated rendering |
| **Backend Language** | Python 3.11+ | Core application logic |
| **AI / LLM** | Groq SDK (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`) | Threat explanation, NGAV, chatbot |
| **System Monitoring** | `psutil` 5.9+ | Cross-platform CPU/RAM/disk/network |
| **Windows Integration** | `pywin32`, `wmi`, `pythoncom` | Event logs, WMI process watching, Authenticode |
| **GPU Telemetry** | `nvidia-ml-py` (NVML), `pyadl` (AMD), direct `sysfs` reads | Hardware monitoring |
| **File Analysis** | `pefile`, `hashlib`, ClamAV adapter | PE parsing, SHA-256/MD5, signature scanning |
| **Networking** | Nmap CLI (`nmap_cli.py`), `requests`, `aiohttp` | Host discovery, vulnerability probing |
| **Database** | SQLite3 (WAL mode) | Scan history, events, quarantine records |
| **Sandbox** | VMware Workstation (`vmrun`), `imageio`+`ffmpeg` | Live malware detonation, video capture |
| **Build / Packaging** | PyInstaller 6.0+ | Single-binary Windows executable |
| **Testing** | `pytest`, `pytest-qt` | Unit and integration regression suite |
| **Linting / Quality** | `ruff`, `mypy`, `bandit` | Static analysis, type checking, security linting |

---

## 4. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       QML Frontend (PySide6)                 │
│  HomePage │ ScanCenter │ RTP │ GPU │ Snapshot │ Assistant… │
└─────────────────────┬────────────────────────────────────────┘
                       │  Qt Signals / Slots (thread-safe)
┌─────────────────────▼────────────────────────────────────────┐
│                  BackendBridge / API Layer                    │
│  BackendBridge │ GPUService │ SnapshotService │ RTPBridge… │
└──────┬──────────────┬──────────────┬─────────────────────────┘
       │ DI Container │              │ Subprocess IPC
┌──────▼──────┐  ┌────▼────────┐  ┌─▼────────────────────────┐
│  Core Svcs  │  │  Engines    │  │  Isolated Subprocesses   │
│  config     │  │  scanning   │  │  GPU Worker (JSON IPC)   │
│  logging    │  │  ai         │  │  VMware Detonation       │
│  container  │  │  rtp        │  │  Nmap Scanner            │
│  startup    │  │  sandbox    │  │  URL Detonator           │
└──────┬──────┘  │  history    │  └──────────────────────────┘
       │         │  filefunction│
┌──────▼──────┐  └─────────────┘
│   Infra     │
│  sqlite_repo│
│  nmap_cli   │
│  events_*   │
│  file_scanner│
└─────────────┘
```

**Key design principles:**
- The **QML UI never blocks** — all I/O and heavy computation happen in `QThread` workers or isolated subprocesses.
- The `BackendBridge` is the single gateway between QML and Python: QML calls `@Slot()` methods, Python updates QML by emitting `Signal()`.
- A **custom Dependency Injection container** (`core/container.py`) injects the correct platform implementation at startup.
- Every subprocess communicates via **newline-delimited JSON** over stdout (for GPU) or via file exchange (for Sandbox).

---

## 5. Project Directory Structure

```
graduationp/
├── main.py                        # Entry point: delegates to backend.entrypoint
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # Ruff/mypy/bandit configuration
├── .env / .env.example            # GROQ_API_KEY and optional settings
│
├── backend/
│   ├── __version__.py             # App version string (1.0.0)
│   ├── application.py             # DesktopSecurityApplication class (startup orchestration)
│   ├── entrypoint.py              # CLI mode handler + GUI launcher
│   ├── runtime.py                 # Bundle/app root path resolution
│   │
│   ├── api/                       # QML-to-Python bridge classes (QObject / @Slot / Signal)
│   │   ├── backend_bridge.py      # Main BackendBridge (scans, events, network)
│   │   ├── gpu_service.py         # GPUServiceBridge (subprocess IPC manager)
│   │   ├── gpu_backend.py         # GPU data model exposed to QML
│   │   ├── settings_service.py    # SettingsService (QSettings persistence)
│   │   ├── notification_service.py# In-app notification queue
│   │   ├── notification_manager.py# Unified QML + tray toast dispatcher
│   │   ├── security_controller.py # Windows: Defender/UAC/Firewall toggle bridge
│   │   ├── system_snapshot_service.py # Windows: live system metrics
│   │   └── sandbox_preview_provider.py # Live VMware screenshot stream provider
│   │
│   ├── core/                      # Framework infrastructure
│   │   ├── container.py           # Dependency injection container + configure()
│   │   ├── config.py              # Application configuration (QSettings wrapper)
│   │   ├── interfaces.py          # Abstract interfaces (IFileScanner, IEventReader…)
│   │   ├── types.py               # Shared data types (ScanRecord, EventItem…)
│   │   ├── logging_setup.py       # Rotating file logger + crash handler
│   │   ├── perf_monitor.py        # Lightweight memory/CPU performance logger
│   │   ├── realtime_protection.py # RTP bridge + worker (WMI / psutil polling)
│   │   ├── resource_monitor.py    # System resource threshold alerting
│   │   ├── result_cache.py        # Thread-safe in-memory result cache
│   │   ├── startup_orchestrator.py# Deferred initialization scheduler (QTimer)
│   │   └── workers.py             # Generic QThreadPool task runner
│   │
│   ├── engines/                   # Security feature modules
│   │   ├── ai/                    # AI-powered analysis
│   │   │   ├── security_chatbot_v4.py   # Groq chatbot bridge (tool-calling)
│   │   │   ├── event_explainer_v5.py    # Event log AI translator
│   │   │   ├── event_summarizer.py      # Batch event summarizer
│   │   │   ├── groq_smart_assistant.py  # Smart assistant orchestrator
│   │   │   ├── event_rules_engine.py    # Deterministic event rule matching
│   │   │   ├── report_explainer.py      # Scan report AI narrator
│   │   │   ├── url_explainer.py         # URL scan AI explainer
│   │   │   ├── event_id_knowledge.py    # Windows Event ID knowledge base
│   │   │   ├── providers/               # LLM provider abstraction
│   │   │   │   ├── base.py              # BaseProvider interface
│   │   │   │   └── groq.py              # Groq cloud provider implementation
│   │   │   └── knowledge/
│   │   │       └── soc_correlation.py   # SOC event correlation rules
│   │   │
│   │   ├── scanning/              # File & URL scanning pipeline
│   │   │   ├── static_scanner.py        # Main StaticScanner (11-stage orchestrator)
│   │   │   ├── static_scan.py           # PE analysis, hashing, string extraction
│   │   │   ├── scanner_engine.py        # Scan engine coordinator
│   │   │   ├── decision.py              # Deterministic scoring & verdict builder
│   │   │   ├── scoring.py               # Score aggregation rules
│   │   │   ├── clamav_adapter.py        # ClamAV integration (socket + CLI)
│   │   │   ├── quarantine_manager.py    # Quarantine vault operations
│   │   │   ├── report_writer.py         # JSON scan report serializer
│   │   │   ├── report_schema.py         # Scan result data models
│   │   │   ├── url_scanner.py           # URL threat scanner
│   │   │   ├── url_multi_engine.py      # Multi-engine URL checking
│   │   │   ├── url_scanner_engine.py    # URL engine coordinator
│   │   │   ├── url_external_apis.py     # External URL reputation APIs
│   │   │   ├── url_scoring.py           # URL threat scoring
│   │   │   ├── url_checker.py           # URL safety checker
│   │   │   ├── installer_autopilot.py   # Sandbox auto-click for installers
│   │   │   ├── sandbox_session.py       # Sandbox session lifecycle
│   │   │   └── integrated_sandbox.py    # Scan + sandbox integration
│   │   │
│   │   ├── scancenter/            # ScanCenter orchestrator (QThread)
│   │   │   ├── scanner_orchestrator.py  # 6-phase scan pipeline (QThread)
│   │   │   ├── groq_explainer.py        # Groq AI explanation for scan results
│   │   │   ├── report_schema.py         # V3Report schema (FileInfo, Verdict, etc.)
│   │   │   ├── history_repo.py          # Scan history SQLite repository
│   │   │   ├── controller.py            # Scan controller bridge
│   │   │   └── export.py                # Report export (PDF/JSON)
│   │   │
│   │   ├── sandbox_vmware/        # VMware Workstation sandbox integration
│   │   │   ├── sandbox_controller.py    # Main sandbox controller
│   │   │   ├── vmrun_client.py          # vmrun CLI wrapper
│   │   │   ├── config.py                # Sandbox configuration (VM path, snapshot)
│   │   │   ├── window_embedder.py       # Win32 SetParent VM window embedding
│   │   │   ├── preview_stream.py        # Live screenshot capture & streaming
│   │   │   ├── report_parser.py         # Guest behavior report parser
│   │   │   └── guest_scripts/
│   │   │       └── detonate.py          # Script injected into guest VM
│   │   │
│   │   ├── filefunction/          # Forensics: secure delete & file recovery
│   │   │   ├── backend_bridge.py        # FileFunctionBridge (QObject for QML)
│   │   │   ├── service.py               # Secure delete + carving business logic
│   │   │   ├── recovery_controller.py   # RecoveryController (raw sector reads)
│   │   │   └── workers.py               # Background QThread workers
│   │   │
│   │   ├── history/               # Unified history & incident tracking
│   │   │   ├── unified_history.py       # Merged scan+incident+quarantine view
│   │   │   └── incident_repo.py         # RTP incident persistence
│   │   │
│   │   ├── gpu/
│   │   │   └── telemetry_worker.py      # Subprocess GPU poller (NVML/ADL/sysfs)
│   │   │
│   │   ├── intel/                 # Intel GPU telemetry caching
│   │   │   ├── cache.py
│   │   │   └── providers.py
│   │   │
│   │   └── sandbox/               # Generic sandbox job schema & runner
│   │       ├── job_schema.py
│   │       ├── report_schema.py
│   │       ├── report_builder.py
│   │       ├── vmware_runner.py
│   │       ├── analyzer_static.py
│   │       ├── analyzer_dynamic.py
│   │       └── engines.py
│   │
│   ├── infra/                     # External service integrations
│   │   ├── sqlite_repo.py         # SQLiteRepo (WAL, connection pooling)
│   │   ├── file_scanner.py        # LocalFileScanner
│   │   ├── nmap_cli.py            # NmapCli (subprocess wrapper)
│   │   ├── events_windows.py      # WindowsEventReader (pywin32)
│   │   ├── system_monitor_psutil.py # PsutilSystemMonitor (Windows)
│   │   ├── integrations.py        # Integration status reporter
│   │   └── privileges.py          # Windows UAC admin check
│   │
│   ├── platform/                  # OS-specific implementations
│   │   ├── paths.py               # Platform-aware data/config path resolution
│   │   └── linux/                 # Linux-only implementations
│   │       ├── admin.py           # Root privilege check
│   │       ├── events_linux.py    # LinuxEventReader (journalctl)
│   │       ├── secure_delete.py   # Linux shred (overwrite + unlink)
│   │       ├── security_controller.py # UFW/AppArmor/SELinux controller
│   │       ├── system_monitor_psutil.py # Linux PsutilSystemMonitor (sysfs)
│   │       └── system_snapshot_service.py # Linux security posture
│   │
│   ├── config/
│   │   └── settings.py            # Application settings dataclass
│   │
│   └── utils/
│       ├── admin.py               # AdminPrivileges (platform-aware elevation)
│       ├── diagnostics.py         # --diagnose CLI tool
│       ├── drop_event_filter.py   # WM_DROPFILES UIPI bypass for drag-and-drop
│       ├── gpu_manager.py         # GPU detection manager
│       ├── secure_delete.py       # Secure deletion utilities (Windows)
│       ├── security_info.py       # Security information helpers
│       └── security_snapshot.py   # Quick security snapshot utilities
│
├── frontend/
│   └── qml/
│       ├── main.qml               # Application root, navigation, sidebar
│       ├── pages/                 # All application views (16 QML pages)
│       ├── components/            # Reusable UI components (cards, charts, dialogs)
│       └── ui/                    # ThemeManager singleton
│
├── payload/
│   ├── sandbox_agent/             # In-VM behavioral analysis agent
│   │   ├── sentinel_agent.py      # Unified observe-classify-decide-execute loop
│   │   ├── monitor.py             # Process/file/network monitor
│   │   ├── classifier.py          # Behavioral threat classifier
│   │   ├── decision.py            # Decision engine
│   │   ├── resolver.py            # Action resolver
│   │   ├── executor.py            # Action executor
│   │   ├── verifier.py            # Post-action verifier
│   │   ├── telemetry.py           # Telemetry collector
│   │   └── hud.py                 # Optional HUD overlay inside guest
│   └── url_detonator/
│       └── webview2_detonator.py  # URL detonation via WebView2
│
├── scripts/
│   ├── build/build.ps1            # Windows PyInstaller build script
│   ├── build/build_linux.sh       # Linux build script
│   ├── run.ps1                    # Development run helper
│   ├── run_as_admin.bat           # Elevated launch shortcut
│   ├── run_diagnostics.py         # Diagnostics runner
│   └── dev/                       # Developer tooling (lint, QML auto-fix, GUI probe)
│
├── docs/                          # Full technical documentation
│   ├── ARCHITECTURE.md
│   ├── FEATURES_AND_WORKFLOWS.md
│   ├── BUILD_AND_VALIDATION.md
│   └── QUICKSTART.md
│
└── config/
    ├── sentinel.spec              # PyInstaller spec (main app)
    ├── sentinel_gpu_worker.spec   # PyInstaller spec (GPU subprocess)
    └── pyproject.toml             # Ruff/mypy/bandit tool configuration
```

---

## 6. Backend System — Deep Dive

### 6.1 Application Startup & Entry Point

**`main.py`** → **`backend.entrypoint.main()`** → **`backend.application.run()`**

The entry point follows a two-phase startup:

**Phase 1 — CLI Mode** (`entrypoint._run_cli_command`): If invoked with `--diagnose`, `--export-diagnostics`, or `--reset-settings`, Sentinel runs the requested tool and exits immediately without launching the GUI.

**Phase 2 — GUI Mode** (`DesktopSecurityApplication`):

The `DesktopSecurityApplication` class in `application.py` orchestrates startup using a **deferred initialization pattern** to achieve fast perceived startup time:

| Timing | Component | Reason |
|---|---|---|
| Immediate | `QApplication`, `QQmlApplicationEngine` | UI must exist first |
| Immediate | `BackendBridge` | QML references it on load |
| Immediate | `SettingsService` | Font/theme must apply before first paint |
| Immediate | `FileFunctionBridge`, `RecoveryController` | File-drop is immediately needed |
| 100ms deferred | Backend monitoring start | UI is already visible |
| 200ms deferred | System Snapshot Service | Heavy metrics collection |
| 300ms deferred | Security Controller | Platform security queries |
| 400ms deferred | Notification Service | Non-critical on startup |
| 500ms deferred | Resource Monitor, RTP auto-start | Background services |
| 1000ms deferred | GPU Service | On-demand (starts when user opens GPU page) |

After QML loads, a **system tray icon** is created with a context menu (Show Dashboard, System Monitor, Quit). Alert notifications from the Resource Monitor and RTP threats are routed through the tray icon when the window is hidden.

If the application has administrator privileges, it enables **WM_DROPFILES drag-and-drop** via a Win32 UIPI bypass (required because elevated processes are normally blocked from receiving OLE drag-and-drop events from lower-integrity windows).

### 6.2 Dependency Injection Container

`backend/core/container.py` implements a minimal DI container that resolves concrete implementations for abstract interfaces at startup. The `configure()` function registers all factories:

```python
# Interfaces resolved at runtime:
ISystemMonitor  → PsutilSystemMonitor (platform-specific)
IEventReader    → WindowsEventReader (Windows) | LinuxEventReader (Linux)
IScanRepository → SqliteRepo
IEventRepository→ SqliteRepo
IFileScanner    → LocalFileScanner
IUrlScanner     → UrlScanner
INetworkScanner → NmapCli
EventExplainerV5→ get_event_explainer_v5()  (Groq-backed)
EventSummarizer → get_event_summarizer()
ChatbotBridge   → None (lazy — created on first user request)
```

This pattern means that no platform-specific import executes on the wrong OS, and unit tests can substitute mocks by registering alternative factories.

### 6.3 Core Services

| Module | Role |
|---|---|
| `core/logging_setup.py` | Rotating file log (`sentinel.log`), crash handlers for uncaught exceptions |
| `core/perf_monitor.py` | Periodic memory/CPU sampling to `sentinel.log` (15-second interval) |
| `core/startup_orchestrator.py` | QTimer-based deferred initialization scheduler |
| `core/resource_monitor.py` | Threshold-based alerting (CPU > 90%, RAM > 85%, disk > 95%) → system tray toasts |
| `core/result_cache.py` | Thread-safe in-memory LRU cache for scan results |
| `core/errors.py` | Sentinel-specific exception hierarchy |
| `core/workers.py` | Generic `QRunnable`-based thread pool task runner |

### 6.4 Platform Abstraction Layer

The `backend/platform/` package is the boundary between OS-neutral and OS-specific code. At startup, `container.py` detects `IS_WINDOWS` / `IS_LINUX` and injects the correct implementation. No platform-specific code ever runs on the wrong OS.

**Windows Implementations:**
- `infra/events_windows.py` — reads Windows Event Log via `pywin32` (`win32evtlog`)
- `api/security_controller.py` — reads/writes Defender, UAC, and Firewall settings via PowerShell/WMI
- `api/system_snapshot_service.py` — WMI-based CPU, RAM, disk, and security metrics
- `infra/system_monitor_psutil.py` — Windows-flavoured `psutil` monitor (includes WMI for hardware details)
- `infra/privileges.py` — `ctypes.windll.shell32.IsUserAnAdmin()`

**Linux Implementations (under `backend/platform/linux/`):**
- `events_linux.py` — parses `journalctl --output=json --lines=N`
- `secure_delete.py` — `shred -u -n 3` or manual multi-pass overwrite + `unlink`
- `security_controller.py` — wraps `ufw`, `firewalld`, `iptables`, `aa-status`, `getenforce`, `mokutil`
- `system_snapshot_service.py` — reads `/proc/meminfo`, `/proc/loadavg`, and `psutil` disk/net
- `system_monitor_psutil.py` — Linux `psutil` monitor with `/sys/class/drm/` GPU reads
- `admin.py` — `os.geteuid() == 0` root check

**Path Resolution (`platform/paths.py`):**
All persistent data (database, logs, settings) is stored at OS-standard locations:
- **Windows:** `%APPDATA%\Sentinel\`
- **Linux:** `$XDG_DATA_HOME/Sentinel/` (defaults to `~/.local/share/Sentinel/`)

### 6.5 Infrastructure Layer

**`infra/sqlite_repo.py` — `SqliteRepo`**

Implements both `IScanRepository` and `IEventRepository`. Uses SQLite3 with:
- **WAL mode** for safe concurrent reads/writes from multiple threads
- `PRAGMA synchronous=NORMAL` for balanced safety/performance
- `PRAGMA cache_size=5000` for increased page cache
- Connection pool (size 5) with 30-second timeout
- Row factory for efficient result access

Tables: `scans` (file scan records), `events` (security events), `url_scans` (URL analysis records), `quarantine` (quarantined file records), `incident_history` (RTP threat events).

**`infra/nmap_cli.py` — `NmapCli`**

Wraps the Nmap binary as a subprocess. Constructs the appropriate command line for host discovery (`-sn`), service detection (`-sV`), or vulnerability scanning (`--script vuln`). Output is XML-parsed into structured Python objects. Returns a graceful "unavailable" result if `nmap` is not in the PATH.

**`infra/file_scanner.py` — `LocalFileScanner`**

Implements `IFileScanner` for local file system access. Validates file existence, read permissions, and size constraints before passing to the scan engine.

### 6.6 API / Bridge Layer

Every service exposed to QML is a `QObject` subclass registered via `engine.rootContext().setContextProperty()`. All public methods are decorated with `@Slot()` and return types are QML-compatible (str, int, bool, list, dict).

**Key bridges and the QML context property they expose:**

| Python Class | QML Property | Purpose |
|---|---|---|
| `BackendBridge` | `Backend` | File scan, network scan, event log, AI report |
| `GPUServiceBridge` | `GPUService` | GPU telemetry (subprocess IPC) |
| `SystemSnapshotService` | `SnapshotService` | System metrics (CPU, RAM, disk, network) |
| `SecurityController` | `SecurityController` | Defender/UFW/AppArmor controls |
| `SettingsService` | `SettingsService` | User preferences, theme, font, close behavior |
| `RealTimeProtectionBridge` | `RTPBridge` | RTP enable/disable/status/threat log |
| `FileFunctionBridge` | `backend` | Secure delete, drag-and-drop |
| `RecoveryController` | `RecoveryService` | Forensic file carving |
| `SandboxLabController` | `SandboxLab` | VMware sandbox lifecycle |
| `NotificationService` | `NotificationService` | In-app notification queue |
| `NotificationManager` | `NotificationManager` | Unified QML + tray notification dispatcher |
| `ResourceMonitorBridge` | `ResourceMonitor` | CPU/RAM/disk threshold alerts |
| `VmwareWindowEmbedder` | `VmwareEmbedder` | Win32 SetParent VM window embedding |

---

## 7. Security Engines — Feature Breakdown

### 7.1 Real-Time Protection (RTP)

**File:** `backend/core/realtime_protection.py`

RTP is Sentinel's process-level EDR component. It monitors every new process launch and runs executable files through the static scanner + Groq NGAV pipeline in real time.

**Architecture:**

```
QML Toggle ON/OFF
       │
RealTimeProtectionBridge (main thread QObject)
       │ starts/stops
RealTimeProtectionWorker (QThread, COM-initialized)
       │
  ┌────┴──────────────────┐
  │  Windows: WMI watcher │  Linux: psutil process polling
  │  Win32_Process events │  every 500ms, PID diff tracking
  └────┬──────────────────┘
       │ new PID + exe path
  StaticScanner.scan_file()
       │
  EnforcementPlan builder
       │
  ┌────┴──────────┐
  │ allow         │  decision_action != "block"
  │ log_only      │  safety guardrails triggered
  │ kill_process  │  high-confidence block verdict
  └───────────────┘
       │
  File action: quarantine / allow
```

**Windows Implementation:** Subscribes to WMI `__InstanceCreationEvent WITHIN 1 WHERE TargetInstance ISA 'Win32_Process'`. Each event carries PID, name, executable path, and parent PID. COM is initialized per-thread (`pythoncom.CoInitialize()`).

**Linux Implementation:** Calls `psutil.process_iter()` every 500ms, maintains a `seen_pids` set, and scans only newly discovered PIDs. Kernel threads and system processes are skipped.

**Safety Guardrails (the EnforcementPlan system):**

Before any process is killed, the `_build_enforcement_plan()` function checks multiple conditions. A block verdict is **downgraded to log_only** if:
- The process is a **Sentinel internal helper** (GPU worker, URL detonator, Sandbox Agent) spawned from Sentinel's own tree.
- The scan decision is **incomplete** (missing score, unknown verdict, or no explicit override).
- The executable is in a **protected install path** (Program Files, `/usr/bin`) and has a valid Authenticode signature — without ClamAV corroboration.
- The executable is a **mainstream browser** (Chrome, Firefox, Edge, Brave) in its expected install location.
- The executable is a **Windows system binary** (under `%SystemRoot%\`).

A validly signed binary is **never quarantined** without explicit ClamAV confirmation, preventing AI-score false positives.

**User Whitelist:** Users can add process names or full paths via QML. The whitelist is persisted in QSettings and propagated to the running worker immediately without restart.

**Key Data Structures:**
- `ThreatEvent` — full incident record (PID, path, score, verdict, action taken, SHA-256, publisher, signature validity)
- `EnforcementPlan` — the derived process/file action pair with diagnostic reason text

**Statistics:** `(total_scanned, threats_found, threats_killed)` emitted every 10 scans.

**Scan Cache:** Up to 5,000 entries, keyed by canonical lowercase path, validated by `(file_size, mtime_ns)` fingerprint. Stale entries (file modified since scan) are automatically evicted.

**Persistence:** Every threat event is recorded to the SQLite `incident_history` table via `IncidentHistoryRepo`.

---

### 7.2 Multi-Engine Scan Center (11-Stage Pipeline)

**Files:** `backend/engines/scanning/`, `backend/engines/scancenter/`

The Scan Center is a 6-phase interactive pipeline (ScanCenter orchestrator) built on top of an 11-stage analysis engine.

**The 11-Stage Analysis Pipeline (StaticScanner):**

| Stage | What Happens |
|---|---|
| **1. Validation & Access** | File existence, read permissions, size check (rejects over-large files) |
| **2. Hashing** | SHA-256 and MD5 simultaneously (`hashlib`) |
| **3. PE Static Analysis** | `pefile`: imports/exports, section entropy (packed binary detection), suspicious API calls (`VirtualAllocEx`, `SetWindowsHookEx`, `CreateRemoteThread`), overlay data |
| **4. String Extraction** | Up to 200 meaningful ASCII/Unicode strings extracted (min length 6) |
| **5. Groq AI NGAV** | Static indicators formatted into a specialized LLM prompt requesting a structured JSON verdict with behavioral classification |
| **6. ClamAV** | Local ClamAV daemon query (socket) or `clamscan` CLI fallback; skipped gracefully if not installed |
| **7. Signature Verification** | Windows Authenticode check via PowerShell `Get-AuthenticodeSignature` |
| **8. IOC Extraction** | Regex extraction of embedded IPs, domains, and URLs |
| **9. Deterministic Scoring** | `scoring.py` aggregates all findings (0-100 score). AI verdict alone cannot trigger blocking — the score must also be positive. |
| **10. Sandbox Detonation** | (Windows only) VMware integration triggered if sandbox configured |
| **11. Report Generation** | `V3Report` JSON saved to SQLite `scans` table |

**The 6-Phase ScanCenter Orchestrator (`scanner_orchestrator.py`, QThread):**

| Phase | Action |
|---|---|
| **Phase 1** | Static ClamAV scan + SHA-256 hash |
| **Phase 2** | VM revert to clean snapshot, monitor script + payload injection, VMware HWND discovery |
| **Phase 3** | Interactive pause — analyst manually triggers "Finish Session" |
| **Phase 4** | Pull `behavior.log` / `behavior_report.json` from guest, release VM embed, revert VM |
| **Phase 5** | Groq AI summary of the full behavior log |
| **Phase 6** | Deterministic scoring, emit `scan_complete`, redirect to scan result page |

The orchestrator emits `progress_updated(int, str)` signals to update the QML progress bar at every milestone, and `scan_complete(dict)` with the full `V3Report` when finished.

**Verdicts:** `Clean`, `Suspicious`, `Malicious`, `Unknown` — with scores 0-100 and triggered rule labels.

**Actions:** `allow`, `log_only`, `block` — fed into the RTP enforcement model when triggered from the scan center.

---

### 7.3 Dynamic Sandbox Lab

**Files:** `backend/engines/sandbox_vmware/`, `payload/sandbox_agent/`

**Windows-only.** Requires VMware Workstation with `vmrun` in the PATH and a pre-configured clean snapshot.

**Host-Side Workflow:**

1. **VM Revert:** `VmrunClient` calls `vmrun revertToSnapshot <vmx> <snapshot>` to restore the guest to a clean baseline.
2. **File Injection:** `vmrun copyFileFromHostToGuest` copies the sample to `C:\Users\Public\Downloads\payload.exe` in the guest.
3. **Monitor Deployment:** A PowerShell monitoring script (`monitor.ps1`) is injected to track process creation, file changes, registry modifications, and network connections.
4. **Visual Capture:** `preview_stream.py` captures the guest desktop at 500ms intervals using `imageio` + host screenshot APIs. Frames are streamed to the QML UI via `SandboxPreviewProvider` (Qt image provider).
5. **HWND Embedding:** `window_embedder.py` uses `EnumWindows` + `SetParent` Win32 calls to embed the `vmware-kvm.exe` console window directly into the Sentinel QML `WindowContainer`. The analyst sees the live VM desktop inside Sentinel.
6. **Teardown:** On "Finish Session", the embedded window is released, behavior logs are pulled via `vmrun copyFileFromGuestToHost`, and the VM is reverted to clean state.
7. **Report:** The `behavior_report.json` is parsed by `report_parser.py` and merged with the static scan results into a final `V3Report`.

**In-VM Agent (`payload/sandbox_agent/sentinel_agent.py`):**

The agent runs inside the guest VM and implements a full **Observe → Classify → Decide → Resolve → Execute → Verify** loop:
- Monitors new processes (`psutil`), file system events, registry changes, and network connections.
- Classifies behaviors against threat rules.
- Writes a structured `behavior_report.json` upon timeout.
- Optional HUD overlay (`hud.py`) shows live activity inside the guest VM.
- Anti-evasion: seeds environment indicators to encourage malware to execute rather than stay dormant.

---

### 7.4 AI Security Assistant

**File:** `backend/engines/ai/security_chatbot_v4.py`

The AI Security Assistant is a full **multi-turn conversational chatbot** backed by Groq's `llama-3.3-70b-versatile` model.

**Architecture:**

```
QML Chat UI
    │ sendMessage(text) @Slot
    │
ChatbotBridge (QObject, main thread)
    │ spawns
GroqChatWorker (QThread)
    │ calls Groq SDK (synchronous, off main thread)
    │ up to MAX_TOOL_ROUNDS=5 tool-calling rounds
    │ emits responseReceived(str) signal
    │
ChatbotBridge receives, updates history, emits to QML
```

**Features:**
- **System prompt** is platform-aware: tailors advice for Windows vs Linux, references the correct package manager (`winget` vs `apt`).
- **Tool-calling:** The chatbot can call system tools (scan files, check security posture, read event logs) and iterate up to 5 rounds before producing a final text reply.
- **Context-aware:** The assistant is briefed on the current system context (Windows/Linux, security posture) in the system prompt.
- **Conversation history** is stored in memory (not persisted across sessions).
- **Thread safety:** Only one worker runs at a time; concurrent requests are silently queued.

---

### 7.5 GPU & Hardware Telemetry

**Files:** `backend/api/gpu_service.py`, `backend/engines/gpu/telemetry_worker.py`

GPU monitoring is deliberately isolated in a **separate subprocess** to prevent driver crashes or hangs from affecting the main UI.

**Data Sources (multi-GPU aware):**

| GPU Type | Primary Source | Fallback |
|---|---|---|
| NVIDIA | `nvidia-ml-py` (NVML direct) | `nvidia-smi` CLI output parsing |
| AMD (Windows) | `pyadl` SDK | WMI query |
| AMD / Intel (Linux) | `/sys/class/drm/cardN/device/hwmon/` sysfs direct reads | `/sys/class/hwmon/` |
| Intel (Windows) | WMI query (optional, gated by `SENTINEL_INTEL_GPU=1`) | — |

**Metrics reported per GPU:** Utilization %, VRAM used/total, core clock, memory clock, shader clock, temperature (GPU die, hotspot, VRAM junction), power draw (W), TDP %, fan speed (RPM + %), PCIe bandwidth.

**IPC Protocol:** The worker subprocess emits newline-delimited JSON to stdout. The main process reads these lines in a `QThread` and emits Qt signals to update the `GPUService` QML model.

**Circuit Breaker:** A 60-second watchdog monitors the subprocess heartbeat. If the worker hangs (e.g., a faulty AMD DRM node blocks a read indefinitely), the circuit breaker force-terminates the subprocess and reports `Unavailable` to the UI. The GPU service can be restarted from QML.

**Hybrid Laptop Detection (Linux):** The system performs a 3-layer PCI bus scan to find powered-off discrete GPUs (via `lspci`) that proprietary drivers might hide.

---

### 7.6 Event Viewer & AI Event Explainer

**Files:** `backend/infra/events_windows.py`, `backend/platform/linux/events_linux.py`, `backend/engines/ai/event_explainer_v5.py`

**Data Collection:**
- **Windows:** `pywin32` (`win32evtlog`) reads from `System`, `Application`, and `Security` event logs. Returns structured `EventItem` objects with ID, source, level, timestamp, and raw message.
- **Linux:** Calls `journalctl --output=json --lines=N --no-pager` and parses the JSON stream. Supports filtering by unit, priority, and time range.

**AI Explainer V5 (`event_explainer_v5.py`):**
- Uses Groq `llama-3.1-8b-instant` (fast model) to generate plain-English explanations of Windows Event IDs or journald messages.
- Has a built-in `event_id_knowledge.py` knowledge base of common Windows Event IDs (4624, 4688, 7045, etc.) for rapid offline lookup.
- `soc_correlation.py` maps event patterns to SOC alert categories (lateral movement, privilege escalation, persistence, etc.).
- **Batch summarization** (`EventSummarizer`) can summarize groups of related events into a single threat narrative.

---

### 7.7 Network Scanner

**File:** `backend/infra/nmap_cli.py`

Wraps the Nmap binary for three scan types:

| Scan Type | Nmap Flags | Purpose |
|---|---|---|
| Host Discovery | `-sn` | Ping sweep to find live hosts on subnet |
| Service Detection | `-sV -T4` | Open port enumeration with service version |
| Vulnerability Scan | `--script vuln -T3` | NSE vulnerability script against targets |

Output is XML-parsed and converted to a structured Python dictionary for QML consumption. Nmap is not required — if absent, the scanner returns `{"status": "unavailable", "reason": "nmap not found in PATH"}`.

---

### 7.8 File Function: Secure Delete & Forensic Carving

**Files:** `backend/engines/filefunction/`, `backend/utils/secure_delete.py`

**Secure Delete (3-Pass):**

1. **Pass 1:** Overwrite file content with cryptographically random bytes.
2. **Pass 2:** Overwrite with random bytes again (different seed).
3. **Pass 3:** Overwrite with all zeros.
4. **Anti-MFT:** Rename the file to a random string before the final `unlink()` to prevent MFT/directory entry recovery.

On Linux, delegates to `shred -u -n 3` if available.

**Forensic File Carving (`RecoveryController`):**

Performs sector-by-sector raw disk reads, scanning for magic file header signatures:
- JPEG: `\xFF\xD8\xFF`
- PDF: `%PDF-`
- PNG: `\x89PNG`
- ZIP/DOCX: `PK\x03\x04`

On **Windows**, uses `CreateFile` with sector-aligned reads for raw disk access (bypasses NTFS file system, requires admin).
On **Linux**, opens `/dev/sdX` directly (requires root).

Recovered file fragments are extracted and saved to an output directory.

---

### 7.9 Security Posture Assessment (System Snapshot)

**Files:** `backend/api/system_snapshot_service.py` (Windows), `backend/platform/linux/system_snapshot_service.py`

Aggregates disparate OS security settings into a single health dashboard, updated every 5 seconds.

**Windows Checks:**
- **Windows Defender:** Real-Time Protection state, signature age (days old), quick scan last run — via WMI `AntiVirusProduct` and PowerShell `Get-MpPreference`.
- **UAC:** Registry `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\EnableLUA`.
- **Firewall:** Domain, Private, and Public profile states via `netsh advfirewall` or WMI.
- **BitLocker:** Drive encryption status via `manage-bde -status`.
- **Windows Update:** Last update date via WMI.

**Linux Checks:**
- **Firewall:** Detects and queries `ufw status`, `firewalld`, `iptables -L`, `nftables`.
- **AppArmor:** `aa-status --enabled` (enforcing / complain / disabled).
- **SELinux:** `getenforce` (Enforcing / Permissive / Disabled).
- **Secure Boot:** `mokutil --sb-state`.
- **Disk Encryption:** `lsblk -o NAME,TYPE,FSTYPE` to find LUKS-encrypted root/home partitions.
- **Automatic Updates:** Detects `unattended-upgrades`, `dnf-automatic`, `yum-cron`.
- **ClamAV:** Checks if ClamAV daemon is running and virus definitions are current.

---

### 7.10 History & Quarantine Management

**Files:** `backend/engines/history/`, `backend/engines/scancenter/history_repo.py`, `backend/engines/scanning/quarantine_manager.py`

**Unified History (`unified_history.py`):**

Merges four data sources into one searchable view:
1. **Scan records** — file and URL scan results with verdicts
2. **Incident records** — RTP threat events with enforcement actions
3. **Quarantine records** — quarantined files with metadata and restore options
4. **URL scan history** — URL analysis results

**Quarantine Vault (`quarantine_manager.py`):**

- Quarantined files are moved to a secure directory (`%APPDATA%\Sentinel\quarantine\`) with randomized names.
- Each entry is recorded in SQLite with: original path, SHA-256, verdict, timestamp, enforcement source, score, and all matched rules.
- The vault supports **safe restore** (move back to original location) and **permanent deletion**.
- Protected quarantine entries (e.g., signed system files) require explicit override metadata to restore.

---

### 7.11 URL Scanner & Detonator

**Files:** `backend/engines/scanning/url_scanner.py`, `payload/url_detonator/webview2_detonator.py`

**URL Scanner:**

Multi-engine URL analysis:
1. **Static checks:** Protocol validation, suspicious TLD detection, known malicious domain list lookup, shortener URL detection.
2. **External APIs:** Queries configurable reputation APIs (VirusTotal, safe browsing APIs) if API keys are configured.
3. **Groq AI:** Analyzes URL structure and any available page content for phishing indicators.
4. **Scoring:** Deterministic 0-100 score with `clean`, `suspicious`, `malicious` verdicts.

**URL Detonator (`webview2_detonator.py`):**

Uses Microsoft WebView2 (via `pywebview`) to safely open URLs in an isolated browser sandbox. Captures page screenshots, DOM content, and any download attempts for analysis.

---

## 8. Frontend — QML User Interface

### 8.1 Layout & Navigation

The main window (`frontend/qml/main.qml`) is an `ApplicationWindow` (1400×900 minimum 1000×600) built with a two-column `RowLayout`:

**Sidebar (collapsible):**
- Collapsed: 74px wide (icon-only)
- Expanded: 218px wide (icon + label)
- Auto-expands on hover, collapses after 1.5s mouse-leave delay
- Navigation items: Home, System Monitor, System Snapshot, Event Viewer, Scan Center, File Function, Sandbox Lab, Network Scan, GPU Monitor, AI Assistant, History, Settings

**Content Area:**
A `Loader` that dynamically instantiates the selected page. Lazy loading — page QML files are only loaded when first navigated to, and kept in memory thereafter.

**Header:** Displays current page title, subtitle, and navigation breadcrumb.

**Notification Center:** An in-app notification panel (slide-in from top-right) fed by `NotificationService`.

### 8.2 Pages Overview

| QML File | Route | Description |
|---|---|---|
| `HomePage.qml` | `home` | Security overview dashboard — quick posture summary, RTP status, recent alerts, quick-action buttons |
| `SystemMonitor.qml` | `system-monitor` | Live CPU/RAM/disk/network charts, RTP process log, resource alerts |
| `SystemSnapshot.qml` | `snapshot` | Full system inventory — hardware, OS, security posture, disk partitions, network interfaces |
| `EventViewer.qml` | `event-viewer` | Windows Event Log / journalctl viewer with AI explanation panel |
| `ScanCenter.qml` | `scan-tool` | File drop zone, scan progress, verdict display, AI report link |
| `AiReport.qml` | `ai-report` | Full Groq AI scan explanation with remediation guidance |
| `SandboxLabPage.qml` | `sandbox-lab` | VMware sandbox controls, live VM window embed, behavior report viewer |
| `GPUMonitor.qml` | `gpu-monitor` | Real-time GPU metrics: utilization, VRAM, clocks, temperatures, power, fan |
| `NetworkScan.qml` | `net-scan` | Network scan controls (subnet input, scan type selector) |
| `NmapScanResultPage.qml` | `nmap-result` | Nmap output with host list, open ports, service versions, vulnerability findings |
| `FileFunction.qml` | `file-function` | Secure delete (drag-and-drop) and forensic carving controls |
| `SecurityAssistant.qml` | `ai-assistant` | Multi-turn security chatbot UI with message history |
| `HistoryPage.qml` | `history` | Tabbed: Scan History / Incidents / Quarantine / URL History |
| `ScanHistory.qml` | (sub-component) | Paginated scan result list with filter controls |
| `ResolutionReport.qml` | (sub-component) | Full scan report viewer (file details, score breakdown, IOCs) |
| `SettingsPage.qml` | `settings` | Theme (dark/light), font size, close-to-tray, RTP auto-start, Groq API key, sandbox VM path |

### 8.3 Theme System

`frontend/qml/ui/ThemeManager.qml` is a QML singleton that provides color tokens for the entire application:
- **Dark mode** (default): Deep navy/charcoal backgrounds, accent indigo (#6366F1)
- **Light mode:** Off-white backgrounds, same accent
- Font size is adjustable from 10px to 18px and propagated via `QApplication.setFont()`
- Theme changes are applied without restart — all QML elements bind to `ThemeManager.*` properties

---

## 9. Payload: Sandbox Agent (In-VM)

**Directory:** `payload/sandbox_agent/`

The sandbox agent is compiled to a standalone `sentinel_agent.exe` via PyInstaller and deployed into the guest VM by the sandbox controller. It is designed to run **only inside the isolated VM**.

**Agent Loop:**

```
Observe (monitor processes, files, network)
    │
Classify (behavioral threat classification)
    │
Decide (should we record / alert / block?)
    │
Resolve (determine action)
    │
Execute (take action if configured)
    │
Verify (confirm action succeeded)
    │
Record → behavior_report.json
```

**Components:**

| File | Role |
|---|---|
| `sentinel_agent.py` | Unified main agent — owns the full O→C→D→R→E→V loop |
| `monitor.py` | psutil process monitor + file system watcher + network connection tracker |
| `classifier.py` | Rule-based behavioral threat classifier |
| `decision.py` | Decision engine with confidence thresholds |
| `resolver.py` | Translates decisions to action records |
| `executor.py` | Executes actions (logging, alerting) |
| `verifier.py` | Confirms actions completed successfully |
| `telemetry.py` | Structured telemetry collection |
| `hud.py` | Optional tkinter overlay showing live activity inside guest |
| `human_sim.py` | Anti-evasion: simulates human-like mouse/keyboard activity to trigger malware |
| `memory.py` | Shared state storage across agent components |
| `models.py` | Agent data models |
| `observer.py` | Event stream aggregator |

**Output:** A `behavior_report.json` containing process creation events, file modifications, registry changes, and network connections — pulled back to the host by the sandbox controller for inclusion in the `V3Report`.

---

## 10. Data Persistence — SQLite

All persistent data is stored in a single SQLite database file (`sentinel.db`) at the platform-standard data directory.

**Database Schema:**

| Table | Purpose | Key Columns |
|---|---|---|
| `scans` | File and URL scan records | `id`, `file_path`, `file_hash`, `scan_type`, `verdict`, `score`, `timestamp`, `report_json` |
| `events` | Security events (cached from Event Log) | `id`, `source`, `event_id`, `level`, `message`, `timestamp` |
| `url_scans` | URL analysis results | `id`, `url`, `verdict`, `score`, `timestamp`, `report_json` |
| `quarantine` | Active quarantine entries | `id`, `original_path`, `quarantine_path`, `sha256`, `verdict`, `timestamp`, `metadata_json` |
| `incident_history` | RTP threat events | `id`, `pid`, `process_name`, `exe_path`, `verdict`, `action_taken`, `timestamp`, `event_json` |

**WAL Mode** allows the RTP engine to write incident records while the UI simultaneously reads scan history, without blocking either operation.

---

## 11. Cross-Platform Support Matrix

| Feature | Windows | Linux |
|---|---|---|
| System Snapshot & Posture | ✅ Defender, UAC, BitLocker, Firewall | ✅ UFW, AppArmor, SELinux, LUKS |
| GPU Telemetry (NVIDIA) | ✅ NVML | ✅ NVML |
| GPU Telemetry (AMD) | ✅ pyadl | ✅ sysfs/DRM direct reads |
| GPU Telemetry (Intel) | ✅ WMI (optional) | ✅ sysfs reads |
| Real-Time Protection | ✅ WMI __InstanceCreation | ✅ psutil polling |
| Event Viewer | ✅ Windows Event Log (pywin32) | ✅ journalctl |
| Sandbox Detonation | ✅ VMware Workstation | ❌ Not supported |
| Secure Delete | ✅ 3-pass overwrite | ✅ shred / manual overwrite |
| Forensic Carving | ✅ Win32 CreateFile (raw) | ✅ /dev/sdX direct read |
| Network Scanner | ✅ Nmap | ✅ Nmap |
| AI Assistant | ✅ Groq | ✅ Groq |
| Security Settings Toggle | ✅ PowerShell/WMI | ✅ Shell wrappers |
| Data Path | `%APPDATA%\Sentinel\` | `~/.local/share/Sentinel/` |
| Admin Check | `IsUserAnAdmin()` (Win32) | `os.geteuid() == 0` |
| Drag-and-Drop (elevated) | ✅ WM_DROPFILES UIPI bypass | ✅ Qt DropArea |

---

## 12. Graceful Degradation Model

Sentinel's "Truthful Platform Boundaries" principle means every capability has an explicit status:

| Status | Meaning | Example |
|---|---|---|
| `ok` / running | Feature is fully operational | RTP running, Nmap found |
| `unsupported` | The OS fundamentally cannot support this | Sandbox on Linux |
| `unavailable` | Feature could work but dependency is absent | Nmap not in PATH, ClamAV not installed |
| `permission_denied` | Feature requires elevation | Raw disk read without admin |
| `degraded` | Feature is partially working | Scanner running but AI key missing |

This is implemented across every service:
- If `nmap` is not found: returns `{"status": "unavailable"}` instead of crashing.
- If `GROQ_API_KEY` is missing: AI features show "API key not configured" without affecting other modules.
- If WMI hangs (GPU driver bug): circuit breaker terminates the subprocess and shows `Unavailable`.
- If ClamAV is missing: the scan pipeline continues without it, noting ClamAV as skipped.
- If the user lacks admin rights: features requiring elevation show `Permission Required` with a specific explanation.

---

## 13. Testing & Quality Assurance

**Test Suite Location:** `backend/tests/` — 35+ test modules.

**Test Coverage Areas:**

| Test File | What It Verifies |
|---|---|
| `test_core.py` | Core infrastructure, config, container resolution |
| `test_container.py` | DI container registration and resolution |
| `test_smoke.py` | Application imports without crashing |
| `test_realtime_protection_runtime.py` | RTP worker lifecycle, scan/kill flow |
| `test_rtp_enforcement_safety.py` | Safety guardrails (no false positive kills) |
| `test_rtp_preference_persistence.py` | RTP QSettings persistence across restarts |
| `test_scan_contracts.py` | Scan result schema contracts |
| `test_scoring_policy.py` | Score aggregation rules |
| `test_decision_alignment.py` | Verdict/action alignment consistency |
| `test_report_schema_v2.py` | V3Report schema validation |
| `test_report_writer_truthfulness.py` | Report writer accuracy |
| `test_scancenter_orchestrator.py` | ScanCenter phase sequencing |
| `test_repos.py` | SQLite repository CRUD operations |
| `test_history_data.py` | History repository queries |
| `test_history_qml_guards.py` | QML-facing history API guards |
| `test_services.py` | Service layer integration |
| `test_backend_bridge_ai.py` | BackendBridge AI path |
| `test_degraded_states.py` | Graceful degradation behavior |
| `test_settings_persistence.py` | Settings QSettings round-trip |
| `test_theme_persistence.py` | Theme preference persistence |
| `test_linux_security_posture.py` | Linux posture check accuracy |
| `test_linux_amd_gpu.py` | Linux AMD GPU sysfs parsing |
| `test_linux_gpu_normalization.py` | GPU metric normalization |
| `test_linux_storage.py` | Linux disk/partition detection |
| `test_platform_paths.py` | Cross-platform path resolution |
| `test_windows_ui_regression_guards.py` | Windows-specific UI regression tests |
| `test_modal_dialog_regressions.py` | Dialog result persistence across QML unload |
| `test_security_truthfulness.py` | No fabricated security values |
| `test_security_toggle_refresh.py` | Security setting toggle + refresh cycle |
| `test_runtime_policies.py` | Runtime enforcement policy consistency |
| `test_application_close_behavior.py` | Close-to-tray vs quit behavior |
| `test_system_monitor_psutil.py` | psutil monitor accuracy |
| `test_sandbox_report.py` | Sandbox behavior report parsing |
| `test_reporting_policy.py` | Report content policy compliance |
| `test_diagnostics.py` | Diagnostics tool output |
| `test_release_polish_guards.py` | Release readiness regression guards |

**Quality Tooling:**

| Tool | Configuration | Purpose |
|---|---|---|
| `pytest` | `config/pytest.ini` | Test runner |
| `ruff` | `pyproject.toml` | Linting + formatting (replaces flake8/isort/black) |
| `mypy` | `pyproject.toml` | Static type checking |
| `bandit` | `pyproject.toml` | Security vulnerability linting |
| `pre-commit` | `.pre-commit-config.yaml` | Git pre-commit hooks |

**Running Tests:**
```bash
pytest backend/tests/           # Full test suite
pytest backend/tests/ -v        # Verbose output
python -m backend --diagnose    # Runtime dependency check
```

---

## 14. Build & Packaging

**PyInstaller Specs:**

| Spec File | Output | Purpose |
|---|---|---|
| `config/sentinel.spec` | `dist/Sentinel/Sentinel.exe` | Main application executable |
| `config/sentinel_gpu_worker.spec` | `dist/sentinel_gpu_worker.exe` | GPU telemetry subprocess |
| `config/sentinel_url_detonator.spec` | `dist/sentinel_url_detonator.exe` | URL detonation subprocess |
| `scripts/build/sentinel_agent.spec` | `dist/sentinel_agent.exe` | In-VM sandbox agent |

**Build Commands:**

```powershell
# Windows — full build
.\scripts\build\build.ps1

# Linux — build script
bash scripts/build/build_linux.sh
```

The PyInstaller build produces a `dist/Sentinel/` directory containing:
- `Sentinel.exe` (main application)
- `sentinel_gpu_worker.exe` (GPU subprocess, placed next to main exe)
- `frontend/qml/` (QML source tree, bundled at `_internal/`)
- `_internal/` (all Python dependencies as DLLs/PYDs)

**Environment Configuration for Frozen Builds:**

Users place a `.env` file next to `Sentinel.exe`. The `entrypoint.py` scans both `app_root()` and `bundle_root()` for the `.env` file, so it works in both development and packaged modes.

---

## 15. Configuration & Environment Variables

**`.env` File:**

```ini
# Required for AI features
GROQ_API_KEY=your_groq_api_key_here

# Optional: skip UAC elevation prompt (development only)
SKIP_UAC=0

# Optional: enable Intel GPU monitoring (slow WMI queries)
SENTINEL_INTEL_GPU=0

# Optional: VMware sandbox configuration
VMWARE_VM_PATH=C:\VMs\Windows10\Windows10.vmx
VMWARE_SNAPSHOT=Clean Base
VMWARE_VMRUN=C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe
```

**QSettings Persistence (via `SettingsService`):**

| Key | Type | Default | Description |
|---|---|---|---|
| `themeMode` | str | `"dark"` | UI theme: `"dark"` or `"light"` |
| `fontSize` | int | 13 | Global font size in pixels |
| `closeToTray` | bool | `false` | Minimize to tray instead of quit |
| `rtpEnabled` | bool | `true` | RTP auto-start on next launch |
| `rtpUserWhitelist` | list[str] | `[]` | User-managed RTP process whitelist |

**CLI Mode:**

```bash
python -m backend --diagnose              # Check all dependencies and show status
python -m backend --export-diagnostics out.json  # Save diagnostics to JSON
python -m backend --reset-settings        # Reset all QSettings to defaults
python main.py                            # Launch GUI normally
```

---

## 16. Security Design Decisions

### AI-Cannot-Kill Principle

The most important security design decision: **AI verdicts alone can never trigger process termination or file quarantine.** The flow is:

```
Groq AI verdict → contributes to score
ClamAV result  → corroborating evidence
Signature check → safety gate
                    ↓
         Deterministic score 0-100
                    ↓
            EnforcementPlan builder
           (multiple safety guards)
                    ↓
          kill / quarantine / log_only
```

A score must be positive, the verdict must be complete, and corroborating evidence (ClamAV or explicit operator override) is required before destructive actions. This prevents LLM hallucinations from causing false-positive terminations.

### Process Whitelist Strategy

The RTP whitelist operates in layers:
1. **Static whitelist** — hundreds of known-safe processes (kernel, Windows components, developer tools, common applications) hardcoded in `WHITELISTED_PROCESSES`.
2. **Name prefix matching** — any process starting with `microsoft.` or `windows.` is automatically trusted.
3. **Sentinel self-trust** — Sentinel's own helper processes are trusted only when they run from Sentinel's own installation tree AND are spawned by Sentinel's own main process (validated via parent PID chain).
4. **User whitelist** — persisted in QSettings, propagated to the running worker immediately.

### Privilege Isolation

- The UI and backend run as a single process (for QML ↔ Python integration), but heavy workloads (GPU, URL detonation, sandbox) are isolated in separate processes.
- Admin privileges are requested via UAC elevation at startup. Non-admin users can still use most features; features requiring elevation show `Permission Required` with a specific explanation.
- The `SKIP_UAC=1` environment variable allows developers to bypass elevation for development.

### Database Thread Safety

Multiple components (RTP engine, scan center, UI) write to SQLite simultaneously. WAL mode ensures readers never block writers and vice versa. Each write operation uses its own connection (no shared connection state across threads).

---

## 17. Limitations & Known Boundaries

| Area | Limitation |
|---|---|
| **Production Readiness** | Research/graduation project. Not a commercially certified EDR. Lacks kernel-level hooks, enterprise policy management, SIEM integration. |
| **Linux RTP** | Uses user-space psutil polling. Advanced rootkits that hide PIDs in the kernel will evade detection. |
| **Sandbox** | Requires licensed VMware Workstation installed locally. Not designed for cloud hypervisor scaling. |
| **AI Hallucinations** | Groq LLM is assistive. Core enforcement is deterministic, but AI explanations may occasionally be inaccurate. |
| **Static Analysis Quality** | `ruff` and `mypy` are configured as cleanup baselines, not passing gates — existing code has known type annotation gaps. |
| **ClamAV Signatures** | Effectiveness depends on ClamAV database freshness. Zero-day malware not yet in the signature database will not be caught by this stage. |
| **Authenticode (Windows)** | Signature verification via PowerShell adds ~1-2 seconds per scan. This is intentional (prevents race conditions with fast-spawning processes). |

---

## 18. CI/CD Pipeline

**GitHub Actions Workflows (`.github/workflows/`):**

| Workflow | Trigger | What It Does |
|---|---|---|
| `ci.yml` | Push / PR to `main` | Install dependencies, run `pytest`, run `ruff` lint check |
| `gui-check.yml` | Push / PR to `main` | Validate QML can be imported (headless Qt) |
| `quality.yml` | Push / PR to `main` | `mypy` type checking, `bandit` security scan |

**Pre-commit Hooks (`.pre-commit-config.yaml`):**

Runs before every commit:
- `ruff` — linting and auto-fixing
- Trailing whitespace removal
- End-of-file newline enforcement
- YAML/JSON validation

---

## 19. BackendBridge — Complete Signal & Slot Reference

**File:** `backend/api/backend_bridge.py`

`BackendBridge` is the largest single file in the project (~1,600 lines). It is the sole gateway between the QML frontend and all backend services. Every public method is a `@Slot()` and every UI update is a `Signal()`.

### Complete Signal Inventory

**System monitoring:**

| Signal | Payload | Purpose |
|---|---|---|
| `snapshotUpdated` | `dict` | System metrics snapshot (CPU, RAM, disk, network) |
| `eventsLoaded` | `list` | Windows Event Log / journalctl event list |
| `scansLoaded` | `list` | Scan history rows |
| `toast` | `(str level, str message)` | In-app notification (redirected to NotificationCenter) |
| `scanFinished` | `(str type, dict result)` | Legacy scan completion |
| `integrationStatusChanged` | — | ClamAV / Nmap availability changed |

**Nmap / Network scanning (streaming):**

| Signal | Payload | Purpose |
|---|---|---|
| `nmapScanStarted` | `(scanId, scanType, targetHost)` | Scan kicked off |
| `nmapScanOutput` | `(scanId, outputText)` | Live stdout line from `QProcess` |
| `nmapScanFinished` | `(scanId, success, exitCode, reportPath)` | Scan complete |

**AI / Event explanation:**

| Signal | Payload | Purpose |
|---|---|---|
| `eventExplanationReady` | `(eventId, explanationJson)` | Groq explanation of a single event |
| `eventExplanationFailed` | `(eventId, errorMessage)` | Explanation failed |
| `eventPreviewReady` | `(eventId, briefJson)` | Brief 1-line preview of an event |
| `chatMessageAdded` | `(role, content)` | Chatbot turn added ("user" \| "assistant") |
| `chatScanProgress` | `(percent, statusMessage)` | Chatbot scan-tool sub-task progress |
| `smartAssistantResponse` | `str JSON` | SmartAssistant structured reply |
| `smartAssistantError` | `str` | SmartAssistant error message |
| `agentStepAdded` | `str JSON` | Agent timeline step (for replay view) |
| `agentStepsCleared` | — | Reset agent timeline |

**Local (offline) scanning:**

| Signal | Payload | Purpose |
|---|---|---|
| `localScanStarted` | — | Local scan begun |
| `localScanProgress` | `str` | Stage name |
| `localScanFinished` | `dict` | Full local scan result |
| `localUrlCheckFinished` | `dict` | Local URL check result |

**VMware sandbox pipeline:**

| Signal | Payload | Purpose |
|---|---|---|
| `sandboxProgress` | `int` 0-100 | Sandbox job overall progress |
| `sandboxFinished` | `dict` | `SandboxJobResult` payload |
| `sandboxFailed` | `str` | Error message |
| `sandboxStateChanged` | `str` | Job state: `IDLE/STARTING/RUNNING/COLLECTING/CLEANUP/FINISHED/FAILED/CANCELLED` |
| `sandboxExplainFinished` | `dict` | AI explanation of sandbox report |
| `sandboxScreenshot` | `str` | Absolute path to latest PNG screenshot |
| `sandboxEventBatch` | `str JSON[]` | Batch of live sandbox events |
| `sandboxStatsUpdate` | `str JSON` | Session stats object |
| `sandboxSessionEnded` | `str JSON` | Full session summary |

**Live sandbox preview (video-like capture):**

| Signal | Payload | Purpose |
|---|---|---|
| `sandboxPreviewStarted` | — | Frame capture started |
| `sandboxPreviewStopped` | — | Frame capture stopped |
| `sandboxPreviewFrameReady` | `int` | New frame number available |
| `sandboxWindowFound` | `bool` | Whether the sandbox window was found |
| `sandboxAutopilotAction` | `str JSON` | Autopilot performed a UI click/action |

**Integrated (bundled) sandbox:**

| Signal | Payload | Purpose |
|---|---|---|
| `integratedSandboxStarted` | — | Started |
| `integratedSandboxProgress` | `str` | Stage name |
| `integratedSandboxFinished` | `dict` | Static + sandbox + scoring result |

**URL scanning:**

| Signal | Payload | Purpose |
|---|---|---|
| `urlScanStarted` | — | URL scan begun |
| `urlScanProgress` | `(str stage, int pct)` | Stage name + progress % |
| `urlScanFinished` | `dict` | Verdict, score, evidence, explanation |

**ScanCenter pipeline (V3 report):**

| Signal | Payload | Purpose |
|---|---|---|
| `scanCenterProgress` | `(int pct, str stage)` | Progress 0-100 + stage label |
| `scanCenterFinished` | `dict` | Full `V3Report.to_dict()` |
| `scanCenterAiBrief` | `str` | Groq AI 1-sentence brief |
| `scanCenterAiDetailed` | `str` | Groq AI multi-paragraph detailed report |
| `scanCenterFailed` | `str` | Error message |
| `scanCenterHistoryLoaded` | `list[dict]` | History rows |
| `scanCenterExplainFinished` | `dict` | `AiExplanation.to_dict()` |
| `scanCenterExported` | `dict` | `{ok, report_path, zip_path, sha256}` |
| `scanCenterPhaseUpdate` | `str JSON` | `{phase, status, summary, score, pct}` — per-phase detail card |
| `scanCenterPreviewUpdated` | `str` | Cache-busted `file:///...?ts=N` URL for live preview image |

**Scan report / history:**

| Signal | Payload | Purpose |
|---|---|---|
| `scanReportExported` | `dict` | `{ok, exported_report_path, exported_artifacts_path, sha256}` |
| `sentinelReportLoaded` | `dict` | Normalized `SentinelReport` (history replay) |
| `scanHistoryLoaded` | `(str request_id, list rows)` | History query result |
| `vmwareDiagnosticsResult` | `list[dict]` | VMware readiness check results |

**Navigation:**

| Signal | Payload | Purpose |
|---|---|---|
| `navigateTo` | `str route` | Requests main.qml to change the active page |
| `sandboxHandoffRequested` | `str path` | Sends a file path to the Sandbox Lab page |

### BackendBridge Initialization Details

On construction, `BackendBridge.__init__()` performs these steps in order, all without blocking the UI:

1. **Resolve DI dependencies** — `ISystemMonitor`, `IEventReader`, `IScanRepository`, `IEventRepository` are resolved from the container immediately. `INetworkScanner`, `IFileScanner`, `IUrlScanner` are resolved with `IntegrationDisabled` / `ExternalToolMissing` exception handling (silently `None` if unavailable).
2. **Start live timer** — `QTimer` ticks every second calling `_tick()` (publishes system snapshot).
3. **Wire worker watchdog** — `get_watchdog()` monitors stalled `CancellableWorker` threads; `_on_worker_stalled` cancels the hung worker and emits a toast.
4. **Create result cache** — `get_scan_cache()` returns a shared `ResultCache` for scan deduplication.
5. **Defer heavyweight init** — three `QTimer.singleShot` calls schedule: SQLite `CREATE TABLE` at 0ms, AI service init at 50ms, ClamAV status probe at 100ms.
6. **Pre-warm security snapshot** — called immediately in background so the first chatbot security question has context ready 3–5 seconds early.

### File Path Normalization (`_normalize_filepath`)

All file paths that arrive from QML are passed through `_normalize_filepath()` which handles:

- `file:///` and `file://` URI prefix stripping
- URL percent-decoding (`%20` → space, etc.)
- Forward-slash / backslash normalization to `os.sep`
- Linux leading `/` insertion
- `os.path.abspath()` resolution of `.` / `..` components

### Scan Result Normalization (`_normalize_file_scan_result_for_qml`)

Before any file scan result is emitted to QML, it is passed through `_normalize_file_scan_result_for_qml()`, which guarantees every expected key exists with a valid type (never `undefined` in QML):

| Key | Type | Fallback |
|---|---|---|
| `file_name`, `file_path` | `str` | `""` |
| `verdict` | `str` | `"Unknown"` |
| `score` | `int` | `0` |
| `iocs` | `dict` | `{}` |
| `groq_analysis` | `dict` | `{}` |
| `pe_info`, `pe_analysis` | `dict` | `{}` |
| `sandbox_result` | `dict` | `{}` |
| `final_decision` | `dict` | Built via `build_final_decision(score, verdict)` |
| `groq_ai_score` | `int` | Pulled from `groq_analysis.score` |
| `iocs_found` | `bool` | `any(bool(v) for v in iocs.values())` |
| `pe_analyzed` | `bool` | `bool(pe_info or pe_analysis)` |
| `has_sandbox` | `bool` | `bool(sandbox_data and sandbox_data.success)` |

An equivalent `_normalize_url_scan_result_for_qml()` performs the same sanitization for URL scan results.

---

## 20. SettingsService — Complete Property & Slot Reference

**File:** `backend/api/settings_service.py`

`SettingsService` persists all user preferences using `QSettings("SentinelSecurity", "SentinelApp")`.

- **Windows:** Stored in the registry at `HKEY_CURRENT_USER\Software\SentinelSecurity\SentinelApp`
- **Linux:** Stored as an INI file at `~/.config/SentinelSecurity/SentinelApp.conf`

### All QSettings Keys and Their Properties

| QSettings Key | `QProperty` Name | Type | Default | Signal |
| --- | --- | --- | --- | --- |
| `themeMode` | `themeMode` | `str` | `"dark"` | `themeModeChanged` |
| `fontSize` | `fontSize` | `str` (`"small"/"medium"/"large"`) | `"medium"` | `fontSizeChanged`, `globalFontChanged(int px)` |
| *(derived)* | `fontSizePixels` | `int` (12/14/16) | 14 | `fontSizeChanged` |
| `liveMonitoring` | `liveMonitoring` | `bool` | `True` | `liveMonitoringChanged` |
| `updateIntervalMs` | `updateIntervalMs` | `int` (≥ 500) | 2000 | `updateIntervalMsChanged` |
| `enableGpuMonitoring` | `enableGpuMonitoring` | `bool` | `True` | `enableGpuMonitoringChanged` |
| `startMinimized` | `closeToTray` / `startMinimized` | `bool` | `False` | `closeToTrayChanged`, `startMinimizedChanged` |
| `startWithSystem` | `startWithSystem` | `bool` | `False` | `startWithSystemChanged` |
| `sendErrorReports` | `sendErrorReports` | `bool` | `False` | `sendErrorReportsChanged` |
| `networkUnit` | `networkUnit` | `str` (`"auto"/"bps"/"Kbps"/"Mbps"/"Gbps"`) | `"auto"` | `networkUnitChanged` |
| `groqApiKey` | `groqApiKeyConfigured` (bool) / `groqApiKeyMasked` (str) | — | `""` | `groqApiKeyChanged` |

### Platform-Constant Properties (read-only)

| Property | Type | Value |
|---|---|---|
| `platformName` | `str` | `platform.system()` (e.g. `"Windows"`, `"Linux"`) |
| `isWindows` | `bool` | `sys.platform == "win32"` |
| `supportsAutostart` | `bool` | `True` on Windows only |
| `supportsCloseToTray` | `bool` | `True` when `QSystemTrayIcon.isSystemTrayAvailable()` |
| `settingsPath` | `str` | Full path of the QSettings backing file |

### Groq API Key Management

The `SettingsService` owns the full Groq API key lifecycle:

1. **On startup:** Any key stored in QSettings is injected into `os.environ["GROQ_API_KEY"]` if the env var is not already set (e.g. from a `.env` file). This means a key saved via the UI survives restarts without requiring a `.env` file.
2. **`saveGroqApiKey(key)`** — persists the key to QSettings **and** sets `os.environ["GROQ_API_KEY"]` immediately. Also calls `reset_groq_provider()` to hot-swap the Groq SDK client without a restart. If an empty string is passed, the key is cleared from both QSettings and the environment.
3. **`groqApiKeyMasked`** — returns `"gsk_••••••••zxcv"` (first 4 + last 4 characters) for safe UI display. The full key is never logged or displayed.
4. **`testGroqConnection()`** — spawns a `_GroqTestWorker` (QThread) that calls `Groq(api_key=...).models.list()` (a lightweight, token-free API call). Emits `groqTestResult("ok"|"error", message)`. Falls back to a raw `urllib` HTTP probe if the `groq` SDK is not installed.

### Windows Autostart (Registry Integration)

When `startWithSystem` is set to `True` on Windows, `_set_windows_autostart(True)` writes to:

```
HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
  "Sentinel" = "C:\path\to\Sentinel.exe"   (frozen build)
              = '"python.exe" "main.py"'     (dev mode)
```

When set to `False`, the registry value is deleted. `supportsAutostart` is always `False` on Linux, so the setter silently ignores enable requests on that platform.

### `resetToDefaults()` Slot

Resets all settings to their defaults, clears the Windows autostart registry entry, and emits all change signals so the UI updates reactively without requiring a page reload.

---

## 21. QML Pages — Internal Wiring Details

This section documents the internal state, QML bindings, and signal connections for each page, going beyond the feature-level description in Section 8.

### HomePage.qml

**State properties:**

- `rtpStatusLabel` (`str`) — current RTP display text: `"Active"`, `"Monitoring"`, `"Disabled"`, `"Unavailable"`, `"Not supported"`, `"Starting..."`
- `rtpGood` (`bool`) — green indicator (RTP running with scanner active)
- `rtpWarning` (`bool`) — amber indicator (RTP running but scanner degraded, or available but disabled)
- `recentScanItem` (`var`) — most recent scan record from `Backend.getUnifiedScanHistory(1)`
- `quarantineActiveCount` (`int`) — active quarantine entries from `Backend.getQuarantineHistory()`
- `incidentCount` (`int`) — recent RTP incidents from `Backend.getIncidentHistory(50)`

**RTP sync logic (`syncRtpState()`):** Calls `RTPBridge.getCapabilityState()`, `getStatus()`, `getMonitoringState()`, `getProcessScannerState()` to compute the display label and color. Runs on:

- A 3-second `Timer` while the page is visible
- Instantly via `Connections { target: RTPBridge; onProtectionStatusChanged; onCapabilityChanged }`
- `triggeredOnStart: true` — refreshes immediately on every navigation to this page

**Activity summary (`loadActivitySummary()`):** Pulls last scan, quarantine count, and incident count on page completion. `formatScanAge()` converts a UTC ISO timestamp to a relative string (`"just now"`, `"5m ago"`, `"2h ago"`, `"3d ago"`).

---

### ScanCenter.qml

**Three-tab interface (segment property):** `0 = File Scan`, `1 = URL Scan`, `2 = History`

**File scan state:**

| Property | Type | Purpose |
|---|---|---|
| `filePath` / `fileName` | `str` | Currently selected file |
| `fileReport` | `var` | Normalized V3Report dict after scan |
| `fileScanning` | `bool` | Scan in progress guard |
| `filePct` / `fileStage` | `int` / `str` | Progress bar binding |
| `optClamAV` | `bool` | Whether to include ClamAV stage (default `true`) |
| `optSandbox` | `bool` | Whether to trigger VMware sandbox |
| `optNet` | `bool` | Whether to include network IOC stage |
| `aiBriefText` / `aiDetailedText` | `str` | Groq AI output (written to `window._scanAiBriefText` for AiReport page) |
| `explainData` | `var` | `AiExplanation` dict for the explain panel |

**URL scan state:**

| Property | Type | Purpose |
|---|---|---|
| `urlInput` | `str` | User-entered URL |
| `urlResult` | `var` | Normalized URL scan result dict |
| `urlScanning` / `urlPct` / `urlStage` | `bool/int/str` | Progress binding |
| `urlOptSandbox` / `urlOptBlockDl` / `urlOptBlockPvt` | `bool` | Scan options |

**Helper functions:**

- `riskColor(risk)` — maps verdict string to `ThemeManager.danger/warning/success/muted` color token
- `fmtSize(bytes)` — formats bytes to human-readable `"1.23 MB"` / `"456 KB"` / `"789 B"`
- `hasSandboxWarnPhase()` — checks `phaseModel` list for any sandbox phase with `status === "warn"`

**Integration status:** Calls `backend.refreshIntegrationStatus()` exactly once per page open (`integrationStatusLoaded` guard) to probe ClamAV availability without spamming subprocess calls.

**Backend signal connections:**

- `Backend.scanCenterProgress` → updates `filePct` and `fileStage`
- `Backend.scanCenterFinished` → writes `fileReport`, clears `fileScanning`
- `Backend.scanCenterAiBrief` → writes `aiBriefText` and `window._scanAiBriefText`
- `Backend.scanCenterAiDetailed` → writes `aiDetailedText`
- `Backend.scanCenterFailed` → clears `fileScanning`, shows toast
- `Backend.scanCenterPhaseUpdate` → parses JSON and appends to `phaseModel` ListModel
- `Backend.scanCenterPreviewUpdated` → updates sandbox live preview image source

---

### SystemMonitor.qml

**Live metric properties (updated by `ResourceMonitor` signals):**

- `cpuPercent`, `ramPercent`, `ramUsedGb`, `ramTotalGb` — system utilization
- `netSentMbps`, `netRecvMbps` — network throughput
- `diskPercent` — primary disk usage
- `monitorRunning` — whether `ResourceMonitor` is active

**RTP state properties** (full granularity):

- `rtpEnabled`, `rtpCapabilityState`, `rtpCapabilityDetail`
- `rtpConfiguredEnabled` — persisted preference (may differ from runtime state)
- `rtpMonitoringState` — `"running"/"starting"/"disabled"/"blocked"/"unsupported"`
- `rtpProcessScannerState` — scanner-level state within the monitor
- `rtpRuntimeDetail` — full diagnostic string from `RTPBridge.getRuntimeDetail()`
- `rtpAvailable` — shorthand bool for UI guard conditions

**Log console:** `ListModel { id: logModel }` holds up to `maxLogEntries: 200` lines, prepended on each new `RTPBridge.new_event_log` signal. Entries are formatted as `"[HH:MM:SS] RTP: Allowed/Flagged/Blocked <process> (PID: N)"`.

**Color helpers:**

- `statusColor(value)` — returns `ThemeManager.danger` (>90%), `warning` (>70%), or `success`
- `formatMbps(val)` — formats to `"X.XX MB/s"`, `"NNN KB/s"`, or `"0 B/s"`

**GPU service link:** `ResourceMonitor.start()` is called when the page becomes visible and the service is not yet running. A 2-second poll timer also syncs `monitorRunning` from `ResourceMonitor.getIsRunning()`.

---

### EventViewer.qml

**State model:**

- `eventModel: []` — raw event list (from `Backend.loadEvents()`)
- `filteredModel: []` — client-side filtered view (recomputed on `searchText` / `levelFilter` change)
- `selectedEvent` / `selectedEventIndex` — currently expanded event
- `levelFilter` — `"All"/"ERROR"/"WARNING"/"INFO"/"CRITICAL"`
- `searchText` — filters on `source`, `message`, and `event_id`

**AI state:**

- `explanationMode` — `"none"/"brief"/"detailed"` — controls which AI panel is shown
- `aiBusy` — spinner guard during AI request
- `aiData` — full `AiExplanation` dict from `Backend.eventExplanationReady`
- `briefData` — short preview from `Backend.eventPreviewReady`

**Filter logic (`filterEvents()`):** Pure client-side filtering — all `N` loaded events are in memory. Converts level names to uppercase for case-insensitive comparison and handles the alias `"INFORMATION"` → `"INFO"`. Search matches on `source`, `message`, and `event_id` substrings.

**Level color helper (`getLevelColor(level)`):** Maps to `ThemeManager.danger` (error/critical), `ThemeManager.warning`, or `ThemeManager.info` (all others).

**Backend signal connections:**

- `Backend.eventsLoaded` → writes `eventModel`, calls `filterEvents()`
- `Backend.eventExplanationReady` → writes `aiData`, sets `explanationMode = "detailed"`
- `Backend.eventExplanationFailed` → writes `aiError`, clears `aiBusy`
- `Backend.eventPreviewReady` → writes `briefData`, sets `explanationMode = "brief"`

---

### HistoryPage.qml

**Four-tab interface:**

| Tab Index | Key | Label | Data source |
|---|---|---|---|
| 0 | `scan` | Scan History | `Backend.getUnifiedScanHistory(200)` |
| 1 | `incidents` | RTP / Incident History | `Backend.getIncidentHistory(200)` |
| 2 | `quarantine` | Quarantine History | `Backend.getQuarantineHistory()` |
| 3 | `url` | URL Scan History | `Backend.getUrlScanHistory(200)` |

**Navigation routing:** The page accepts a `requestedTab` property set by `main.qml` route aliases (`"history-scan"`, `"history-incidents"`, `"history-quarantine"`, `"history-url"`). `applyRequestedTab()` maps the string key to the numeric `currentTab` index.

**Quarantine workflow:**

- `pendingQuarantineItem` / `pendingQuarantineAction` — hold the item and action (`"restore"/"delete"`) while a confirmation dialog is open
- `quarantineActionResult` — stores the backend result dict `{ok, message}` for the result dialog
- Actions call `Backend.restoreQuarantineItem(id)` or `Backend.deleteQuarantineItem(id)` and refresh on signal

**Refresh strategy:** `refreshAll()` fetches all four tabs on page open. `refreshCurrentTab()` refreshes only the active tab after a quarantine action to avoid unnecessary DB reads.

---

### GPUMonitor.qml

**GPU selection:** `selectedGpuIndex` (`int`) controls which GPU's data is displayed when multiple GPUs are present. Bound to `GPUService.currentGpuIndex`.

**Lazy-start GPU service:** Three hooks ensure GPU monitoring starts exactly once regardless of timing:

1. `Component.onCompleted` — if page was created while already visible
2. `onVisibleChanged` — normal first-open via navigation
3. `onGpuServiceAvailableChanged` — if `GPUService` was registered after the page was already open (deferred 1000ms init)

Calls `GPUService.start(1000)` — the argument is the polling interval in milliseconds.

**Metric status system:** Each GPU metric has an associated status key in `metricStatus{}`. Helper functions:

- `_gpuMetricStatus(obj, key)` → `"ok"/"unavailable"/"unsupported"/"permission_denied"/"not_exposed"/"backend_error"/"shared_memory"`
- `_gpuMetricText(obj, key, decimals, suffix)` → either the formatted number (e.g. `"72°C"`) or the status label (e.g. `"Permission required"`)
- `_gpuMetricNumber(obj, key)` → `null` when status is not `"ok"`, otherwise the `Number`
- `_gpuMemoryText(obj, key, decimals)` → formatted VRAM string

This means every metric card gracefully shows `"Unavailable"` / `"Unsupported"` / `"Permission required"` instead of blank or `NaN` when a sensor cannot be read — consistent with the graceful degradation model used throughout the application.

---

### SettingsPage.qml

**Reactive sync from `SettingsService`:** All settings controls (`themeModeCombo`, `fontSizeCombo`, `startupSwitch`, `minimizeToTraySwitch`, `gpuSwitch`, `intervalSpinner`) implement `reloadFromService()` / `reloadThemeMode()` / `reloadFontSize()` functions called via `Connections { target: SettingsService }` on each relevant signal. This means if the settings change via code (e.g. `--reset-settings` CLI), the UI reflects it instantly.

**Sections rendered as cards:**

1. **Appearance** — theme mode combo (`dark`/`light`/`system`), font size combo (`small`/`medium`/`large`)
2. **Behavior** — close-to-tray switch, start minimized switch, start-with-system switch (Windows only, hidden on Linux via `SettingsService.supportsAutostart`)
3. **Performance** — GPU monitoring switch, update interval spinner (500ms–10000ms)
4. **Security / AI** — Groq API key input field (masked display via `groqApiKeyMasked`), "Test Connection" button (`testGroqConnection()` → `groqTestResult` signal updates status label), "Save" button (`saveGroqApiKey()`)
5. **Advanced** — "Reset to Defaults" button with confirmation dialog

All sections use `ThemeManager.panel()`, `ThemeManager.border()`, `ThemeManager.foreground()`, `ThemeManager.muted()` color tokens to automatically adapt to dark/light mode.

---

## 22. Release History (CHANGELOG)

**File:** `CHANGELOG.md`

Sentinel follows an honest, single-file changelog with one released version.

---

### [1.0.0] — 2026-04-22

#### Release Hardening

- **Scan score/verdict/enforcement alignment:** RTP and the Scan Center UI now consume the same normalized `FinalDecision` object, eliminating cases where the UI could show a different verdict than what the enforcement engine acted on.
- **Windows RTP fix:** Process launch monitoring was silently dropping live scan activity events; now all monitored process scan outcomes are surfaced in the RTP log and System Monitor console.
- **RTP preference persistence:** The enabled/disabled toggle now follows the user's last explicit action. First-run default is `enabled`. No longer resets on every launch.
- **ClamAV status normalization:** Linux, UI, and runtime paths previously disagreed about whether ClamAV was installed. Now all three paths share a single normalization function (`get_clamav_status()` in `infra/integrations.py`).
- **Security posture truthfulness:** The System Snapshot page now separates real `On`, `Off`, `Unknown`, `Unavailable`, and `Degraded` states for every security control, instead of collapsing them to `On/Off`.

#### Cross-Platform Behavior

- **Linux RTP honesty:** Linux Real-Time Protection is now explicitly documented and reported in the UI as "process-polling implementation" (not WMI). The capability detail string reflects this.
- **Windows-only controls:** Defender, UAC, TPM, and VMware Sandbox controls are no longer shown on Linux — they display as `Unsupported` rather than being faked or hidden.
- **Runtime path standardization:** Platform-native paths (`%APPDATA%` on Windows, `$XDG_DATA_HOME` on Linux) are favored, with a legacy fallback that reads from the old location if the new one doesn't exist yet.

#### Diagnostics & Supportability

- **Honest degraded reporting:** `--diagnose` now explicitly marks degraded optional dependencies (e.g. ClamAV missing, Nmap not found, GROQ_API_KEY not set) rather than presenting partial capability as fully healthy.
- **Exported diagnostics:** `--export-diagnostics out.json` produces a local JSON file with feature-level availability details, suitable for bug reports and remote support.
- **Documented runtime paths:** Crash logs, application logs, and the SQLite database path are all surfaced through the platform path layer and shown in `--diagnose` output.

#### Packaging & Release Notes

- **Linux build script:** `scripts/build/build_linux.sh` now uses repo-relative paths instead of hardcoded `D:\` drive letters, making it portable across development machines.
- **Documentation accuracy:** Release-facing docs were corrected to reflect the current Groq-only AI runtime (not OpenAI/Anthropic), current platform support matrix, and current runtime path behavior.
- **Release checklist:** `docs/releases/FINAL_RELEASE_CHECKLIST.md` added with explicit Windows and Linux validation steps.

#### Known Limitations Carried into This Release

| Item | Status |
| --- | --- |
| VMware sandbox detonation | Windows-only; no Linux equivalent |
| Linux Event Viewer | Depends on `journalctl`; does not emulate Windows Event Log semantics |
| Installer format | No MSI, DEB, or RPM installer; portable build / source distribution only |
| Central management | No policy server, SIEM integration, or multi-endpoint dashboard |
| Linux RTP depth | User-space psutil polling only; kernel-level hooks not implemented |

---

## Summary: What Makes Sentinel Technically Notable

1. **Process-isolated architecture** — three dedicated subprocesses (GPU, URL detonator, Sandbox Agent) with custom IPC protocols keep the UI permanently fluid.
2. **Native OS integrations** — WMI event watching, direct sysfs reads, journalctl parsing — no generic wrappers.
3. **AI-safe enforcement** — deterministic scoring guards prevent LLM hallucinations from causing false-positive process kills.
4. **Truthful platform boundaries** — every capability explicitly reports its availability status; nothing is silently swallowed or fabricated.
5. **Production-grade patterns** — dependency injection, repository pattern, WAL-mode SQLite, deferred initialization, circuit breakers, and a comprehensive pytest regression suite.
6. **Dual-platform parity** — feature-equivalent implementations for both Windows and Linux, each using the deepest available OS integration rather than the lowest common denominator.
7. **Complete QML ↔ Python signal contract** — 40+ typed signals on `BackendBridge` alone, every one documented with payload type and purpose. All scan results are normalized before emission so QML never receives `undefined` keys.
8. **Settings hot-swap** — Groq API key changes, theme changes, and font changes all take effect immediately without a restart, implemented through QSettings signals propagated to both the Python `QApplication` and QML `ThemeManager`.

---

*Report generated from source analysis of Sentinel v1.0.0 — branch `main` — 2026-05-13*
