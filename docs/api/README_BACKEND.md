# Sentinel Backend Architecture

## Overview

Sentinel uses a **Clean OOP Architecture** with strict separation of concerns, dependency injection, and testable components. The backend is built entirely in Python using PySide6 for QML integration.

## Architecture Layers

### 1. Core Domain (`app/core/`)

**Purpose:** Business logic, interfaces, and data models

**Files:**
- `types.py`: Domain data types (`ScanRecord`, `EventItem`, `ScanType` enum)
- `interfaces.py`: Abstract base classes defining contracts (`ISystemMonitor`, `INetworkScanner`, etc.)
- `errors.py`: Custom exceptions (`SentinelError`, `IntegrationDisabled`, `ExternalToolMissing`)
- `container.py`: Dependency injection container with `configure()` function

**Design Principles:**
- No external dependencies (except ABC from stdlib)
- Pure data structures using `@dataclass`
- Interface contracts using `ABC` and `@abstractmethod`

### 2. Infrastructure (`app/infra/`)

**Purpose:** Concrete implementations of core interfaces

**Services:**

| Service | File | Interface | Description |
|---------|------|-----------|-------------|
| System Monitor | `system_monitor_psutil.py` | `ISystemMonitor` | CPU, memory, GPU, network, disk metrics using `psutil` |
| Event Reader | `events_windows.py` | `IEventReader` | Windows event log reader using `win32evtlog` |
| Network Scanner | `nmap_cli.py` | `INetworkScanner` | Network scanning via Nmap CLI |
| File Scanner | `file_scanner.py` | `IFileScanner` | SHA256 hash calculation + optional VirusTotal lookup |
| URL Scanner | `url_scanner.py` | `IUrlScanner` | URL reputation check via VirusTotal API |
| Repository | `sqlite_repo.py` | `IScanRepository`, `IEventRepository` | SQLite database for scans and events |
| VirusTotal Client | `vt_client.py` | N/A | REST API v3 client for threat intelligence |

### 3. UI Bridge (`app/ui/`)

**Purpose:** QObject facade connecting QML frontend to Python backend

**File:** `backend_bridge.py`

**Exposed to QML:**
- **Signals:**
  - `snapshotUpdated(dict)`: System metrics snapshot (every 1 second when live)
  - `eventsLoaded(list)`: Windows event log entries
  - `toast(str, str)`: Notifications (level, message)
  - `scanFinished(str, dict)`: Scan completion (type, result)

- **Slots:**
  - `startLive()`: Begin live system monitoring (1 Hz)
  - `stopLive()`: Stop live monitoring
  - `loadRecentEvents()`: Load Windows event log
  - `runNetworkScan(str, bool)`: Run network scan (target, fast mode)
  - `scanFile(str)`: Scan file by path
  - `scanUrl(str)`: Scan URL via VirusTotal
  - `getScanHistory() -> list`: Get recent scan records

### 4. Configuration (`app/config/`)

**Purpose:** Environment-based settings

**File:** `settings.py`

**Environment Variables:**
```env
VT_API_KEY=your_virustotal_api_key_here
OFFLINE_ONLY=false
NMAP_PATH=/usr/bin/nmap
```

Load from `.env` file using `python-dotenv`.

## Dependency Injection Flow

```
1. Application Start (main.py)
   ↓
2. Configure DI Container (core/container.py)
   - Register all interface → implementation mappings
   ↓
3. Create Backend Bridge (ui/backend_bridge.py)
   - Resolve dependencies from DI container
   ↓
4. Expose to QML via setContextProperty("Backend", bridge)
   ↓
5. QML calls Backend.startLive() → emits snapshotUpdated signal
```

## Data Flow Example: Live Monitoring

```
QML: Backend.startLive()
  ↓
BackendBridge.startLive() [Slot]
  - Starts QTimer (1 second interval)
  ↓
Timer tick → BackendBridge._tick()
  - Calls system_monitor.snapshot()
  ↓
PsutilSystemMonitor.snapshot() [Implementation]
  - Returns {"cpu": {...}, "mem": {...}, ...}
  ↓
BackendBridge emits snapshotUpdated(dict)
  ↓
QML: Connections { target: Backend; onSnapshotUpdated: ... }
  - Updates UI with live data
```

## External Integrations

### Nmap (Network Scanning)
- **Type:** Local CLI tool
- **Requirement:** Nmap installed from https://nmap.org/
- **Detection:** Auto-detects in PATH or common Windows locations
- **Usage:** `nmap -F -T4 192.168.1.0/24` (fast scan) or `nmap -sV -T3 target` (comprehensive)

### VirusTotal (Threat Intelligence)
- **Type:** REST API v3
- **Requirement:** API key from https://www.virustotal.com/
- **Configuration:** Set `VT_API_KEY` in `.env`
- **Usage:**
  - File scanning: Submit SHA256 hash for reputation check
  - URL scanning: Submit URL for analysis
  - Rate limits: Free tier = 4 requests/minute

## Database Schema

**Location:** `%USERPROFILE%/.sentinel/sentinel.db`

### `scans` Table
```sql
CREATE TABLE scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    type TEXT NOT NULL,  -- NETWORK, FILE, URL
    target TEXT NOT NULL,
    status TEXT NOT NULL,
    findings TEXT,  -- JSON
    meta TEXT  -- JSON
)
```

### `events` Table
```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,  -- INFO, WARNING, ERROR, SUCCESS, FAILURE
    source TEXT NOT NULL,  -- System, Application, Security
    message TEXT NOT NULL
)
```

## Testing

### Unit Tests (`app/tests/`)

**Run tests:**
```bash
pytest app/tests/
```

**Test files:**
- `test_container.py`: DI container registration/resolution
- `test_repos.py`: SQLite repository CRUD operations
- `test_services.py`: File scanner hash calculation

**Design:**
- No Qt dependencies (tests run without GUI)
- Use `pytest` fixtures for temporary databases/files
- Test against interfaces, not implementations

## Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Install External Tools (Optional)
- **Nmap:** Download from https://nmap.org/download.html
- **VirusTotal API Key:** Sign up at https://www.virustotal.com/

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your settings
```

### 4. Run Application
```bash
python main.py
```

## Configuration Options

### Offline Mode
Set `OFFLINE_ONLY=true` in `.env` to disable all external integrations:
- Network scanning disabled
- VirusTotal lookups disabled
- Only local system monitoring and event reading

### Custom Nmap Path
If Nmap is not in PATH:
```env
NMAP_PATH=C:\Program Files (x86)\Nmap\nmap.exe
```

## Error Handling

### IntegrationDisabled
Raised when a feature is disabled by configuration:
```python
try:
    scanner = DI.resolve(INetworkScanner)
except IntegrationDisabled as e:
    print(f"Feature disabled: {e}")
```

### ExternalToolMissing
Raised when required external tool not found:
```python
try:
    nmap = NmapCli()
except ExternalToolMissing as e:
    print(f"Install Nmap: {e}")
```

## QML Integration Example

### SystemSnapshot Page
```qml
import QtQuick

AppSurface {
    id: root
    
    Component.onCompleted: {
        Backend.startLive()
    }
    
    Component.onDestruction: {
        Backend.stopLive()
    }
    
    Connections {
        target: Backend
        
        function onSnapshotUpdated(data) {
            cpuText.text = data.cpu.usage.toFixed(1) + "%"
            memText.text = (data.mem.used / 1e9).toFixed(1) + " GB"
        }
    }
    
    Text {
        id: cpuText
        text: "0.0%"
    }
}
```

### NetworkScan Page
```qml
Button {
    text: "Scan Network"
    onClicked: {
        Backend.runNetworkScan(targetField.text, true)
    }
}

Connections {
    target: Backend
    
    function onScanFinished(type, result) {
        if (type === "network") {
            console.log("Found hosts:", result.hosts)
        }
    }
    
    function onToast(level, message) {
        // Show notification
        toastManager.show(level, message)
    }
}
```

## Performance Considerations

### Live Monitoring
- Updates every 1 second (1 Hz)
- `psutil` operations are non-blocking
- GPU monitoring optional (requires pynvml or GPUtil)

### Network Scanning
- **Blocking operation:** Runs in main thread (consider QThread for production)
- Fast scan: ~10-30 seconds
- Comprehensive scan: 1-5 minutes
- Timeout: 5 minutes maximum

### File Scanning
- **Blocking operation:** SHA256 calculation for large files
- VirusTotal API: ~1-2 seconds per request
- Rate limit: 4 requests/minute (free tier)

## Production Recommendations

### Threading
Move blocking operations to QThread:
```python
class ScanWorker(QThread):
    finished = Signal(dict)
    
    def run(self):
        result = self.scanner.scan(self.target)
        self.finished.emit(result)
```

### Caching
Add caching layer for VirusTotal lookups:
```python
class CachedVTClient:
    def __init__(self, vt_client):
        self.vt = vt_client
        self.cache = {}
    
    def scan_file_hash(self, sha256):
        if sha256 not in self.cache:
            self.cache[sha256] = self.vt.scan_file_hash(sha256)
        return self.cache[sha256]
```

### Logging
Replace `print()` with proper logging:
```python
import logging
logger = logging.getLogger(__name__)

logger.info("Backend initialized")
logger.error(f"Scan failed: {e}")
```

## Troubleshooting

### "Nmap not found"
1. Install Nmap from https://nmap.org/download.html
2. Add to PATH or set `NMAP_PATH` in `.env`

### "VirusTotal API key not configured"
1. Sign up at https://www.virustotal.com/
2. Copy API key to `.env`: `VT_API_KEY=your_key_here`

### "Import win32evtlog could not be resolved"
```bash
pip install pywin32
```

### Database locked error
- Close all application instances
- Delete `%USERPROFILE%/.sentinel/sentinel.db`
- Restart application

## License

MIT License - See LICENSE file for details
