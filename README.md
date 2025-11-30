# 🛡️ Sentinel - Endpoint Security Suite

<div align="center">

A modern desktop security application built with PySide6 and QML, featuring real-time system monitoring, security feature tracking, and a beautiful dark/light theme system.

![Version](https://img.shields.io/badge/version-1.0.0--beta-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Qt](https://img.shields.io/badge/Qt-6.x-green)
![Platform](https://img.shields.io/badge/platform-Windows-blue)
![License](https://img.shields.io/badge/license-MIT-blue)

**Real-time system monitoring • Threat detection • Network scanning**

[Features](#-features) • [Installation](#-installation) • [Quick Start](#-quick-start) • [Documentation](#-documentation)

</div>

---

## 📋 Overview

Sentinel is a comprehensive endpoint security suite for Windows that provides real-time system monitoring, threat detection, and network analysis. Built with Python and Qt 6, it offers a modern, user-friendly interface for both security professionals and home users.

### ✨ Key Highlights

- **📊 Real-Time Monitoring** - Live CPU, Memory, Disk, and Network metrics
- **🔍 Smart Event Viewer** - Windows event logs in plain English
- **🛡️ Threat Scanning** - VirusTotal integration (optional)
- **🌐 Network Scanner** - Nmap-powered device discovery (optional)
- **🎨 Beautiful UI** - Dark/Light themes with smooth animations
- **💾 Database Persistence** - SQLite storage for all scans

---

## 🚀 Quick Start

### Installation

```powershell
# Clone repository
git clone https://github.com/mahmoudbadr238/graduationp.git
cd graduationp

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run Sentinel
python main.py
```

### First Launch

1. Application opens on **Home** page with live system metrics
2. Navigate using sidebar or keyboard shortcuts (`Ctrl+1` through `Ctrl+7`)
3. Try **Event Viewer** (`Ctrl+2`) to see Windows events in plain English
4. Go to **Settings** (`Ctrl+7`) to change theme

---

## ✨ Features

### Core Features (No Setup Required)

#### 📊 Live System Monitoring
- Real-time CPU, Memory, Disk, Network metrics (1 Hz refresh)
- GPU usage monitoring (when available)
- Animated progress bars and smooth transitions

#### 🔍 Intelligent Event Viewer
- Translates technical Event IDs to user-friendly messages
  - `Event 6005` → "Windows Event Log service started"
  - `Event 4624` → "User successfully logged in"
- Color-coded severity: ERROR (red), WARNING (yellow), INFO (blue), SUCCESS (green)
- Loads from Application, System, and Security logs

#### 🖥️ System Snapshot
- **Overview**: All metrics at a glance
- **Hardware**: CPU, RAM, GPU specifications
- **Network**: Interface statistics and active connections
- **OS Info**: Windows version, build, uptime

#### 📜 Scan History
- View all completed scans
- Export to CSV (Downloads folder)
- Filter by type (File, URL, Network)

#### 🎨 Appearance
- **Dark Mode**: Low-light friendly
- **Light Mode**: Bright environment optimized
- **System Sync**: Matches Windows theme automatically
- Smooth 300ms color transitions

### Optional Features (Require Setup)

#### 🛡️ VirusTotal Integration
- File scanning against 70+ antivirus engines
- URL reputation checks
- Free tier: 4 requests/min, 500/day

**Setup**: [API Integration Guide](docs/api/API_INTEGRATION_GUIDE.md#virustotal-integration)

#### 🌐 Network Scanner
- Device discovery on local network
- Port scanning (Quick: top 100, Full: all 65K)
- Service version detection

**Setup**: [Nmap Installation Guide](docs/api/API_INTEGRATION_GUIDE.md#nmap-integration)

---

## 🔧 Configuration

### Basic Setup

Copy `.env.example` to `.env` and configure:

```env
# Optional: VirusTotal API Key (get from virustotal.com/gui/join-us)
VT_API_KEY=

# Optional: Nmap path (auto-detected if in PATH)
NMAP_PATH=

# Disable all external APIs
OFFLINE_ONLY=false
```

### Enable Optional Features

#### VirusTotal
1. Get free API key: https://www.virustotal.com/gui/join-us
2. Add to `.env`: `VT_API_KEY=your_key_here`
3. Restart Sentinel → Status shows "VirusTotal: Enabled"

#### Nmap
1. Download: https://nmap.org/download.html
2. Install with "Add to PATH" option
3. Verify: `nmap --version`
4. Restart Sentinel → Status shows "Nmap: Available"

#### Administrator Mode
For full Security event log access:
```powershell
.\scripts\run_as_admin.bat
```

---

## 🛠️ Development

### Tech Stack
- **Backend**: Python 3.10+, psutil, win32evtlog, requests
- **Frontend**: Qt 6 (PySide6), QML
- **Database**: SQLite 3
- **Architecture**: Clean Architecture, Dependency Injection

### Project Structure
```
graduationp/
├── app/              # Python backend
│   ├── core/         # Domain logic (DI, interfaces)
│   ├── infra/        # Infrastructure (DB, APIs)
│   ├── ui/           # QML ↔ Python bridge
│   └── tests/        # Unit tests
├── qml/              # Qt Quick UI
│   ├── pages/        # Application pages
│   └── components/   # Reusable UI components
├── config/           # Configuration files
├── scripts/          # Helper scripts
│   ├── dev/          # Development tools
│   ├── build/        # Build scripts
│   └── tests/        # Test scripts
├── docs/             # Documentation
│   ├── api/          # API documentation
│   ├── development/  # Development notes
│   ├── guides/       # User guides
│   ├── project/      # Project status
│   └── user/         # User documentation
├── main.py           # Entry point
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

### Build from Source
```powershell
git clone https://github.com/mahmoudbadr238/graduationp.git
cd graduationp
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## 🐛 Troubleshooting

### Common Issues

**"VirusTotal API key required"**  
→ Add API key to `.env` or run in offline mode

**"Nmap not found"**  
→ Install Nmap and add to PATH: `where nmap`

**"Not running with administrator privileges"**  
→ Use `scripts/run_as_admin.bat` for full Security log access

**"Could not set initial property duration"**  
→ Known non-blocking warning (cosmetic only)

### Getting Help
- **Issues**: https://github.com/mahmoudbadr238/graduationp/issues
- **Email**: mahmoudbadr238@gmail.com

---

## 📊 System Requirements

**Minimum:**
- Windows 10 (1809+)
- Python 3.10+
- 2 GB RAM
- 500 MB disk space

**Recommended:**
- Windows 11 (22H2+)
- Python 3.11+
- 4 GB RAM
- 1 GB disk space

---

## 🔐 Security & Privacy

- ✅ **All data stays local** - No telemetry or cloud uploads
- ✅ **SQLite database** in `~/.sentinel/sentinel.db`
- ✅ **No tracking** - Zero usage statistics collected
- ⚠️ **VirusTotal**: File hashes sent (optional) - Don't scan confidential files
- ✅ **Nmap**: Local scans only (no external connections)

For more details, see [SECURITY.md](SECURITY.md) and [Privacy Policy](docs/PRIVACY.md).

---

## 📚 Documentation

Comprehensive documentation is organized in the [`docs/`](docs/) directory:

### Getting Started
- **[Quick Start Guide](docs/QUICKSTART.md)** - Get up and running in 5 minutes
- **[Metrics Reference](docs/guides/METRICS_REFERENCE_GUIDE.md)** - Understanding system metrics

### User Guides
- **[User Manual](docs/user/USER_MANUAL.md)** - Complete feature reference
- **[Layout Guide](docs/guides/SPACIOUS_LAYOUT_GUIDE.md)** - UI/UX best practices

### Development
- **[Architecture Overview](docs/api/README_BACKEND.md)** - System design and structure
- **[API Integration Guide](docs/api/API_INTEGRATION_GUIDE.md)** - VirusTotal & Nmap setup
- **[Contributing Guide](docs/CONTRIBUTING.md)** - How to contribute

### Project Information
- **[Project Status](docs/project/)** - Implementation and completion tracking
- **[Refactoring Reports](docs/development/refactoring/)** - Technical improvements

---

## 🗺️ Roadmap

### v1.0.0-beta (Current) ✅
- Real-time system monitoring
- Windows event viewer with translations
- Scan history with CSV export
- Theme support (dark/light/system)
- Optional VirusTotal & Nmap integration

### v1.1.0 (Next 2-4 weeks)
- VirusTotal file upload + analysis polling
- Background threading for scans
- First-run setup wizard
- Historical metrics charts
- Automated test suite

### v2.0.0 (Future)
- Multi-language support
- Plugin system for custom scanners
- AI-powered threat detection
- Cloud sync (optional)

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m "feat: Add amazing feature"`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

---

## 📜 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Qt Framework** - Cross-platform UI
- **VirusTotal** - Threat intelligence API
- **Nmap** - Network scanning
- **psutil** - System monitoring
- All contributors who helped improve Sentinel

---

<div align="center">

**⭐ Star us on GitHub if you find Sentinel useful! ⭐**

[Report Bug](https://github.com/mahmoudbadr238/graduationp/issues) • [Request Feature](https://github.com/mahmoudbadr238/graduationp/issues) • [Documentation](docs/)

</div>
