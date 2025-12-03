<div align="center">

# 🛡️ Sentinel

### Intelligent Endpoint Security Suite

<br>

<img src="https://img.shields.io/badge/version-1.0.0--beta-0078D4?style=for-the-badge&logo=windows&logoColor=white" alt="Version">
<img src="https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/Qt-6.x-41CD52?style=for-the-badge&logo=qt&logoColor=white" alt="Qt">
<img src="https://img.shields.io/badge/AI-Local%20LLM-FF6F00?style=for-the-badge&logo=tensorflow&logoColor=white" alt="AI">
<img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">

<br><br>

**An AI-powered desktop security application that makes Windows security accessible to everyone.**

*Built with PySide6, QML, and Local AI — No cloud required.*

<br>

[✨ Features](#-features) · [🚀 Quick Start](#-quick-start) · [📖 Documentation](#-documentation) · [🤝 Contributing](#-contributing)

---

<br>

</div>

## 📋 Overview

**Sentinel** is a comprehensive endpoint security suite designed to bridge the gap between complex Windows security tools and everyday users. By leveraging **local AI technology**, Sentinel translates cryptic system events into clear, actionable explanations — no security expertise required.

> 🎓 **Graduation Project** — Developed as a capstone project demonstrating modern desktop application architecture, AI integration, and user-centered security design.

<br>

### 🌟 What Makes Sentinel Different?

| Traditional Security Tools | Sentinel |
|---------------------------|----------|
| ❌ Cryptic error codes | ✅ Plain English explanations |
| ❌ Requires expertise | ✅ Designed for everyone |
| ❌ Cloud-dependent AI | ✅ **100% Local AI** — Your data never leaves your PC |
| ❌ Overwhelming dashboards | ✅ Clean, intuitive interface |
| ❌ Subscription fees | ✅ Free and open source |

<br>

### ✨ Key Highlights

| Feature | Description |
|---------|-------------|
| 🤖 **AI-Powered Event Analysis** | Local LLM translates Windows events into 5-section explanations anyone can understand |
| 📊 **Real-Time Monitoring** | Live CPU, Memory, Disk, GPU, and Network metrics with beautiful visualizations |
| 🔍 **Smart Event Viewer** | Color-coded security events with severity ratings and actionable recommendations |
| 🛡️ **Threat Scanning** | VirusTotal integration for file and URL analysis (optional) |
| 🌐 **Network Scanner** | 8 specialized Nmap scan types with streaming output (optional) |
| 🎨 **Modern UI** | Dark/Light/System themes with smooth 300ms transitions |
| 💾 **Local Database** | SQLite storage — all data stays on your machine |

---

<br>

## 🚀 Quick Start

### Prerequisites

- **Windows 10** (1809+) or **Windows 11**
- **Python 3.10+** ([Download](https://www.python.org/downloads/))
- **Git** ([Download](https://git-scm.com/downloads))

### Installation

```powershell
# Clone the repository
git clone https://github.com/mahmoudbadr238/graduationp.git
cd graduationp

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Launch Sentinel
python main.py
```

### First Launch Checklist

| Step | Action |
|------|--------|
| 1️⃣ | Application opens on **Home** — view live system metrics |
| 2️⃣ | Navigate with sidebar or shortcuts (`Ctrl+1` to `Ctrl+7`) |
| 3️⃣ | Try **Event Viewer** (`Ctrl+2`) — see AI-powered event explanations |
| 4️⃣ | Customize in **Settings** (`Ctrl+7`) — change theme, configure APIs |

> 💡 **Tip:** Run as Administrator for full Security event log access: `.\scripts\run_as_admin.bat`

<br>

## ✨ Features

### 🤖 AI-Powered Event Analysis (Core Feature)

Sentinel's standout feature is its **local AI engine** that transforms complex Windows events into human-readable explanations:

```
┌─────────────────────────────────────────────────────────────────┐
│  Before (Raw Event)                                             │
├─────────────────────────────────────────────────────────────────┤
│  Event ID: 4625                                                 │
│  Source: Microsoft-Windows-Security-Auditing                    │
│  Level: Information                                             │
│  Message: An account failed to log on...                        │
└─────────────────────────────────────────────────────────────────┘
                              ▼ AI Processing ▼
┌─────────────────────────────────────────────────────────────────┐
│  After (Sentinel Explanation)                                   │
├─────────────────────────────────────────────────────────────────┤
│  📌 What Happened                                               │
│  Someone tried to log into your computer but entered the wrong  │
│  password. This could be you mistyping, or someone else trying  │
│  to access your account.                                        │
│                                                                 │
│  🔍 Why This Happens                                            │
│  Failed login attempts occur when credentials don't match.      │
│  Common causes: typos, forgotten passwords, or unauthorized     │
│  access attempts.                                               │
│                                                                 │
│  ✅ What To Do                                                  │
│  • If this was you: Double-check your password                  │
│  • If repeated failures: Consider enabling account lockout      │
│  • If suspicious: Review the source IP address                  │
│                                                                 │
│  🔧 Technical Notes                                             │
│  Event 4625 | Security Log | Logon Type: 3 (Network)           │
└─────────────────────────────────────────────────────────────────┘
```

**Key Benefits:**
- 🔒 **100% Local Processing** — No data sent to external servers
- ⚡ **Instant Analysis** — No API latency or rate limits
- 📚 **Knowledge Base** — Pre-built explanations for 50+ common events
- 🎯 **Severity-Aware** — Recommendations tailored to event criticality

<br>

### 📊 Real-Time System Monitoring

| Metric | Details |
|--------|---------|
| **CPU** | Per-core usage, temperature (if available), frequency |
| **Memory** | Used/Available RAM, swap usage |
| **Disk** | Read/Write speeds, partition usage |
| **Network** | Upload/Download speeds, active connections |
| **GPU** | Utilization, VRAM, temperature (NVIDIA/AMD) |

- 🔄 **1 Hz refresh rate** with smooth animated transitions
- 📈 **Historical tracking** in SQLite database
- 🎨 **Beautiful visualizations** with progress bars and charts

<br>

### 🔍 Smart Event Viewer

Transform Windows Event Logs from cryptic technical data into actionable insights:

| Severity | Visual | Example Events |
|----------|--------|----------------|
| 🔴 **Critical** | Red badge | System crashes, hardware failures |
| 🟠 **Error** | Orange badge | Application errors, service failures |
| 🟡 **Warning** | Yellow badge | Resource warnings, permission issues |
| 🔵 **Information** | Blue badge | Successful operations, status updates |
| 🟢 **Success** | Green badge | Audit successes, completed tasks |

**Sources Monitored:** Application, System, Security (requires Admin)

<br>

### 🖥️ System Snapshot

Get a comprehensive view of your system:

- **Overview** — All metrics at a glance
- **Hardware** — CPU model, RAM specs, GPU details
- **Network** — Interface stats, active connections, IP addresses
- **OS Info** — Windows version, build number, system uptime

<br>

### 🛡️ Threat Scanning (Optional)

Integrate with **VirusTotal** for enhanced threat detection:

| Feature | Description |
|---------|-------------|
| File Scanning | Check files against 70+ antivirus engines |
| URL Analysis | Verify website safety before visiting |
| Hash Lookup | Quick reputation checks without uploading |

> 📝 **Free Tier:** 4 requests/minute, 500/day — [Get API Key](https://www.virustotal.com/gui/join-us)

<br>

### 🌐 Network Scanner (Optional)

**8 Specialized Scan Types** powered by Nmap:

| Scan Type | Purpose |
|-----------|---------|
| 🔍 Host Discovery | Find live devices on your network |
| 🗺️ Network Mapping | Map topology with traceroute |
| 🚪 Port Scanning | Detect open/closed/filtered ports |
| 💻 OS Detection | Identify operating systems |
| ⚙️ Service Detection | Find running services and versions |
| 🔥 Firewall Detection | Detect firewall rules |
| ⚠️ Vulnerability Scan | Check for known CVEs |
| 📡 Protocol Analysis | Analyze IP protocols |

- 📺 **Real-time streaming output** with console view
- 🎯 **Auto-detect subnet** for network-wide scans
- 💾 **Reports auto-saved** to `~/.sentinel/nmap_reports/`

> 📝 **Requires:** [Nmap](https://nmap.org/download.html) installed and in PATH

<br>

## ⚙️ Configuration

### Environment Setup

Create a `.env` file in the project root (or copy from `.env.example`):

```env
# ─────────────────────────────────────────────────────────
# SENTINEL CONFIGURATION
# ─────────────────────────────────────────────────────────

# VirusTotal API Key (Optional)
# Get free key: https://www.virustotal.com/gui/join-us
VT_API_KEY=

# Nmap Path (Optional - auto-detected if in PATH)
NMAP_PATH=

# Offline Mode - Disable all external API calls
OFFLINE_ONLY=false
```

### Optional Integrations

<details>
<summary><b>🛡️ VirusTotal Setup</b></summary>

1. Create free account: https://www.virustotal.com/gui/join-us
2. Copy API key from your profile
3. Add to `.env`: `VT_API_KEY=your_key_here`
4. Restart Sentinel
5. Verify: Status bar shows "VirusTotal: Enabled"

</details>

<details>
<summary><b>🌐 Nmap Setup</b></summary>

1. Download installer: https://nmap.org/download.html
2. Install with **"Add to PATH"** option checked
3. Verify in terminal: `nmap --version`
4. Restart Sentinel
5. Verify: Status bar shows "Nmap: Available"

</details>

<details>
<summary><b>🔐 Administrator Mode</b></summary>

For full Security event log access:

```powershell
# Option 1: Use provided script
.\scripts\run_as_admin.bat

# Option 2: Right-click python.exe → Run as Administrator
```

</details>

<br>

## 🏗️ Architecture

### Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | PySide6 + QML | Modern declarative UI with animations |
| **Backend** | Python 3.10+ | Business logic and system integration |
| **AI Engine** | Local LLM | Event analysis without cloud dependency |
| **Database** | SQLite | Local persistence for scans and settings |
| **Monitoring** | psutil | Cross-platform system metrics |
| **Events** | win32evtlog | Windows Event Log integration |

### Design Principles

- 🧱 **Clean Architecture** — Separation of concerns with clear boundaries
- 💉 **Dependency Injection** — Testable, modular components
- 🎨 **Singleton Theme System** — Consistent styling across all components
- ⚡ **Async Processing** — Non-blocking UI with background workers
- 🔒 **Privacy First** — All processing happens locally

### Project Structure

```
sentinel/
├── 📁 app/                    # Python Backend
│   ├── 🤖 ai/                 # AI engine and event analysis
│   │   ├── ai_worker.py       # Background AI processing
│   │   ├── event_explainer.py # Event explanation generation
│   │   ├── local_llm_engine.py# Local LLM integration
│   │   └── event_id_knowledge.py # Pre-built event knowledge base
│   ├── 🔧 core/               # Domain logic
│   │   ├── container.py       # Dependency injection container
│   │   ├── interfaces.py      # Abstract interfaces
│   │   └── workers.py         # Background task workers
│   ├── 🌐 infra/              # Infrastructure
│   │   ├── sqlite_repo.py     # Database operations
│   │   ├── events_windows.py  # Windows Event Log reader
│   │   ├── vt_client.py       # VirusTotal API client
│   │   └── nmap_cli.py        # Nmap integration
│   ├── 🖥️ ui/                 # QML ↔ Python Bridge
│   │   ├── backend_bridge.py  # Main bridge for QML
│   │   └── settings_service.py# Settings management
│   └── 🧪 tests/              # Unit tests
│
├── 📁 qml/                    # Qt Quick Frontend
│   ├── main.qml               # Application root
│   ├── 📄 pages/              # Application pages
│   │   ├── EventViewer.qml    # AI-powered event viewer
│   │   ├── SystemSnapshot.qml # System information
│   │   └── ...                # Other pages
│   ├── 🧩 components/         # Reusable UI components
│   │   ├── Theme.qml          # Singleton theme system
│   │   ├── Card.qml           # Hover-enabled containers
│   │   └── ...                # Other components
│   └── 🎨 theme/              # Theme definitions
│
├── 📁 docs/                   # Documentation
├── 📁 scripts/                # Helper scripts
├── 📄 main.py                 # Application entry point
├── 📄 requirements.txt        # Python dependencies
└── 📄 README.md               # This file
```

<br>

## 🐛 Troubleshooting

<details>
<summary><b>Common Issues & Solutions</b></summary>

| Issue | Solution |
|-------|----------|
| "VirusTotal API key required" | Add key to `.env` or set `OFFLINE_ONLY=true` |
| "Nmap not found" | Install Nmap and ensure it's in PATH (`where nmap`) |
| "Not running with administrator privileges" | Use `scripts/run_as_admin.bat` |
| "Could not set initial property duration" | Cosmetic warning only — safe to ignore |
| AI explanations not appearing | Check `~/.sentinel/logs/` for AI worker errors |

</details>

<details>
<summary><b>Getting Help</b></summary>

- 📝 **Open an Issue:** [GitHub Issues](https://github.com/mahmoudbadr238/graduationp/issues)
- 📧 **Email:** mahmoudbadr238@gmail.com
- 📚 **Documentation:** [docs/](docs/)

</details>

<br>

## 💻 System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **OS** | Windows 10 (1809+) | Windows 11 (22H2+) |
| **Python** | 3.10 | 3.11+ |
| **RAM** | 2 GB | 4 GB |
| **Storage** | 500 MB | 1 GB |
| **Display** | 1280×720 | 1920×1080 |

<br>

## 🔐 Security & Privacy

Sentinel is designed with privacy as a core principle:

| Aspect | Implementation |
|--------|----------------|
| 🔒 **Data Storage** | All data stored locally in `~/.sentinel/sentinel.db` |
| 🚫 **No Telemetry** | Zero usage statistics or analytics collected |
| 🤖 **Local AI** | All AI processing happens on your machine |
| 🌐 **Optional APIs** | VirusTotal/Nmap are opt-in only |
| ⚠️ **VirusTotal Note** | File hashes sent when enabled — avoid scanning confidential files |

📄 See [SECURITY.md](SECURITY.md) and [Privacy Policy](docs/PRIVACY.md) for details.

<br>

## 📚 Documentation

| Category | Description |
|----------|-------------|
| 📘 **[Quick Start Guide](docs/QUICKSTART.md)** | Get running in 5 minutes |
| 📗 **[User Manual](docs/user/USER_MANUAL.md)** | Complete feature reference |
| 📙 **[API Integration](docs/api/API_INTEGRATION_GUIDE.md)** | VirusTotal & Nmap setup |
| 📕 **[Architecture](docs/api/README_BACKEND.md)** | System design overview |
| 📓 **[Contributing](docs/CONTRIBUTING.md)** | How to contribute |

<br>

## 🗺️ Roadmap

### ✅ v1.0.0-beta (Current)

- [x] Real-time system monitoring (CPU, RAM, GPU, Disk, Network)
- [x] **AI-powered event explanations with 5-section format**
- [x] Windows Event Viewer with severity color-coding
- [x] Scan history with CSV export
- [x] Theme support (Dark/Light/System) with persistence
- [x] VirusTotal & Nmap integration
- [x] 8 specialized Nmap scan types with streaming output
- [x] Settings persistence across restarts

### 🚧 v1.1.0 (Planned)

- [ ] VirusTotal file upload with analysis polling
- [ ] Background threading for all scans
- [ ] First-run setup wizard
- [ ] Historical metrics charts
- [ ] Automated test suite expansion

### 🔮 v2.0.0 (Future)

- [ ] Multi-language support (i18n)
- [ ] Plugin system for custom scanners
- [ ] Enhanced AI threat detection
- [ ] Cloud sync (optional, encrypted)

<br>

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](docs/CONTRIBUTING.md) first.

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/graduationp.git

# Create feature branch
git checkout -b feature/amazing-feature

# Make changes and commit
git commit -m "feat: Add amazing feature"

# Push and create PR
git push origin feature/amazing-feature
```

<br>

## 📜 License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

<br>

## 🙏 Acknowledgments

| Technology | Usage |
|------------|-------|
| [Qt Framework](https://www.qt.io/) | Cross-platform UI framework |
| [PySide6](https://doc.qt.io/qtforpython/) | Python bindings for Qt |
| [psutil](https://github.com/giampaolo/psutil) | System monitoring |
| [VirusTotal](https://www.virustotal.com/) | Threat intelligence API |
| [Nmap](https://nmap.org/) | Network scanning |

<br>

---

<div align="center">

<br>

**Built with ❤️ as a Graduation Project**

<br>

[![GitHub stars](https://img.shields.io/github/stars/mahmoudbadr238/graduationp?style=social)](https://github.com/mahmoudbadr238/graduationp/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/mahmoudbadr238/graduationp?style=social)](https://github.com/mahmoudbadr238/graduationp/network/members)

<br>

[⬆ Back to Top](#-sentinel)

</div>
