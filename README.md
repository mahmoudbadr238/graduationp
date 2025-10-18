# Sentinel - Endpoint Security Suite

A modern desktop security application built with PySide6 and QML, featuring real-time system monitoring, security feature tracking, and a beautiful dark/light theme system.

![Python Version](https://img.shields.io/badge/python-3.13-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.8.1-green)
![License](https://img.shields.io/badge/license-MIT-blue)

## ✨ Features

### 🔍 Security Monitoring
- **Event Viewer** - Real-time security event tracking
- **System Snapshot** - Comprehensive system status overview
  - Operating System Information
  - Hardware Usage (CPU, Memory, GPU, Storage)
  - Network Monitoring
  - Security Features Status (Windows Defender, Firewall, BitLocker, Secure Boot, TPM)
- **Scan History** - Track all security scans
- **Network Scan** - Scan network for potential threats
- **Data Loss Prevention** - Monitor and prevent data leaks

### 🎨 Modern UI/UX
- **Dark/Light/System Themes** - Adaptive theming with smooth transitions
- **Responsive Design** - Clean, modern interface with smooth animations
- **Live Charts** - Real-time performance monitoring with animated charts
- **Keyboard Shortcuts** - Quick navigation (Ctrl+1-7)
- **Accessibility** - Full screen reader support

### ⚡ Performance
- **Live Metrics** - Real-time CPU, Memory, GPU, Network, and Disk monitoring
- **Async Loading** - Fast page switching with async component loading
- **Smooth Animations** - 300ms color transitions, fade effects

## 🚀 Installation

### Prerequisites
- Python 3.13 or higher
- Windows 10/11 (for full security features)

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/sentinel.git
cd sentinel
```

2. **Create virtual environment**
```bash
python -m venv .venv
.venv\Scripts\activate  # On Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Run the application**
```bash
python main.py
```

## 📦 Dependencies

- **PySide6** (6.8.1) - Qt for Python framework
- **psutil** (6.1.0) - System and process monitoring
- **WMI** (1.5.1) - Windows Management Instrumentation (Windows only)

See [requirements.txt](requirements.txt) for complete dependency list.

## 🎮 Usage

### Navigation
- Use the sidebar to navigate between different security tools
- **Keyboard Shortcuts:**
  - `Ctrl+1` - Event Viewer
  - `Ctrl+2` - System Snapshot
  - `Ctrl+3` - Scan History
  - `Ctrl+4` - Network Scan
  - `Ctrl+5` - Scan Tool
  - `Ctrl+6` - Data Loss Prevention
  - `Ctrl+7` - Settings
  - `Esc` - Return to Event Viewer

### Theme Switching
1. Navigate to Settings (Ctrl+7 or click Settings in sidebar)
2. Select your preferred theme:
   - **Dark** - Dark blue-gray color scheme
   - **Light** - Clean white/light gray scheme
   - **System** - Follows your OS theme preference

## 🏗️ Project Structure

```
sentinel/
├── app/                    # Application core
│   ├── application.py     # Qt application setup
│   └── __pycache__/
├── qml/                    # QML frontend
│   ├── components/        # Reusable UI components
│   │   ├── Theme.qml      # Theme singleton
│   │   ├── Card.qml
│   │   ├── SidebarNav.qml
│   │   └── ...
│   ├── pages/             # Application pages
│   │   ├── EventViewer.qml
│   │   ├── SystemSnapshot.qml
│   │   ├── Settings.qml
│   │   └── snapshot/      # System snapshot sub-pages
│   ├── theme/             # Theme definitions
│   ├── ui/                # UI managers
│   │   └── ThemeManager.qml
│   └── main.qml           # Root window
├── docs/                   # Documentation
│   ├── development/       # Development notes
│   └── releases/          # Release notes
├── tests/                  # Test files
├── .github/               # GitHub configuration
├── main.py                # Entry point
├── requirements.txt       # Python dependencies
├── CHANGELOG.md           # Version history
└── README.md              # This file
```

## 🔧 Development

### Architecture
- **Backend**: Python with PySide6 for system monitoring and Qt integration
- **Frontend**: QML for declarative UI with reactive theming
- **Theme System**: Centralized ThemeManager with automatic color transitions
- **Component Pattern**: Reusable components with consistent styling

### Key Components
- **ThemeManager** - Singleton managing dark/light/system themes
- **Theme** - Reactive color tokens bound to ThemeManager
- **AppSurface** - Standard page wrapper with scroll and animations
- **Card/AnimatedCard** - Container components with hover effects
- **LiveMetricTile** - Real-time metric display boxes

### Adding New Pages
1. Create QML file in `qml/pages/`
2. Add to `qml/pages/qmldir`
3. Add Component to `main.qml` pageComponents array
4. Add navigation item to `SidebarNav.qml`

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and updates.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with PySide6 (Qt for Python)
- System monitoring powered by psutil
- Icons and design inspired by modern security tools

## 📧 Contact

Project Link: [https://github.com/mahmoudbadr238/graduationp](https://github.com/yourusername/sentinel)

---

**Note**: Some security features require administrator privileges on Windows.
