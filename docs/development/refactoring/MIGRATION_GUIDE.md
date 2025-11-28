# Backend Refactoring - Migration & Integration Guide

**Target Audience**: Developers integrating refactored backend with QML frontend  
**Difficulty**: Intermediate  
**Time to Complete**: 30-60 minutes  

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [What Changed](#what-changed)
3. [File Replacement](#file-replacement)
4. [QML Integration](#qml-integration)
5. [Testing Your Integration](#testing-integration)
6. [Troubleshooting](#troubleshooting)

---

## Overview

The backend refactoring delivers **non-blocking operations**, **proper thread safety**, and **clean QML integration** through:
- Multi-phase startup orchestration
- Thread pool workers with cancellation
- Structured logging with Qt signals
- Async service facade with result caching
- Comprehensive error handling

**Key Benefit**: UI stays responsive during all backend operations.

---

## What Changed

### ✨ Improvements Per File

#### 1. `startup_orchestrator.py` → `startup_orchestrator_refactored.py`

**Before**: Sequential initialization, no error recovery
```python
logging_setup()
backend_bridge_init()
gpu_service_init()
# If any fails, app might be partially initialized
```

**After**: Multi-phase with error recovery
```python
orchestrator = StartupOrchestrator()
orchestrator.schedule_immediate("logging", setup_logging)
orchestrator.schedule_deferred("backend", 100, init_backend)
orchestrator.schedule_background("gpu", 300, init_gpu)
orchestrator.taskFailed.connect(handle_failure)  # Recover gracefully
```

**Impact**: Better startup resilience, easier to add services

#### 2. `workers.py` → `workers_refactored.py`

**Before**: Basic worker, no timeout, no progress, no watchdog
```python
worker = Worker(do_work)
thread_pool.start(worker)
# Hope it completes... no way to cancel or detect if stuck
```

**After**: Full-featured worker with cancellation, heartbeat, progress
```python
worker = CancellableWorker(
    "scan-file-123",
    scan_file_task,
    timeout_ms=60000,
    path="/path/to/file"
)
worker.signals.progress.connect(lambda wid, pct: update_bar(pct))
worker.signals.error.connect(on_error)
watchdog.register_worker(worker.worker_id)
thread_pool.start(worker)
```

**Impact**: Can cancel long operations, track progress, detect stalls

#### 3. `logging_setup.py` → `logging_setup_refactored.py`

**Before**: Print statements, inconsistent formatting
```python
print(f"✓ Events loaded: {count}")
logger.info("GPU service started")
# Different formats, Unicode issues on Windows
```

**After**: Structured logs with Qt signals, UTF-8 encoding
```python
[2025-11-12 10:30:45] [INFO] app.core: Events loaded: 300
[2025-11-12 10:30:46] [OK] GPU service started
# Signals sent to QML: toast.emit("info", "GPU service started")
```

**Impact**: Consistent logging, QML notifications, no encoding errors

#### 4. `backend_bridge.py` → `backend_bridge_refactored.py`

**Before**: Blocking operations freeze UI
```python
def load_events(self):
    events = self.event_reader.tail(300)  # Blocks until complete
    self.snapshotUpdated.emit(events)     # Too late, UI was frozen
```

**After**: Async workers, UI stays responsive
```python
def load_events(self):
    worker = CancellableWorker("load-events", load_task, timeout_ms=10000)
    worker.signals.finished.connect(lambda wid, events: 
        self.eventsLoaded.emit(events))
    watchdog.register_worker(worker.worker_id)
    thread_pool.start(worker)
    # Returns immediately, UI responsive
```

**Impact**: 0ms main thread blocking during operations

#### 5. `gpu_service.py` - No changes needed

The GPU service is already well-designed. The refactoring report recommends enhancements (subprocess lifecycle, circuit breaker) but not critical.

---

## File Replacement

### Step 1: Backup Originals (Recommended)

```powershell
# Create backup directory
New-Item -ItemType Directory -Path app/core/backup -Force

# Backup original files
Copy-Item app/core/startup_orchestrator.py app/core/backup/
Copy-Item app/core/workers.py app/core/backup/
Copy-Item app/core/logging_setup.py app/core/backup/
Copy-Item app/ui/backend_bridge.py app/ui/backup/
```

### Step 2: Replace With Refactored Versions

```powershell
# Replace files (must do all at once to avoid partial state)
Copy-Item app/core/startup_orchestrator_refactored.py app/core/startup_orchestrator.py -Force
Copy-Item app/core/workers_refactored.py app/core/workers.py -Force
Copy-Item app/core/logging_setup_refactored.py app/core/logging_setup.py -Force
Copy-Item app/ui/backend_bridge_refactored.py app/ui/backend_bridge.py -Force
```

### Step 3: Verify Replacement

```powershell
# Check that refactored features are present
Select-String -Path app/core/workers.py -Pattern "class.*Watchdog"
# Should find: "class WorkerWatchdog(QObject):"

Select-String -Path app/ui/backend_bridge.py -Pattern "snapshotUpdated"
# Should find: "snapshotUpdated = Signal(dict)"
```

---

## QML Integration

### Phase 1: Connect Backend Signals

**File**: `qml/pages/SystemSnapshot.qml`

```qml
import QtQuick
import "../components"
import "../theme"

AppSurface {
    id: root
    
    // Reference to backend
    required property var backendBridge
    
    // Connect to live snapshot updates
    Connections {
        target: backendBridge
        
        function onSnapshotUpdated(snapshot) {
            // Update all UI elements from snapshot
            cpuValue.text = snapshot.cpu.usage.toFixed(1) + "%"
            memValue.text = snapshot.mem.percent.toFixed(1) + "%"
            gpuValue.text = snapshot.gpu.usage.toFixed(1) + "%"
            
            // Update charts
            cpuChart.pushValue(snapshot.cpu.usage / 100)
            memChart.pushValue(snapshot.mem.percent / 100)
        }
    }
    
    // Start live monitoring on page load
    Component.onCompleted: {
        backendBridge.startLive()
    }
    
    // Stop when page unloaded
    Component.onDestruction: {
        backendBridge.stopLive()
    }
}
```

### Phase 2: Add Error Toast Notifications

**File**: `qml/pages/SettingsPage.qml`

```qml
AppSurface {
    id: root
    required property var backendBridge
    
    // Toast notification component
    Toast {
        id: notification
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
    }
    
    // Listen for backend errors
    Connections {
        target: backendBridge
        
        function onToast(level, message) {
            // Display error/warning/info messages
            switch(level) {
                case "error":
                    notification.show("Error", message, "red")
                    break
                case "warning":
                    notification.show("Warning", message, "orange")
                    break
                case "success":
                    notification.show("Success", message, "green")
                    break
                default:
                    notification.show("Info", message, "blue")
            }
        }
    }
}
```

### Phase 3: Add Scan Progress Tracking

**File**: `qml/components/ScanDialog.qml`

```qml
Dialog {
    id: scanDialog
    required property var backendBridge
    
    ProgressBar {
        id: progressBar
        from: 0
        to: 100
    }
    
    Text {
        id: statusText
        text: "Preparing..."
    }
    
    // Track scan progress
    Connections {
        target: backendBridge
        
        function onScanProgress(taskId, percent) {
            if (taskId === scanDialog.currentTaskId) {
                progressBar.value = percent
                statusText.text = `Scanning... ${percent}%`
            }
        }
        
        function onScanFinished(scanType, result) {
            if (scanType === scanDialog.currentScanType) {
                if (result.success) {
                    statusText.text = "Scan completed!"
                    progressBar.value = 100
                    // Process results
                    displayScanResults(result)
                } else {
                    statusText.text = `Scan failed: ${result.error}`
                    notification.show("error", result.error)
                }
                close()
            }
        }
    }
    
    // Start scan
    function startScan(scanType) {
        currentScanType = scanType
        currentTaskId = "scan-" + Date.now()
        progressBar.value = 0
        statusText.text = "Starting scan..."
        
        if (scanType === "file") {
            backendBridge.scanFile(selectedFilePath)
        } else if (scanType === "url") {
            backendBridge.scanUrl(selectedUrl)
        }
    }
}
```

### Phase 4: Register Backend as QML Context Property

**File**: `app/application.py`

Already done! But verify:
```python
# In Application.__init__()
self.backend_bridge = BackendBridge()
self.engine.rootContext().setContextProperty("backendBridge", self.backend_bridge)
```

---

## Testing Integration

### Test 1: Backend Startup
```powershell
python test_backend_startup.py
# Expected: 4/4 tests passed
```

### Test 2: App Launch (No Errors)
```powershell
python main.py 2>&1 | Select-String -Pattern "ERROR|charmap|failed"
# Expected: No matches (or only expected warnings)
```

### Test 3: Live Monitoring
1. Launch app
2. Go to **System Overview** tab
3. Watch CPU/RAM/Disk values update every 3 seconds
4. **Expected**: Values change smoothly without UI freeze

### Test 4: Event Loading
1. Launch app
2. Go to **Event Viewer** tab
3. Watch for events to load without freezing UI
4. **Expected**: Spinner spins, events appear, no frozen UI

### Test 5: Error Handling
1. Launch app
2. Verify toast notification appears if nmap not found
3. Check Settings page displays error message
4. **Expected**: User sees friendly error message, not Python exception

### Test 6: Graceful Shutdown
1. Launch app with all operations running
2. Close app window
3. Check that workers cancelled and app closes in <5 seconds
4. **Expected**: No crashes, clean shutdown

---

## Troubleshooting

### Issue: "Cannot import name 'CancellableWorker'"
**Cause**: Using old workers.py that doesn't have the class  
**Solution**:
```powershell
# Verify you replaced the file
Select-String -Path app/core/workers.py -Pattern "class CancellableWorker"
# If no match, copy refactored version again
Copy-Item app/core/workers_refactored.py app/core/workers.py -Force
```

### Issue: "snapshotUpdated signal not emitted"
**Cause**: Live monitoring not started or connection not registered  
**Solution** in QML:
```qml
Component.onCompleted: {
    backendBridge.startLive()  // Make sure this is called
}

Connections {
    target: backendBridge
    onSnapshotUpdated: console.log("Signal received!")  // Debug
}
```

### Issue: Worker not cancelling on shutdown
**Cause**: Worker not registered with watchdog  
**Solution** in Python:
```python
watchdog = get_watchdog()
watchdog.register_worker(worker.worker_id)
```

### Issue: "charmap codec can't encode character"
**Cause**: Using original events_windows.py with Unicode  
**Solution**:
```powershell
# Verify the fix is present
Select-String -Path app/infra/events_windows.py -Pattern "\[OK\] Read"
# Should find: "[OK] Read {len(...)} events from {source}"
```

### Issue: Performance hasn't improved
**Cause**: Async operations still blocking on main thread  
**Solution**:
1. Verify workers are actually on thread pool:
   ```python
   QThreadPool.globalInstance().start(worker)  # Must call
   ```
2. Check that signals are connected:
   ```python
   worker.signals.finished.connect(on_complete)  # Must connect
   ```
3. Profile with `cProfile` to find bottleneck

---

## Quick Reference

### Common Signal Connections

| Signal | Parameters | Use Case |
|--------|-----------|----------|
| `snapshotUpdated` | `dict` (metrics) | Live system monitoring |
| `eventsLoaded` | `list` (events) | Display event list |
| `scansLoaded` | `list` (scans) | Display scan history |
| `scanFinished` | `str` (type), `dict` (result) | Scan completion |
| `scanProgress` | `str` (task_id), `int` (percent) | Progress bar |
| `toast` | `str` (level), `str` (message) | Error notifications |

### Common Methods

| Method | Async | Returns | Use Case |
|--------|-------|---------|----------|
| `startLive()` | No | None | Start 2-3s update interval |
| `stopLive()` | No | None | Stop live monitoring |
| `loadRecentEvents()` | Yes | - | Load last 300 events |
| `runNetworkScan()` | Yes | - | Scan network range |
| `scanFile()` | Yes | - | VirusTotal file scan |
| `scanUrl()` | Yes | - | VirusTotal URL scan |

---

## Next Steps

1. **Replace Files**: Follow "File Replacement" section above
2. **Update QML**: Add signal connections as shown
3. **Test Integration**: Run all 6 tests from "Testing Integration"
4. **Monitor Logs**: Watch `%APPDATA%\Sentinel\logs\sentinel.log`
5. **Measure Performance**: Time startup and operations before/after
6. **Document Changes**: Update your team's development guide

---

## Support

For detailed information:
- **Architecture**: See `BACKEND_REFACTORING_REPORT.md`
- **Quick Start**: See `BACKEND_QUICK_REFERENCE.md`
- **Validation**: See `DEPLOYMENT_VALIDATION.md`
- **Testing**: Run `test_backend_startup.py`

---

*Last Updated: November 12, 2025*
