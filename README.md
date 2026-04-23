# Sentinel — Endpoint Security Suite

Sentinel is a cross-platform desktop endpoint security application built with **PySide6/QML** and **Python**. It provides real-time system telemetry, security posture assessment, event log analysis, file scanning, sandbox detonation, network scanning, and AI-assisted threat analysis with explicit degraded-mode reporting and truthful platform capability boundaries.

---

## Table of Contents

- [Features](#features)
- [Platform Support](#platform-support)
- [Technology Stack](#technology-stack)
- [Pages and UI](#pages-and-ui)
- [Feature Detail](#feature-detail)
  - [System Snapshot](#system-snapshot)
  - [GPU Monitor](#gpu-monitor)
  - [Event Viewer](#event-viewer)
  - [Scan Center](#scan-center)
  - [Sandbox Lab](#sandbox-lab)
  - [File Function](#file-function)
  - [Network Scan](#network-scan)
  - [Real-Time Protection](#real-time-protection)
  - [AI Analysis](#ai-analysis)
  - [Security Posture](#security-posture)
- [Quick Start](#quick-start)
- [Optional Providers and Degraded Mode](#optional-providers-and-degraded-mode)
- [Runtime Paths](#runtime-paths)
- [Architecture](#architecture)
- [Diagnostics](#diagnostics)
- [Testing](#testing)
- [Current Boundaries](#current-boundaries)
- [Documentation](#documentation)
- [License](#license)

---

## Features

| Feature | Windows | Linux |
| --- | --- | --- |
| System Snapshot (CPU, RAM, Storage, Network) | Yes | Yes |
| GPU Monitor - NVIDIA | Yes | Yes |
| GPU Monitor - AMD | Yes | Yes (native sysfs, no ROCm required) |
| GPU Monitor - Hybrid multi-GPU laptop | Yes | Yes |
| Event Viewer (system event logs) | Windows Event Log | systemd journal |
| Security Posture Assessment | Yes | Yes |
| File Scanning (static + AI NGAV) | Yes | Yes |
| ClamAV Integration | Yes | Yes |
| Sandbox Detonation (VMware) | Yes | No |
| File Shredding (secure delete) | Yes | Yes |
| File Carving / Recovery | Yes | Yes |
| Network Scan (Nmap) | Yes | Yes |
| URL Scanning | Yes | Yes |
| Real-Time Process Protection | Yes (WMI watcher) | Yes (process polling) |
| AI Analysis (Groq) | Yes | Yes |
| AI Security Chatbot | Yes | Yes |
| Quarantine Manager | Yes | Yes |
| XDG Runtime Paths | No | Yes |
| Scan History (SQLite) | Yes | Yes |

---

## Platform Support

### Windows

- Full feature set including VMware sandbox, Real-Time Protection (WMI process monitoring), Windows Event Log, Windows Defender and UAC integration
- GPU monitoring via ADL SDK (AMD) and NVML/nvidia-smi (NVIDIA)
- AppData-based runtime paths
- Portable PyInstaller packaging is supported; validate the packaged build on a clean Windows machine before publishing

### Linux

- First-class support for system snapshot, GPU monitoring, security posture, file scanning, network scanning, event logs, AI analysis, and Real-Time Protection via process polling
- GPU monitoring via native sysfs/DRM (AMD, no ROCm required), NVML/nvidia-smi (NVIDIA), and a hybrid-laptop supplement that detects GPUs via DRM and lspci regardless of driver state
- Event logs via `journalctl` presented through the shared Event Viewer UI with normalized fields
- Security posture via `ufw`, `iptables`, `firewalld`, `nftables`, ClamAV, AppArmor, SELinux, `mokutil`
- XDG-compliant runtime paths
- VMware sandbox is not available on Linux

---

## Technology Stack

### Core Framework

| Technology | Version | Purpose |
| --- | --- | --- |
| Python | 3.11+ | Application runtime |
| PySide6 (Qt 6) | ≥ 6.6.0 | GUI framework — QML engine, signals/slots, QProcess |
| psutil | ≥ 5.9.0 | Cross-platform CPU, RAM, disk, network, process metrics |
| SQLite 3 | stdlib | Scan history, events database (WAL mode, indexed) |
| python-dotenv | ≥ 1.0.0 | `.env` API key and config management |

### AI / LLM Providers

| Provider | Model | Use |
| --- | --- | --- |
| Groq (required for AI features) | `llama-3.3-70b-versatile` | Event explanation, deep threat analysis |
| Groq (required for AI features) | `llama-3.1-8b-instant` | Security chatbot, fast interactive queries |

> AI features require a `GROQ_API_KEY` set in the `.env` file. Without it, event explanations, AI scan summaries, and the security chatbot will be unavailable. All non-AI features (scanning, monitoring, event log, network scan) work offline.

- Rate limiting: 30 req/min with 2 s minimum interval
- Retry: 3 attempts with exponential backoff (1 s → 30 s)
- Privacy engine: strips IPs, usernames, file paths before sending to AI

### GPU Monitoring

| Technology | Platform | Provider |
| --- | --- | --- |
| `nvidia-ml-py` (NVML) | Windows + Linux | NVIDIA primary — full metrics |
| `nvidia-smi` CLI | Windows + Linux | NVIDIA fallback when NVML absent |
| `pyadl` (AMD ADL SDK) | Windows / WSL | AMD primary on Windows |
| Linux DRM sysfs | Linux | AMD primary — `/sys/class/drm/card*/device/` |
| hwmon sysfs | Linux | AMD temperature, power, fan |
| `/sys/module/amdgpu/version` | Linux | AMD driver version |
| `lspci` | Linux | GPU name resolution + hybrid supplement |
| DRM card enumeration | Linux | Detects all vendors regardless of driver state |

### Windows-Only Technologies

| Technology | Purpose |
| --- | --- |
| `pywin32` (win32evtlog, win32con) | Windows Event Log reading |
| `WMI` | Process creation monitoring (Real-Time Protection), system inventory |
| VMware Workstation + `vmrun` CLI | Sandbox detonation and live preview |
| `pefile` | PE (Portable Executable) binary static analysis |
| `imageio[ffmpeg]` | Sandbox live video capture (GIF/MP4) |
| `pywebview` | URL detonation in isolated WebView2 |

### Linux-Only Technologies

| Technology | Purpose |
| --- | --- |
| `journalctl` (systemd) | System event log collection |
| `ufw` / `firewalld` / `nftables` / `iptables` | Firewall status detection |
| `clamscan` / `clamd` | ClamAV antivirus and real-time scanner |
| `mokutil` | Secure Boot state |
| `aa-status` | AppArmor enforcement state |
| `getenforce` | SELinux enforcement state |
| `lspci` | PCI GPU enumeration (hybrid laptop detection) |
| `/sys/class/drm/` | DRM GPU enumeration |
| `/sys/class/drm/cardN/device/hwmon/` | AMD temperature, power, fan sensors |
| `modinfo amdgpu` | AMD kernel module version |

### Scanning and Security Engines

| Technology | Purpose | Platform |
| --- | --- | --- |
| Groq AI NGAV | AI-powered Next-Gen AV analysis | Both |
| `pefile` | PE static analysis (imports, entropy, suspicious indicators) | Windows |
| ClamAV (`clamscan`) | Signature-based antivirus | Both |
| Nmap CLI | Network host, port, OS, and service discovery | Both |
| VirusTotal API (optional) | External threat intelligence | Both |
| Google Safe Browsing API (optional) | URL reputation | Both |
| SHA-256 / MD5 | File integrity hashing | Both |

### Build and Tooling

| Tool | Version | Purpose |
| --- | --- | --- |
| PyInstaller | ≥ 6.0.0 | Standalone binary packaging |
| Ruff | ≥ 0.1.0 | Linting and formatting |
| MyPy | ≥ 1.0.0 | Static type checking |
| Bandit | ≥ 1.7.0 | Security linting |
| pytest + pytest-qt | ≥ 8.0.0 | Unit and integration testing |

---

## Pages and UI

| Page | Description |
| --- | --- |
| **Home** | Security health dashboard — threat status, quick stats, system overview |
| **System Monitor** | Real-time charts for CPU, RAM, disk I/O, and network throughput |
| **GPU Monitor** | NVIDIA / AMD GPU telemetry — usage, temperature, power, VRAM, clocks, fan, PCIe; multi-GPU navigation |
| **Event Viewer** | Windows Event Log (Windows) or systemd journal (Linux) — filtered event list with AI-powered explanations |
| **Scan Center** | File scanning — drag-and-drop, multi-engine analysis, verdict scoring, scan history |
| **Sandbox Lab** | VMware Workstation detonation — live desktop preview, process/file/network delta report (Windows only) |
| **File Function** | Secure file shredding (3-pass) and forensic file carving/recovery |
| **Network Scan** | Nmap-based host discovery, port scan, OS detection, service version, vulnerability scan |
| **Security Assistant** | Groq-powered AI chatbot for interactive threat queries and remediation guidance |
| **AI Report** | AI-generated explanation of scan findings with actionable recommendations |
| **System Snapshot** | Full system inventory across six sub-pages: Overview, Hardware, OS Info, Security, Network, Adapters |
| **History** | Unified scan history, incident history, quarantine records, security events, and URL scan history |
| **Settings** | UI preferences, telemetry refresh, startup behavior, tray behavior, and local diagnostics guidance |

---

## Feature Detail

### System Snapshot

Six tabbed sub-pages covering complete system state:

- **Overview** — OS name, version, hostname, uptime, logged-in user, domain
- **Hardware** — CPU model, core/thread count, RAM capacity, disk geometry, GPU specs
- **OS Info** — Kernel/build version, patch level, install date, architecture
- **Security** — Firewall status, antivirus presence, Secure Boot, disk encryption, remote access exposure, AppArmor/SELinux (Linux)
- **Network** — IP addresses, DNS servers, default gateway, routing table
- **Adapters** — NIC name, MAC, link speed, driver, duplex mode

Storage view filters pseudo-filesystems, loop mounts, Snap `squashfs` images, and container overlays by default. A debug toggle in the storage section exposes all mounts for advanced inspection.

---

### GPU Monitor

Real-time GPU telemetry with rolling 60-point history charts.

**Collected metrics:**

| Metric | AMD (Linux sysfs) | NVIDIA (NVML/nvidia-smi) |
| --- | --- | --- |
| GPU utilization % | `gpu_busy_percent` | NVML utilization rates |
| GPU temperature °C | `hwmon/temp1_input` | NVML temperature sensor |
| Power draw W | `hwmon/power1_average` | NVML power usage |
| Fan speed % | `hwmon/pwm1` (0–255) | NVML fan speed |
| Fan RPM | `hwmon/fan1_input` | — |
| VRAM used / total | `mem_info_vram_*` | NVML memory info |
| Core clock MHz | — | NVML clock (graphics) |
| Memory clock MHz | — | NVML clock (memory) |
| PCIe Gen / Width | — | NVML PCIe info |
| Encoder / Decoder % | — | NVML encoder/decoder |
| Driver version | `/sys/module/amdgpu/version` | NVML system driver |
| GPU name | `lspci -s <pci> -nn` | NVML device name |

**Metric availability states** — no metric ever shows a fake `0` value:

| State | UI label | Meaning |
| --- | --- | --- |
| `ok` | Live | Metric actively collected |
| `unsupported` | Unsupported | Hardware or driver does not expose this |
| `unavailable` | Unavailable | Metric expected but could not be read |
| `not_exposed` | Not exposed | Sensor exists but driver does not surface it |
| `permission_denied` | Permission required | Elevated privileges needed |
| `backend_error` | Backend error | Query failed with an error |
| `shared_memory` | Shared memory | AMD iGPU/APU — no dedicated VRAM |

**Hybrid laptop detection (Linux):** Three-layer detection ensures both GPUs appear with navigation arrows:
1. Primary — pynvml (NVIDIA) / amdgpu sysfs (AMD)
2. Vendor fallback — nvidia-smi (when pynvml absent), pyadl (WSL/Windows)
3. DRM supplement — scans `/sys/class/drm` for any driver-loaded GPU not yet found
4. lspci supplement — scans PCI bus for GPUs with no driver loaded at all (PRIME power-off mode)

---

### Event Viewer

Unified event log viewer with a shared interface on both platforms.

**Windows** — reads from Windows Event Log via `pywin32` (`win32evtlog`):
- Sources: System, Application, Security channels
- Parses Event ID, level, source, timestamp, message
- Built-in Event ID knowledge base with 73+ known event types
- Human-readable friendly message generation

**Linux** — reads from systemd journal via `journalctl --output=json`:
- Sources: all unit logs (equivalent to System + Application)
- Priority mapping: Emergency/Alert/Critical/Error/Warning/Notice/Info/Debug → standardized levels
- Same `EventItem` schema as Windows for UI consistency
- Handles binary/non-UTF-8 journal data safely

Both platforms support:
- Level filtering (Critical, Error, Warning, Information)
- Up to 200 events per query
- **AI-powered event explanation** via Groq — each event can be explained in plain English with severity assessment and remediation steps

---

### Scan Center

Multi-engine file scanning pipeline with 11 sequential stages:

1. Input validation and file access check
2. Hash computation (SHA-256, MD5) and file metadata collection
3. PE header analysis — imports, exports, sections, entropy, suspicious indicators (`pefile`)
4. String extraction — up to 200 meaningful strings, IOC detection
5. **Groq AI NGAV** — behavioral analysis prompt with static indicators
6. ClamAV signature scan (if installed and in PATH)
7. Signature verification (Authenticode on Windows)
8. IOC extraction — embedded IPs, domains, URLs
9. Verdict scoring — deterministic aggregation (no LLM for final verdict)
10. Optional VMware sandbox detonation (Windows only)
11. Report generation (JSON) and SQLite history insert

**Supported file types:** All files for static analysis. PE-specific deep analysis for `.exe`, `.dll`, `.sys`, `.scr`, `.com`, `.pif`, `.msi`.

---

### Sandbox Lab

Dynamic malware detonation using **VMware Workstation** — Windows only.

**Workflow:**
1. Restore VM to clean snapshot
2. Copy sample into guest via `vmrun copyFileFromHostToGuest`
3. Execute detonation script inside guest (PowerShell)
4. Capture live desktop screenshots every 500 ms (12 frames max)
5. Collect before/after deltas: running processes, created files, network connections
6. Parse `summary.json` from guest
7. Render results in Sandbox Lab page with live video preview

**Configuration (environment variables):**
```
VMRUN_PATH     Path to vmrun.exe
VMX_PATH       Path to .vmx VM image
VM_SNAPSHOT    Snapshot name to restore (default: "Clean Base")
VM_GUEST_USER  Guest OS username
VM_GUEST_PASS  Guest OS password
```

**Not available on Linux** — VMware Workstation and vmrun.exe are Windows-only dependencies.

---

### File Function

Two independent capabilities:

**Secure File Shredding:**
- 3-pass overwrite: random bytes → random bytes → zeros
- File renamed to random 16-character string before deletion (destroys MFT/directory record)
- Works on both Windows (NTFS) and Linux (ext4, btrfs, etc.)
- Non-blocking — runs on Qt thread pool with progress reporting

**Forensic File Carving / Recovery:**
- Sector-by-sector scan of a disk or partition image
- Magic number detection for JPEG, PNG, PDF (header + footer matching)
- Sector size: 512 bytes; carved file cap: 20 MiB per file
- Recovered files written to platform recovery directory

---

### Network Scan

Nmap-backed host and service discovery.

**Scan profiles:**

| Profile | Nmap flags | Description |
| --- | --- | --- |
| Host discovery | `-sn` | Live host ping sweep |
| Network map | `-sn --traceroute` | Host discovery + route tracing |
| Port scan | `-sS` / `-sT` | SYN scan (root) or TCP connect (unprivileged) |
| OS detection | `-O` | Operating system fingerprinting |
| Service version | `-sV` | Service and version identification |
| Vulnerability scan | `--script vuln` | NSE vulnerability scripts |
| Firewall detection | `-f --data-length` | Firewall/IDS probing |

On Linux without root, SYN scan automatically falls back to TCP connect scan. Full OS detection and SYN scan require root.

**URL scanning** — separate pipeline:
- Offline heuristics: blocklist matching, typosquatting detection, suspicious TLD check
- HTTP content fetch and analysis
- Optional VirusTotal and Google Safe Browsing API integration
- AI classification via Groq

---

### Real-Time Protection

Continuous process monitoring that scans newly launched processes and can terminate them when the final enforcement decision requires blocking.

**How it works:**
1. Windows uses a WMI watcher for `Win32_Process.__InstanceCreation`
2. Linux uses process polling to detect newly launched executables
3. New process PID and executable path are captured
4. Static scanner plus optional Groq AI NGAV analysis runs on the executable
5. Enforcement uses the normalized final decision object:
   - `allow` -> log only
   - `block` -> terminate the process and log the incident

**ThreatEvent data:** PID, process name, executable path, matched rules, threat score (0–100), action taken, timestamp, SHA-256.

Platform note:
- Windows RTP depends on `pywin32` and `wmi`
- Linux RTP depends on `psutil`
- The UI reports configured state separately from runtime health so a saved preference is never confused with a running monitor

---

### AI Analysis

**Groq integration:**
- Primary model `llama-3.3-70b-versatile` for deep event explanation and threat analysis
- Faster model `llama-3.1-8b-instant` for interactive chatbot queries
- Offline knowledge base fallback when API is unavailable

**Privacy engine:** Automatically redacts IP addresses, usernames, file paths, and other sensitive identifiers from all data sent to AI providers.

**AI features:**
- **Event explanation** — plain-English summary of any Event Viewer / journalctl entry with severity rating and remediation steps
- **Security chatbot** — interactive threat query interface
- **Scan report explanation** — detailed narrative of scan findings with actionable recommendations
- **URL threat classification** — human-readable verdict with confidence score

Groq is the only cloud AI provider currently wired into the application. If `GROQ_API_KEY` is not set, cloud AI features stay unavailable and the app falls back to local/non-AI behavior where implemented.

---

### Security Posture

Platform-native checks with three-state indicators: good (green) / warning (amber) / bad (red).

**Windows checks:**
- Windows Defender status — real-time protection, tamper protection, behavior monitoring, signature age, last scan time
- Windows Firewall — Domain, Private, and Public profile states
- UAC level
- TPM presence
- Secure Boot state

**Linux checks:**
- Firewall — `ufw status verbose`, `iptables -L`, `firewalld`, `nftables` (first found is used)
- Antivirus — ClamAV: daemon active (Realtime active) vs. scanner-only vs. not installed
- Secure Boot — `mokutil --sb-state`
- Disk encryption — backing device detection for root and home
- Package updates — pending security updates via package manager
- Remote access exposure — open SSH, RDP, VNC ports
- Mandatory access control — AppArmor (`aa-status`) or SELinux (`getenforce`)

---

## Quick Start

### Requirements

- Python 3.11+
- Git
- PySide6-compatible desktop environment

### Optional tools that improve coverage

| Tool | Purpose | Platform |
| --- | --- | --- |
| Groq API key | AI event explanation, chatbot, scan reports | Both |
| Nmap | Network scanning | Both |
| ClamAV (`clamscan` / `clamd`) | Signature-based file scanning | Both |
| `pynvml` / `nvidia-smi` | NVIDIA GPU telemetry | Both |
| `rocm-smi` | AMD GPU telemetry (alternative to sysfs) | Linux |
| `ufw` / `firewalld` | Firewall posture reporting | Linux |
| `mokutil` | Secure Boot state | Linux |
| `aa-status` | AppArmor enforcement state | Linux |
| VMware Workstation + vmrun | Sandbox detonation | Windows |

### Windows

```powershell
git clone https://github.com/mahmoudbadr238/graduationp.git
cd graduationp

python -m venv .venv
.venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt

python -m backend --diagnose
python main.py
```

### Linux

```bash
git clone https://github.com/mahmoudbadr238/graduationp.git
cd graduationp

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
pip install -r linux_requirements.txt

python -m backend --diagnose
python main.py
```

Use [run_linux.sh](run_linux.sh) to set up a Linux dev environment automatically, and [build_linux.sh](build_linux.sh) to create a PyInstaller build.

### Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_key              # enables Groq-backed AI features

# Windows sandbox (optional)
VMRUN_PATH=C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe
VMX_PATH=D:\vm\windows10\Windows 10 x64.vmx
VM_SNAPSHOT=Clean Base
VM_GUEST_USER=IEUser
VM_GUEST_PASS=Passw0rd!
```

---

## Optional Providers and Degraded Mode

Sentinel stays fully usable when optional tools are absent:

| Missing tool | Behavior |
| --- | --- |
| No GPU backend | GPU page shows device name, all metrics marked Unavailable/Unsupported — no fake `0%` |
| No Groq API key | Groq-backed AI features stay unavailable; non-AI features continue working |
| No ClamAV | Scan Center skips ClamAV engine; Groq NGAV and static analysis still run |
| No Nmap | Network Scan page shows "Nmap not found" — other features unaffected |
| No firewall tool (Linux) | Security page reports "No supported firewall stack detected" |
| No `mokutil` (Linux) | Secure Boot shown as Unavailable |
| VMware not configured | Sandbox Lab page disabled; all other scan engines still run |
| No NVML on Linux | NVIDIA detected via nvidia-smi fallback, then DRM/lspci if also absent |

---

## Runtime Paths

| Type | Windows | Linux |
| --- | --- | --- |
| Config | `%APPDATA%\Sentinel` | `$XDG_CONFIG_HOME/sentinel` |
| Data | `%APPDATA%\Sentinel` | `$XDG_DATA_HOME/sentinel` |
| Logs | `%APPDATA%\Sentinel\logs` | `$XDG_STATE_HOME/sentinel/logs` |
| Crash logs | `%APPDATA%\Sentinel\crashes` | `$XDG_STATE_HOME/sentinel/crashes` |
| Quarantine | `%PROGRAMDATA%\Sentinel\Quarantine` | `$XDG_DATA_HOME/sentinel/quarantine` |
| Scan reports | `%APPDATA%\Sentinel\scan_reports` | `$XDG_DATA_HOME/sentinel/scan_reports` |
| Database | `%APPDATA%\Sentinel\sentinel.db` | `$XDG_DATA_HOME/sentinel/sentinel.db` |

Sentinel keeps legacy compatibility lookups for older locations such as `~/.sentinel` so existing local data remains readable after upgrade.

---

## Architecture

```text
backend/
  api/              QML-facing services and bridges
                      GPUServiceBridge — QProcess worker, heartbeat watchdog, circuit breaker
                      BackendBridge — scanning, AI, network, snapshot APIs
                      SnapshotService — pre-warmed system and security caches
  core/             Config, logging, DI container, startup, performance monitor
  engines/
    ai/             Groq provider, event explainer, chatbot, report
    filefunction/   Secure delete (3-pass), file carving/recovery
    sandbox_vmware/ VMware Workstation detonation (Windows only)
    scancenter/     11-stage multi-engine scan pipeline
    scanning/       URL scanner, quarantine manager, report writer
  infra/            Nmap CLI, SQLite repository, optional integration helpers
  platform/
    paths.py        XDG / AppData cross-platform path resolver
    linux/          All Linux-specific implementations (see below)
  tests/            Automated tests (27+ cases for Linux GPU and posture)
  utils/            Secure delete, logging utilities

backend/platform/linux/
  drm_enumeration.py       /sys/class/drm card scanner — vendor, driver, PCI address
  amd_sysfs_provider.py    AMD GPU metrics from sysfs/hwmon (no ROCm required)
  gpu_normalization.py     Cross-vendor metric normalization with status system
  telemetry_worker.py      GPU telemetry subprocess (JSON-line protocol)
  events_linux.py          journalctl event reader — same interface as Windows
  security_posture.py      UFW, iptables, ClamAV, AppArmor, SELinux detection
  security_snapshot.py     Security state snapshot for System Snapshot page
  system_monitor_psutil.py psutil-based CPU, RAM, disk, network metrics
  system_snapshot_service.py Hardware and OS inventory
  secure_delete.py         3-pass file shredding on Linux filesystems
  storage.py               SQLite with XDG paths
  admin.py                 Root privilege detection and graceful degradation

frontend/qml/
  components/       Shared QML components (cards, dialogs, chart widgets)
  pages/            Top-level application pages
  ui/ theme/        ThemeManager — color tokens, typography, spacing
```

**Key service patterns:**

- **GPUServiceBridge** — spawns the platform telemetry worker as a `QProcess`, parses newline-delimited JSON, maintains 60-point rolling deque per metric, implements 60 s heartbeat watchdog and 3-fault circuit breaker
- **Subprocess isolation** — GPU worker, URL detonator, and sandbox runner all execute in child processes so a crash never blocks the UI
- **Provider degraded mode** — every optional integration has an explicit unavailable/unsupported state reported to QML rather than a silent failure

---

## Diagnostics

```bash
python -m backend --diagnose
python -m backend --export-diagnostics diagnostics.json
python -m backend --reset-settings
```

Diagnostics validate optional integrations, runtime paths, database connectivity, and degraded provider state before the UI starts. Run them first when troubleshooting.

---

## Testing

**Windows:**
```powershell
.venv\Scripts\python -m pytest backend/tests -q
```

**Linux:**
```bash
.venv/bin/python -m pytest backend/tests -q
```

Test coverage includes:

- DRM GPU enumeration — connector filtering, vendor/driver reads, iGPU class detection, multi-card
- AMD sysfs provider — discrete VRAM, iGPU shared-memory, hwmon temperature/power/fan, missing hwmon
- GPU metric normalization — status preservation (`shared_memory`, `permission_denied`), key mapping, provider status, regression guards for Windows NVIDIA payloads
- Linux storage filtering — pseudo-filesystem exclusion, loop device exclusion, debug toggle
- Cross-platform runtime path selection
- Linux security posture mapping

---

## Current Boundaries

These are intentionally out of scope on Linux at the moment:

| Capability | Status |
| --- | --- |
| VMware sandbox detonation | Windows only — requires vmrun.exe |
| Windows Defender / UAC / TPM integration | Windows only |
| Linux Event Viewer source | systemd journal only — requires `journalctl` |
| Central management / policy server | Not included in this release |
| Native installer packages | Portable/CLI build flow only — no MSI, DEB, or RPM installer in this repo |

Sentinel reports unavailable or unsupported states instead of pretending these controls exist.

---

## Documentation

- [docs/QUICKSTART.md](docs/QUICKSTART.md)
- [docs/releases/FINAL_RELEASE_CHECKLIST.md](docs/releases/FINAL_RELEASE_CHECKLIST.md)
- [docs/guides/LINUX_SUPPORT.md](docs/guides/LINUX_SUPPORT.md)
- [docs/api/README_BACKEND.md](docs/api/README_BACKEND.md)
- [docs/sandbox_vmware.md](docs/sandbox_vmware.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)

Historical design notes under `docs/project/` and `docs/development/` are kept for traceability, but they are not the release source of truth.

---

## License

MIT. See [LICENSE](LICENSE).
