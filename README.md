# Sentinel — Endpoint Security Suite

Sentinel is a cross-platform desktop endpoint security application built with PySide6/QML and Python. It provides real-time system telemetry, security posture assessment, file scanning, network scanning, and optional AI-assisted analysis — designed as a graduation project and hardened toward a credible enterprise-ready desktop product.

---

## Features

### System Snapshot
- Live CPU, RAM, storage, and network metrics
- Tabbed view: System Overview, GPU Monitor, Network, Security
- Per-mount storage classification with hidden-mount debug toggle
- Security posture summary with platform-native provider diagnostics

### GPU Monitor
- MSI Afterburner–style real-time charts (usage, temperature, power, VRAM, clocks, fan)
- Multi-GPU support with navigation arrows to switch between cards
- Provider-based architecture with explicit metric availability states
- **AMD** — native sysfs/DRM/hwmon collection, no ROCm or external tools required
- **NVIDIA** — pynvml primary, nvidia-smi fallback, auto-detected via DRM + lspci on hybrid laptops
- Hybrid laptop support: NVIDIA dGPU detected via lspci even when driver or nvidia-smi is absent
- No fake zero values — every metric carries an explicit status (Live, Unavailable, Unsupported, Not exposed, Shared memory, Permission required, Backend error)

### Security Posture
- Firewall detection: ufw, firewalld, nftables, iptables
- Antivirus/scanner: ClamAV realtime daemon vs. scanner-only vs. not installed
- Secure Boot, disk encryption, TPM presence
- AppArmor / SELinux enforcement state
- Package update state and remote-access exposure (Linux)
- Windows Defender, UAC, TPM flows (Windows)
- Three-state indicators: good / warning / bad

### Scan Center
- File and URL scanning with quarantine management
- Secure delete for quarantined files
- Scan history with clear action
- Recovery controller for file restoration

### Network Scan
- Nmap-backed host and port discovery
- Device enumeration UI with diagnostic output

### AI Analysis
- Groq API integration (LLaMA models) for event explanation and security chatbot
- Offline knowledge base fallback
- AI-generated security reports

### File Function
- File recovery workflow with checkboxes
- Secure-delete integration

### Diagnostics
- Runtime path validation
- Optional provider health checks
- Crash capture and export

---

## Platform Support

| Capability | Windows | Linux |
| --- | --- | --- |
| System snapshot | Supported | Supported |
| GPU monitoring — NVIDIA | Supported (pynvml / WMI) | Supported (pynvml / nvidia-smi / DRM+lspci) |
| GPU monitoring — AMD | Supported (ADL SDK) | Supported (native sysfs — no ROCm needed) |
| GPU monitoring — hybrid laptop | Supported | Supported (DRM + lspci supplement) |
| Security posture page | Supported | Supported (platform-native checks) |
| File scanning and quarantine | Supported | Supported |
| Network scan UI | Supported | Supported |
| AI analysis (Groq) | Supported | Supported |
| XDG runtime paths | N/A | Supported |
| Event Viewer integration | Supported | Not available |
| VMware sandbox flows | Supported | Not available on Linux host |

---

## GPU Monitoring Detail

### Detection priority

| Priority | Provider | Vendor | Notes |
| --- | --- | --- | --- |
| 1 | pynvml / NVML | NVIDIA | Full metrics |
| 2 | nvidia-smi | NVIDIA | Fallback when pynvml absent |
| 3 | amdgpu sysfs | AMD | Native kernel interface, no ROCm |
| 4 | rocm-smi | AMD | When ROCm is installed |
| 5 | pyadl | AMD | WSL only (Windows ADL SDK) |
| 6 | DRM supplement | Any | Driver loaded, no SMI tool |
| 7 | lspci supplement | Any | No driver loaded (PRIME power-off) |

### Metric availability states

| State | UI label | Meaning |
| --- | --- | --- |
| `ok` | Live | Metric actively collected |
| `unsupported` | Unsupported | Hardware or driver does not expose this metric |
| `unavailable` | Unavailable | Metric expected but could not be read |
| `not_exposed` | Not exposed | Sensor exists but driver does not surface it |
| `permission_denied` | Permission required | Elevated privileges needed |
| `backend_error` | Backend error | Query failed with an error |
| `shared_memory` | Shared memory | AMD iGPU/APU uses shared system RAM — no dedicated VRAM |

### AMD iGPU / APU notes
AMD APUs (Renoir, Cezanne, Rembrandt, Phoenix, …) report little or no dedicated VRAM. Sentinel detects this and labels VRAM tiles **Shared memory** rather than showing 0 B or Unavailable. GPU utilization, temperature, and fan metrics (where exposed by the hwmon driver) are still collected normally.

---

## Linux Notes

Sentinel is first-class on Linux for snapshot, security posture, diagnostics, storage classification, and core scanning flows.

- Filters pseudo filesystems, loop mounts, Snap squashfs images, and container overlays from the default storage view
- Exposes a debug toggle in System Snapshot → Storage to show hidden mounts
- Uses platform-native checks for firewall, package updates, Secure Boot, disk encryption, remote access, and MAC enforcement
- Uses XDG-style runtime paths instead of Windows `APPDATA` fallbacks
- GPU normalization prevents any missing Linux sensor from appearing as a fake `0%` or `0 C`

See [docs/guides/LINUX_SUPPORT.md](docs/guides/LINUX_SUPPORT.md) for full Linux details and current limitations.

---

## Quick Start

### Requirements

- Python 3.11+
- Git
- PySide6-compatible desktop environment (X11 or Wayland)

### Optional integrations

| Tool | Purpose |
| --- | --- |
| Groq API key | AI-assisted features |
| Nmap | Network scanning |
| ClamAV (`clamd` / `clamscan`) | Linux antivirus detection |
| `ufw`, `firewalld`, `nftables`, `iptables` | Richer firewall reporting |
| `pynvml` | Best Linux NVIDIA GPU telemetry |
| `nvidia-smi` | NVIDIA GPU fallback telemetry |
| `rocm-smi` | Improved Linux AMD GPU telemetry |
| `mokutil` | Secure Boot state |
| `aa-status` | AppArmor enforcement state |

### Windows

```powershell
git clone https://github.com/mahmoudbadr238/graduationp.git
cd graduationp

python -m venv .venv
.venv\Scripts\activate

python -m pip install --upgrade pip
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

You can also use [run_linux.sh](run_linux.sh) to provision a Linux dev environment from the repo, and [build_linux.sh](build_linux.sh) to create a PyInstaller build.

---

## Optional Providers and Degraded Mode

Sentinel stays usable when optional providers are missing:

- **No GPU backend** — GPU page still shows the device name and marks all metrics as Unavailable or Unsupported; no fake `0%` values
- **No firewall tool on Linux** — security page reports that no supported firewall stack was detected
- **No ClamAV on Linux** — security page reports "Not installed" instead of claiming protection
- **No package manager probe** — package-update status becomes Unavailable rather than defaulting to green
- **No Groq API key** — AI features are hidden; offline knowledge base remains available
- **No Nmap** — network scan UI stays visible with a clear "Nmap not found" message

---

## Runtime Paths

| Type | Windows | Linux |
| --- | --- | --- |
| Config | `%APPDATA%\Sentinel` | `$XDG_CONFIG_HOME/sentinel` |
| Data | `%APPDATA%\Sentinel` | `$XDG_DATA_HOME/sentinel` |
| Logs | `%APPDATA%\Sentinel\logs` | `$XDG_STATE_HOME/sentinel/logs` |
| Crash logs | `%APPDATA%\Sentinel\crashes` | `$XDG_STATE_HOME/sentinel/crashes` |
| Quarantine | `%PROGRAMDATA%\Sentinel\Quarantine` | `$XDG_DATA_HOME/sentinel/quarantine` |

Linux keeps legacy compatibility lookups for older `~/.config/Sentinel`, `~/.local/share/Sentinel`, and `~/.sentinel` locations, but new writes use the normalized XDG layout.

---

## Diagnostics

```bash
python -m backend --diagnose
python -m backend --export-diagnostics diagnostics.json
python -m backend --reset-settings
```

Diagnostics validate optional integrations, runtime paths, and degraded providers before launching the UI. Run them first when troubleshooting a missing feature.

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

The test suite covers:

- Linux GPU DRM enumeration and connector filtering
- AMD sysfs provider: discrete VRAM, iGPU shared-memory, hwmon sensors
- GPU metric normalization: status preservation, key mapping, regression guards
- Linux mount filtering and storage normalization
- Cross-platform runtime path selection
- Linux security posture mapping

---

## Architecture

```text
backend/
  api/          QML-facing services and bridges (GPUService, BackendBridge, …)
  core/         Config, logging, DI container, startup, performance monitoring
  engines/      Scanning, AI, sandbox, file recovery workflows
  infra/        Optional integration helpers (Nmap, SQLite, …)
  platform/     OS-specific abstractions
    linux/      DRM enumeration, AMD sysfs provider, GPU normalization,
                security posture, storage classification, telemetry worker
  tests/        Automated tests

frontend/qml/
  components/   Shared QML components (cards, dialogs, charts)
  pages/        Top-level pages (HomePage, GPUMonitor, ScanCenter, …)
  ui/ theme/    ThemeManager, global typography and color tokens
```

Key service boundaries:

- **GPUServiceBridge** — spawns the platform-appropriate telemetry worker as a `QProcess`, parses JSON-line output, maintains 60-point rolling history per metric, implements heartbeat watchdog and circuit breaker
- **BackendBridge** — exposes scanning, AI, network, and snapshot APIs to QML
- **SnapshotService** — pre-warms security and system snapshot caches on startup
- **RTPBridge** — real-time protection controller

---

## Current Boundaries

These are intentionally out of scope on Linux:

- Windows Event Viewer collection
- Windows Defender / UAC / TPM privilege flows
- VMware sandbox execution from a Linux host

Linux support is explicit about partial coverage. Sentinel reports unavailable or unsupported states instead of pretending those controls exist.

---

## Documentation

- [docs/QUICKSTART.md](docs/QUICKSTART.md)
- [docs/guides/LINUX_SUPPORT.md](docs/guides/LINUX_SUPPORT.md)
- [docs/api/README_BACKEND.md](docs/api/README_BACKEND.md)
- [docs/sandbox_vmware.md](docs/sandbox_vmware.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Contributing

Before opening a PR:

```bash
python -m backend --diagnose
.venv/bin/python -m pytest backend/tests -q
```

---

## License

MIT. See [LICENSE](LICENSE).
