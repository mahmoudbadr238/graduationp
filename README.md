<div align="center">

# 🛡️ Sentinel

### Intelligent Endpoint Security Suite

<br>

<img src="https://img.shields.io/badge/version-1.0.0-0078D4?style=for-the-badge&logo=windows&logoColor=white" alt="Version">
<img src="https://img.shields.io/badge/python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/Qt-6.x-41CD52?style=for-the-badge&logo=qt&logoColor=white" alt="Qt">
<img src="https://img.shields.io/badge/platform-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white" alt="Platform">
<img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">

<br><br>

**A Windows-first desktop security application for monitoring, scanning, and AI-assisted analysis.**

*Built with PySide6, QML, Python services, optional cloud integrations, and Windows security tooling.*

<br>

[✨ Features](#-features) · [🚀 Quick Start](#-quick-start) · [🤖 AI Setup](#-ai-configuration) · [🏗️ Architecture](#-architecture) · [📚 Documentation](#-documentation) · [🤝 Contributing](#-contributing)

---

<br>

</div>

## 📋 Overview

**Sentinel** is the active graduation project codebase for a desktop endpoint
security suite focused on Windows monitoring and analysis. The current version
of the repository uses a `backend/` + `frontend/qml/` structure and combines
system visibility, file and URL scanning, optional sandbox detonation, and
AI-assisted explanations in a single desktop app.

> 🎓 **Graduation Project** — developed as a capstone project around desktop
> security workflows, Windows integration, QML UI architecture, and practical
> security tooling.

<br>

### 🌟 What Makes Sentinel Different?

| Traditional Security Tools | Sentinel |
|---------------------------|----------|
| ❌ Hard to follow for non-specialists | ✅ Designed to be readable and guided |
| ❌ Split across many disconnected tools | ✅ Monitoring, scanning, and triage in one app |
| ❌ Raw system data only | ✅ Human-readable analysis and summaries |
| ❌ Minimal local diagnostics | ✅ Built-in diagnostics and export flows |
| ❌ Weak desktop UX | ✅ QML-based interface with theming and notifications |

<br>

### ✨ Key Highlights

| Feature | Description |
|---------|-------------|
| 🤖 **AI-Assisted Analysis** | Groq-backed explanations for security assistant and report interpretation |
| 📊 **Live System Monitoring** | CPU, memory, disk, network, and GPU telemetry with live dashboards |
| 📋 **Event Viewer** | Windows event inspection with explanation workflows and severity cues |
| 🔍 **Scan Center** | File and URL scanning with reporting and history persistence |
| 🌐 **Network Scan** | Optional Nmap-backed scans from the desktop UI |
| 🗂️ **File Function** | Secure deletion and recovery-oriented workflows |
| 🖥️ **Sandbox Lab** | VMware-based detonation and behavior review |
| 🔔 **Notifications** | In-app notification center plus system tray integration |
| 🧪 **Diagnostics** | `python -m backend --diagnose` and JSON diagnostics export |
| 🎨 **Modern UI** | Sidebar navigation, QML components, and theme-aware pages |

---

<br>

## 🤖 AI Configuration

Sentinel currently documents **Groq** as the primary AI provider in the active
setup flow. AI features can be left unconfigured, but they will fall back to
reduced or offline behavior.

### Setup Options

#### Option 1: Groq (Recommended)

```powershell
# Set Groq API key for AI-backed features
$env:GROQ_API_KEY = "gsk_your-key-here"

# Launch Sentinel
python main.py
```

Get an API key at [console.groq.com](https://console.groq.com/).

#### Option 2: .env File

Copy `.env.example` to `.env` and configure the values you need:

```env
GROQ_API_KEY=
SENTRY_DSN=
NMAP_PATH=
OFFLINE_ONLY=false

SANDBOX_VMRUN=C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe
SANDBOX_VMX=D:\vm\windows10\Windows 10 x64.vmx
SANDBOX_SNAPSHOT=Clean Base
SANDBOX_GUEST_USER=
SANDBOX_GUEST_PASS=
```

#### Option 3: Offline-Only Mode

```powershell
$env:OFFLINE_ONLY = "true"
python main.py
```

### AI-Related Features

| Feature | Uses AI For |
|---------|------------|
| **Security Assistant** | System-aware question answering and security guidance |
| **Scan Center** | Report interpretation and AI summaries |
| **Sandbox / Scan Reports** | Higher-level explanation of analysis results |
| **Event Analysis Paths** | AI-enhanced explanation when configured |

### Offline Behavior

Without `GROQ_API_KEY`, Sentinel can still operate with partial functionality:

- ✅ Core desktop UI still launches
- ✅ System monitoring and local tools still work
- ✅ Diagnostics and configuration flows still work
- ✅ Scan workflows can still run where local tooling is available
- ❌ AI-backed assistant and Groq summaries are unavailable

> 💡 **Tip:** If you are validating a fresh machine, run
> `python -m backend --diagnose` before opening the UI.

---

<br>

## 🚀 Quick Start

### Prerequisites

- **Windows 10** or **Windows 11**
- **Python 3.11+** ([Download](https://www.python.org/downloads/))
- **Git** ([Download](https://git-scm.com/downloads))
- Optional: **Nmap** for network scans
- Optional: **VMware Workstation** for Sandbox Lab / sandbox-assisted scans

### Installation

```powershell
# Clone the repository
git clone https://github.com/mahmoudbadr238/graduationp.git
cd graduationp

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# Create local configuration
Copy-Item .env.example .env

# Launch Sentinel
python main.py
```

### First Launch Checklist

| Step | Action |
|------|--------|
| 1️⃣ | Start with `python -m backend --diagnose` if this is a new machine |
| 2️⃣ | Launch the app with `python main.py` |
| 3️⃣ | Review **Home**, **Event Viewer**, **System Snapshot**, and **System Monitor** |
| 4️⃣ | Configure Groq or VMware only if you need those flows |
| 5️⃣ | If prompted, allow UAC elevation for full Windows visibility |

> 💡 **Tip:** For limited-access development sessions, you can skip elevation
> with `SKIP_UAC=1`.

<br>

## ✨ Features

### 🤖 AI-Assisted Security Workflows

Sentinel includes AI-connected flows for assistant responses and report
interpretation when `GROQ_API_KEY` is configured.

**Key Benefits:**
- ⚡ **Fast setup** with one primary AI environment variable
- 🧭 **Guided explanations** layered on top of local analysis results
- 🔒 **Optional by design** so the app still works in reduced mode
- 🧪 **Diagnostic-friendly** because AI is not required to validate the app

<br>

### 📊 System Snapshot and System Monitor

| Area | Details |
|------|---------|
| **CPU / Memory** | Live usage, health context, and dashboard presentation |
| **Disk / Network** | Activity metrics and interface-level details |
| **GPU** | NVIDIA and AMD telemetry paths where supported |
| **History Views** | Live charting in monitoring pages |

- 🔄 Continuous update flow through backend services
- 📈 Separate pages for broad snapshot and focused monitoring
- 🖥️ Desktop-native UI with system tray support

<br>

### 📋 Event Viewer

Transform Windows event data into a workflow that is easier to inspect and
triage:

| Capability | Description |
|------------|-------------|
| **Windows Event Access** | Reads Windows event sources where privileges allow |
| **Severity Presentation** | Visual prioritization inside the UI |
| **Explanation Paths** | Human-readable guidance layered onto raw event data |
| **Admin Awareness** | Full access improves visibility into protected sources |

<br>

### 🔍 Scan Center

Scan Center is one of the main active modules in the current codebase:

- **File scanning** workflows
- **URL scanning** workflows
- **History tab** with persisted scan records
- **Export/report** paths for completed jobs
- **Optional sandbox coupling** through VMware-backed execution paths

<br>

### 🌐 Network Scan (Optional)

Sentinel integrates with **Nmap** when it is installed or configured via
`NMAP_PATH`.

- 📡 Desktop-triggered network scanning
- 🧾 Result pages for collected output
- ⚙️ Optional dependency that does not block the rest of the app

> 📝 **Requires:** [Nmap](https://nmap.org/download.html) installed or available
> via `NMAP_PATH`

<br>

### 🗂️ File Function

The File Function area covers local file operations oriented around security and
recovery tasks:

- **Secure deletion** / shred flows
- **Recovery-oriented** workflows
- **Bridge-based backend services** exposed to QML

<br>

### 🖥️ Sandbox Lab

Sentinel includes VMware-driven sandbox functionality for deeper detonation and
behavior review:

- **VMware Workstation integration**
- **Guest automation and preview tooling**
- **Diagnostics for sandbox prerequisites**
- **Detonation support for suspicious samples**

> 📝 **Requires:** VMware Workstation and a configured guest environment

<br>

### 💬 Security Assistant

An AI-assisted desktop helper that can operate alongside Sentinel's system
context and security tooling.

- **System-aware** assistant behavior
- **Groq-backed** when configured
- **Integrated into the app UI**

<br>

### 🔔 Notifications and Diagnostics

- **In-app notification center**
- **System tray integration**
- **Crash capture and logging**
- **CLI diagnostics** via:

```powershell
python -m backend --diagnose
python -m backend --export-diagnostics diagnostics.json
python -m backend --reset-settings
```

<br>

## ⚙️ Configuration

### Environment Setup

Create a `.env` file in the project root or copy it from `.env.example`:

```env
# Primary AI provider
GROQ_API_KEY=

# Optional external services
SENTRY_DSN=
NMAP_PATH=
OFFLINE_ONLY=false

# VMware Sandbox Lab
SANDBOX_VMRUN=C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe
SANDBOX_VMX=D:\vm\windows10\Windows 10 x64.vmx
SANDBOX_SNAPSHOT=Clean Base
SANDBOX_GUEST_USER=
SANDBOX_GUEST_PASS=
SANDBOX_HOST_RESULTS_DIR=C:\SentinelSandbox\results
SANDBOX_HOST_FRAMES_DIR=C:\SentinelSandbox\frames
```

### Optional Integrations

<details>
<summary><b>🌐 Nmap Setup</b></summary>

1. Install Nmap from https://nmap.org/download.html
2. Make sure it is on `PATH`, or set `NMAP_PATH`
3. Run `python -m backend --diagnose`
4. Launch Sentinel and open the Network Scan page

</details>

<details>
<summary><b>🖥️ VMware Setup</b></summary>

Configure the VMware-related values in `.env`:

- `SANDBOX_VMRUN`
- `SANDBOX_VMX`
- `SANDBOX_SNAPSHOT`
- `SANDBOX_GUEST_USER`
- `SANDBOX_GUEST_PASS`

Then validate your setup with Sentinel diagnostics and Sandbox Lab checks.

</details>

<details>
<summary><b>🔐 Administrator Mode</b></summary>

Sentinel may request elevation automatically on startup.

For reduced-access development sessions:

```powershell
$env:SKIP_UAC = "1"
python main.py
```

</details>

<br>

## 🏗️ Architecture

### Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | PySide6 + QML | Desktop UI, theming, pages, and components |
| **Backend** | Python 3.11+ | Application services, bridges, engines, and orchestration |
| **Monitoring** | psutil, WMI, GPU integrations | Live system telemetry |
| **Scanning** | Local engines + optional Nmap / VMware | Scan and investigation workflows |
| **Persistence** | SQLite and local config | History, settings, and runtime state |
| **Validation** | pytest, Ruff, MyPy, Bandit | Tests and quality checks |

### Design Principles

- 🧱 **Separation of concerns** between QML UI and Python services
- ⚡ **Deferred startup** for heavier services
- 🔌 **Optional integrations** that degrade gracefully when absent
- 🧪 **CLI diagnostics** for easier local validation
- 🔒 **Local-first operation** with optional external providers

### Project Structure

```text
graduationp/
├── backend/
│   ├── api/                 # QML-facing services and backend bridge objects
│   ├── config/              # Environment-backed runtime settings
│   ├── core/                # Startup, logging, DI, monitoring, notifications
│   ├── engines/             # AI, scanning, sandbox, file, and security engines
│   ├── infra/               # Integration helpers such as Nmap availability
│   ├── tests/               # Automated tests
│   └── utils/               # Diagnostics, admin helpers, support utilities
│
├── frontend/qml/
│   ├── main.qml             # App shell and route switching
│   ├── components/          # Reusable QML building blocks
│   ├── pages/               # Main pages such as ScanCenter and EventViewer
│   ├── theme/               # Theme system
│   ├── ui/                  # Theme manager and UI helpers
│   └── ux/                  # Responsive / utility QML helpers
│
├── config/                  # JSON configuration assets
├── docs/                    # User, API, guide, and project documentation
├── scripts/                 # Local helper scripts
├── .env.example             # Example environment configuration
├── main.py                  # Desktop entrypoint with crash capture
└── pyproject.toml           # Tooling and packaging configuration
```

<br>

## 🐛 Troubleshooting

<details>
<summary><b>Common Issues & Solutions</b></summary>

| Issue | Solution |
|-------|----------|
| `nmap` not detected | Install Nmap or set `NMAP_PATH`, then run diagnostics |
| VMware actions fail | Verify `SANDBOX_VMRUN`, `SANDBOX_VMX`, snapshot, and guest credentials |
| AI assistant unavailable | Check `GROQ_API_KEY` and confirm `OFFLINE_ONLY` is not `true` |
| Reduced Windows visibility | Relaunch with administrator privileges |
| Startup problems | Run `python -m backend --diagnose` and inspect exported diagnostics |

</details>

<details>
<summary><b>Getting Help</b></summary>

- 📝 **Open an Issue:** [GitHub Issues](https://github.com/mahmoudbadr238/graduationp/issues)
- 📧 **Email:** mahmoudbadr238@gmail.com
- 📚 **Docs Index:** [docs/DOCUMENTATION_INDEX.md](docs/DOCUMENTATION_INDEX.md)

</details>

<br>

## 💻 System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **OS** | Windows 10 | Windows 11 |
| **Python** | 3.11 | 3.11+ |
| **RAM** | 4 GB | 8 GB |
| **Storage** | 1 GB | More if sandbox artifacts are enabled |
| **Display** | 1280x720 | 1920x1080 |

<br>

## 🔐 Security & Privacy

Sentinel is designed to run locally first, with optional cloud-connected
features where configured.

| Aspect | Implementation |
|--------|----------------|
| 🔒 **Local state** | Settings, history, and diagnostics are stored locally |
| 🚫 **Optional providers** | External services are opt-in through environment variables |
| 🤖 **AI usage** | Controlled through `GROQ_API_KEY` and `OFFLINE_ONLY` |
| 🌐 **Tool integrations** | Nmap and VMware are optional local dependencies |

📄 See [SECURITY.md](SECURITY.md) and [docs/PRIVACY.md](docs/PRIVACY.md) for details.

<br>

## 📚 Documentation

| Category | Description |
|----------|-------------|
| 📘 **[Quick Start Guide](docs/QUICKSTART.md)** | Guided setup and first-run instructions |
| 📗 **[User Manual](docs/user/USER_MANUAL.md)** | User-facing feature walkthrough |
| 📙 **[Quick Reference](docs/user/QUICK_REFERENCE.md)** | Shortcuts and operational reference |
| 📔 **[API Integration](docs/api/API_INTEGRATION_GUIDE.md)** | Integration and backend-oriented notes |
| 📕 **[Backend Overview](docs/api/README_BACKEND.md)** | Backend structure and design details |
| 📓 **[Sandbox VMware Guide](docs/sandbox_vmware.md)** | VMware setup and sandbox usage |
| 📒 **[Contributing](CONTRIBUTING.md)** | Contribution workflow and validation steps |

<br>

## 🗺️ Project Status

### ✅ Current Codebase

- [x] QML desktop shell with sidebar navigation
- [x] Event Viewer, System Snapshot, and System Monitor pages
- [x] Scan Center with file, URL, and history flows
- [x] Nmap result page and optional network scan integration
- [x] File Function workflows
- [x] VMware Sandbox Lab integration
- [x] Security Assistant and notification center
- [x] Diagnostics, settings reset, and export helpers
- [x] Test, lint, and static-analysis tooling in the repo

### 🚧 Ongoing Maintenance Areas

- [ ] Documentation alignment as features evolve
- [ ] Continued QA expansion across desktop workflows
- [ ] Additional hardening around optional integrations
- [ ] More coverage for scan and sandbox paths

<br>

## 🤝 Contributing

Contributions are welcome. Please read the current
[Contributing Guide](CONTRIBUTING.md) first.

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/graduationp.git
cd graduationp

# Create a branch
git checkout -b feature/amazing-feature

# Validate your changes
python -m backend --diagnose
python -m pytest backend/tests -q

# Push and open a PR
git push origin feature/amazing-feature
```

<br>

## 📜 License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for
details.

<br>

## 🙏 Acknowledgments

| Technology | Usage |
|------------|-------|
| [Qt Framework](https://www.qt.io/) | Desktop UI framework |
| [PySide6](https://doc.qt.io/qtforpython/) | Python bindings for Qt |
| [psutil](https://github.com/giampaolo/psutil) | System telemetry |
| [Groq](https://groq.com/) | AI-backed assistant and analysis flows |
| [Nmap](https://nmap.org/) | Optional network scanning |
| [VMware Workstation](https://www.vmware.com/) | Optional sandbox integration |

<br>

---

<div align="center">

<br>

**Built as a graduation project focused on practical desktop security workflows**

<br>

[![GitHub stars](https://img.shields.io/github/stars/mahmoudbadr238/graduationp?style=social)](https://github.com/mahmoudbadr238/graduationp/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/mahmoudbadr238/graduationp?style=social)](https://github.com/mahmoudbadr238/graduationp/network/members)

<br>

[⬆ Back to Top](#-sentinel)

</div>
