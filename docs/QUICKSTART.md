# Quick Start Guide

Get Sentinel up and running in 5 minutes!

## ⚡ Prerequisites

- Windows 10 or 11
- Python 3.10+ installed ([Download](https://www.python.org/downloads/))
- Git (optional, for cloning)

## 📥 Installation

### Option 1: Clone from GitHub
```bash
git clone https://github.com/mahmoudbadr238/graduationp.git
cd graduationp
```

### Option 2: Download ZIP
1. Download the repository as ZIP
2. Extract to a folder
3. Open terminal/PowerShell in that folder

## 🔧 Setup

1. **Create virtual environment**
```bash
python -m venv .venv
```

2. **Activate virtual environment**
```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# Windows CMD
.venv\Scripts\activate.bat
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

This will install:
- PySide6 6.8.1 (Qt for Python)
- psutil 6.1.0 (system monitoring)
- WMI 1.5.1 (Windows management)

## ▶️ Run

```bash
python main.py
```

The application will launch in a new window!

## 🎨 First Steps

1. **Explore the interface**
   - Click through the sidebar menu items
   - Try the System Snapshot page

2. **Change the theme**
   - Click "Settings" in the sidebar (or press `Ctrl+7`)
   - Select "Light", "Dark", or "System"
   - Watch the smooth transition!

3. **Try keyboard shortcuts**
   - `Ctrl+1` - Event Viewer
   - `Ctrl+2` - System Snapshot
   - `Ctrl+3` - Scan History
   - `Ctrl+4` - Network Scan
   - `Ctrl+5` - Scan Tool
   - `Ctrl+6` - Data Loss Prevention
   - `Ctrl+7` - Settings
   - `Esc` - Return to Event Viewer

## 🔍 Features to Check Out

### AI Setup (Optional but Recommended)
Set up Groq for free AI-powered security analysis:
1. Get a free API key at [console.groq.com](https://console.groq.com/)
2. Create a `.env` file in the project root:
   ```
   GROQ_API_KEY=gsk_your-key-here
   ```
3. Restart Sentinel — AI features are now available in Event Viewer and Security Assistant

> Without an API key, Sentinel works fully offline using its built-in knowledge base (500+ event IDs).

### System Snapshot
Navigate to System Snapshot (Ctrl+2) and explore:
- **Overview** — Security status summary
- **OS Info** — Operating system details
- **Hardware** — Live CPU, Memory, GPU, Storage charts
- **Network** — Upload/Download monitoring
- **Security** — Windows security features status

### Event Viewer
Open Event Viewer (Ctrl+1) for AI-powered Windows event analysis:
- Click any event for a plain-English explanation
- Color-coded severity (Critical/Error/Warning/Info)
- Run as Admin for Security log access

### Scan Center
Open Scan Center (Ctrl+5) for file and URL scanning:
- Drag-and-drop files for analysis
- Paste URLs for threat detection
- VirusTotal integration (optional, set `VT_API_KEY` in `.env`)

### Secure File Shredder
Open File Functions for secure file deletion:
- Choose overwrite passes (1/3/7/35 Gutmann)
- Two-step confirmation for safety
- Real-time progress with cancellation

### Live Monitoring
Watch the live charts update in real-time:
- CPU usage updates every second
- Memory percentage displayed
- Network throughput graphs
- GPU telemetry (NVIDIA/AMD)

## ⚠️ Common Issues

### "Application is running without administrative privileges"
This is a warning, not an error. Some security features require admin rights.

**To run as admin:**
1. Right-click `main.py`
2. Select "Run as administrator"

### Import errors
Make sure virtual environment is activated and dependencies installed:
```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

### QML errors
Ensure you're using Python 3.10+ and PySide6 6.6+:
```bash
python --version
pip show PySide6
```

## 📚 Learn More

- Full documentation: [README.md](README.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)

## 🆘 Need Help?

- Check [README.md](README.md) for detailed documentation
- Open an issue on GitHub
- Review the docs in `docs/` folder

---

Enjoy using Sentinel! 🛡️
