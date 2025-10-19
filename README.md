# 🛡️ Sentinel - Endpoint Security Suite# Sentinel - Endpoint Security Suite



<div align="center">A modern desktop security application built with PySide6 and QML, featuring real-time system monitoring, security feature tracking, and a beautiful dark/light theme system.



![Version](https://img.shields.io/badge/version-1.0.0--beta-blue)![Python Version](https://img.shields.io/badge/python-3.13-blue)

![Python](https://img.shields.io/badge/python-3.10%2B-blue)![PySide6](https://img.shields.io/badge/PySide6-6.8.1-green)

![Qt](https://img.shields.io/badge/Qt-6.x-green)![License](https://img.shields.io/badge/license-MIT-blue)

![Platform](https://img.shields.io/badge/platform-Windows-blue)

## ✨ Features

**Real-time system monitoring • Threat detection • Network scanning**

### 🔍 Security Monitoring

[Features](#-features) • [Installation](#-installation) • [Quick Start](#-quick-start) • [Documentation](#-documentation)- **Event Viewer** - Real-time security event tracking

- **System Snapshot** - Comprehensive system status overview

</div>  - Operating System Information

  - Hardware Usage (CPU, Memory, GPU, Storage)

---  - Network Monitoring

  - Security Features Status (Windows Defender, Firewall, BitLocker, Secure Boot, TPM)

## 📋 Overview- **Scan History** - Track all security scans

- **Network Scan** - Scan network for potential threats

Sentinel is a comprehensive endpoint security suite for Windows that provides real-time system monitoring, threat detection, and network analysis. Built with Python and Qt 6, it offers a modern, user-friendly interface for both security professionals and home users.- **Data Loss Prevention** - Monitor and prevent data leaks



### ✨ Key Highlights### 🎨 Modern UI/UX

- **Dark/Light/System Themes** - Adaptive theming with smooth transitions

- **📊 Real-Time Monitoring** - Live CPU, Memory, Disk, and Network metrics- **Responsive Design** - Clean, modern interface with smooth animations

- **🔍 Smart Event Viewer** - Windows event logs in plain English- **Live Charts** - Real-time performance monitoring with animated charts

- **🛡️ Threat Scanning** - VirusTotal integration (optional)- **Keyboard Shortcuts** - Quick navigation (Ctrl+1-7)

- **🌐 Network Scanner** - Nmap-powered device discovery (optional)- **Accessibility** - Full screen reader support

- **🎨 Beautiful UI** - Dark/Light themes with smooth animations

- **💾 Database Persistence** - SQLite storage for all scans### ⚡ Performance

- **Live Metrics** - Real-time CPU, Memory, GPU, Network, and Disk monitoring

---- **Async Loading** - Fast page switching with async component loading

- **Smooth Animations** - 300ms color transitions, fade effects

## 🚀 Quick Start

## 🚀 Installation

### Installation

### Prerequisites

```powershell- Python 3.13 or higher

# Clone repository- Windows 10/11 (for full security features)

git clone https://github.com/mahmoudbadr238/graduationp.git

cd graduationp### Setup



# Create virtual environment1. **Clone the repository**

python -m venv .venv```bash

.venv\Scripts\activategit clone https://github.com/mahmoudbadr238/graduationp.git

cd graduationp

# Install dependencies```

pip install -r requirements.txt

2. **Create virtual environment**

# Run Sentinel```bash

python main.pypython -m venv .venv

```.venv\Scripts\activate  # On Windows

```

### First Launch

3. **Install dependencies**

1. Application opens on **Home** page with live system metrics```bash

2. Navigate using sidebar or keyboard shortcuts (`Ctrl+1` through `Ctrl+7`)pip install -r requirements.txt

3. Try **Event Viewer** (`Ctrl+2`) to see Windows events in plain English```

4. Go to **Settings** (`Ctrl+7`) to change theme

4. **Run the application**

---```bash

python main.py

## ✨ Features```



### Core Features (No Setup Required)## 📦 Dependencies



#### 📊 Live System Monitoring- **PySide6** (6.8.1) - Qt for Python framework

- Real-time CPU, Memory, Disk, Network metrics (1 Hz refresh)- **psutil** (6.1.0) - System and process monitoring

- GPU usage monitoring (when available)- **WMI** (1.5.1) - Windows Management Instrumentation (Windows only)

- Animated progress bars and smooth transitions

See [requirements.txt](requirements.txt) for complete dependency list.

#### 🔍 Intelligent Event Viewer

- Translates technical Event IDs to user-friendly messages## 🎮 Usage

  - `Event 6005` → "Windows Event Log service started"

  - `Event 4624` → "User successfully logged in"### Navigation

- Color-coded severity: ERROR (red), WARNING (yellow), INFO (blue), SUCCESS (green)- Use the sidebar to navigate between different security tools

- Loads from Application, System, and Security logs- **Keyboard Shortcuts:**

  - `Ctrl+1` - Event Viewer

#### 🖥️ System Snapshot  - `Ctrl+2` - System Snapshot

- **Overview**: All metrics at a glance  - `Ctrl+3` - Scan History

- **Hardware**: CPU, RAM, GPU specifications  - `Ctrl+4` - Network Scan

- **Network**: Interface statistics and active connections  - `Ctrl+5` - Scan Tool

- **OS Info**: Windows version, build, uptime  - `Ctrl+6` - Data Loss Prevention

  - `Ctrl+7` - Settings

#### 📜 Scan History  - `Esc` - Return to Event Viewer

- View all completed scans

- Export to CSV (Downloads folder)### Theme Switching

- Filter by type (File, URL, Network)1. Navigate to Settings (Ctrl+7 or click Settings in sidebar)

2. Select your preferred theme:

#### 🎨 Appearance   - **Dark** - Dark blue-gray color scheme

- **Dark Mode**: Low-light friendly   - **Light** - Clean white/light gray scheme

- **Light Mode**: Bright environment optimized   - **System** - Follows your OS theme preference

- **System Sync**: Matches Windows theme automatically

- Smooth 300ms color transitions## 🏗️ Project Structure



### Optional Features (Require Setup)```

sentinel/

#### 🛡️ VirusTotal Integration├── app/                    # Application core

- File scanning against 70+ antivirus engines│   ├── application.py     # Qt application setup

- URL reputation checks│   └── __pycache__/

- Free tier: 4 requests/min, 500/day├── qml/                    # QML frontend

│   ├── components/        # Reusable UI components

**Setup**: [API Integration Guide](docs/API_INTEGRATION_GUIDE.md#virustotal-integration)│   │   ├── Theme.qml      # Theme singleton

│   │   ├── Card.qml

#### 🌐 Network Scanner│   │   ├── SidebarNav.qml

- Device discovery on local network│   │   └── ...

- Port scanning (Quick: top 100, Full: all 65K)│   ├── pages/             # Application pages

- Service version detection│   │   ├── EventViewer.qml

│   │   ├── SystemSnapshot.qml

**Setup**: [Nmap Installation Guide](docs/API_INTEGRATION_GUIDE.md#nmap-integration)│   │   ├── Settings.qml

│   │   └── snapshot/      # System snapshot sub-pages

---│   ├── theme/             # Theme definitions

│   ├── ui/                # UI managers

## 🔧 Configuration│   │   └── ThemeManager.qml

│   └── main.qml           # Root window

### Basic Setup├── docs/                   # Documentation

│   ├── development/       # Development notes

Copy `.env.example` to `.env` and configure:│   └── releases/          # Release notes

├── tests/                  # Test files

```env├── .github/               # GitHub configuration

# Optional: VirusTotal API Key (get from virustotal.com/gui/join-us)├── main.py                # Entry point

VT_API_KEY=├── requirements.txt       # Python dependencies

├── CHANGELOG.md           # Version history

# Optional: Nmap path (auto-detected if in PATH)└── README.md              # This file

NMAP_PATH=```



# Disable all external APIs## 🔧 Development

OFFLINE_ONLY=false

```### Architecture

- **Backend**: Python with PySide6 for system monitoring and Qt integration

### Enable Optional Features- **Frontend**: QML for declarative UI with reactive theming

- **Theme System**: Centralized ThemeManager with automatic color transitions

#### VirusTotal- **Component Pattern**: Reusable components with consistent styling

1. Get free API key: https://www.virustotal.com/gui/join-us

2. Add to `.env`: `VT_API_KEY=your_key_here`### Key Components

3. Restart Sentinel → Status shows "VirusTotal: Enabled"- **ThemeManager** - Singleton managing dark/light/system themes

- **Theme** - Reactive color tokens bound to ThemeManager

#### Nmap- **AppSurface** - Standard page wrapper with scroll and animations

1. Download: https://nmap.org/download.html- **Card/AnimatedCard** - Container components with hover effects

2. Install with "Add to PATH" option- **LiveMetricTile** - Real-time metric display boxes

3. Verify: `nmap --version`

4. Restart Sentinel → Status shows "Nmap: Available"### Adding New Pages

1. Create QML file in `qml/pages/`

#### Administrator Mode2. Add to `qml/pages/qmldir`

For full Security event log access:3. Add Component to `main.qml` pageComponents array

```powershell4. Add navigation item to `SidebarNav.qml`

.\run_as_admin.bat

```## 📝 Changelog



---See [CHANGELOG.md](CHANGELOG.md) for version history and updates.



## 📚 Documentation## 🤝 Contributing



- **[API Integration Guide](docs/API_INTEGRATION_GUIDE.md)** - VirusTotal & Nmap setupContributions are welcome! Please feel free to submit a Pull Request.

- **[Quick Start Guide](QUICKSTART.md)** - 5-minute getting started

- **[Architecture Overview](docs/README_BACKEND.md)** - Clean Architecture, DI1. Fork the repository

- **[QA Report](docs/development/QA_COMPREHENSIVE_REPORT.md)** - Testing results2. Create your feature branch (`git checkout -b feature/AmazingFeature`)

- **[Contributing Guide](CONTRIBUTING.md)** - How to contribute3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)

- **[Changelog](CHANGELOG.md)** - Version history4. Push to the branch (`git push origin feature/AmazingFeature`)

5. Open a Pull Request

---

## 📄 License

## 🛠️ Development

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Tech Stack

- **Backend**: Python 3.10+, psutil, win32evtlog, requests## 🙏 Acknowledgments

- **Frontend**: Qt 6 (PySide6), QML

- **Database**: SQLite 3- Built with PySide6 (Qt for Python)

- **Architecture**: Clean Architecture, Dependency Injection- System monitoring powered by psutil

- Icons and design inspired by modern security tools

### Project Structure

```## 📧 Contact

graduationp/

├── app/           # Python backendProject Link: [https://github.com/mahmoudbadr238/graduationp](https://github.com/mahmoudbadr238/graduationp)

│   ├── core/      # Domain logic (DI, interfaces)

│   ├── infra/     # Infrastructure (DB, APIs)---

│   ├── ui/        # QML ↔ Python bridge

│   └── tests/     # Unit tests**Note**: Some security features require administrator privileges on Windows.

├── qml/           # Qt Quick UI
│   ├── pages/     # Application pages
│   └── components/ # Reusable UI components
└── docs/          # Documentation
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
→ Use `run_as_admin.bat` for full Security log access

**"Could not set initial property duration"**  
→ Known non-blocking warning (cosmetic only)

### Getting Help
- **Issues**: https://github.com/mahmoudbadr238/graduationp/issues
- **Discussions**: https://github.com/mahmoudbadr238/graduationp/discussions
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
- Mobile companion app
- Multi-language support
- Plugin system for custom scanners
- AI-powered threat detection
- Cloud sync (optional)

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

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

Made with ❤️ by [Mahmoud Badr](https://github.com/mahmoudbadr238)

[Report Bug](https://github.com/mahmoudbadr238/graduationp/issues) • [Request Feature](https://github.com/mahmoudbadr238/graduationp/issues) • [Documentation](docs/)

</div>
