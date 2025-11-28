# BACKEND REFACTORING - QUICK REFERENCE

## 📍 Refactored Files Location

All refactored files are in `app/` directory with `_refactored` suffix:

```
app/core/
├── startup_orchestrator_refactored.py     # Multi-phase startup ✨
├── workers_refactored.py                  # Async worker infrastructure ✨
└── logging_setup_refactored.py            # Structured logging with Qt adapter ✨

app/ui/
├── backend_bridge_refactored.py           # QML-facing service facade ✨
└── gpu_service.py                         # (Already well-designed, ready for enhancement)
```

---

## 🔄 Key Improvements At A Glance

### 1. Signal/Slot Architecture

**BEFORE**: Ad-hoc signal definitions
```python
snapshotUpdated = Signal(dict)
eventsLoaded = Signal(list)
```

**AFTER**: Comprehensive signal definitions with types and documentation
```python
snapshotUpdated = Signal(dict)          # System metrics snapshot
eventsLoaded = Signal(list)             # Windows event records
scansLoaded = Signal(list)              # Scan history
scanFinished = Signal(str, dict)        # type, result
scanProgress = Signal(str, int)         # task_id, percent
toast = Signal(str, str)                # level, message
```

---

### 2. Async/Thread Safety

**BEFORE**: Blocking operations freeze UI
```python
def scanFile(self, path: str):
    # This blocks the main thread!
    result = self.file_scanner.scan_file(path)
    self.scanFinished.emit("file", result)
```

**AFTER**: Non-blocking workers with watchdog
```python
def scanFile(self, path: str):
    worker = CancellableWorker("scan-file-...", scan_task, timeout_ms=60000)
    worker.signals.finished.connect(on_success)
    worker.signals.error.connect(on_error)
    
    watchdog.register_worker(worker.worker_id)
    thread_pool.start(worker)
    # Returns immediately, UI stays responsive
```

---

### 3. Service Orchestration

**BEFORE**: Linear initialization
```python
setup_logging()
setup_backend()
setup_gpu()
setup_scanner()
```

**AFTER**: Multi-phase orchestration with error recovery
```python
orchestrator.add_immediate("logging", setup_logging)          # Critical
orchestrator.add_deferred("backend", 100, setup_backend)      # Important
orchestrator.add_background("gpu", 300, setup_gpu)            # Background
orchestrator.add_background("scanner", 300, setup_scanner)

orchestrator.taskFailed.connect(handle_failure)
orchestrator.startupComplete.connect(on_complete)
orchestrator.execute()  # Returns immediately, runs async
```

---

### 4. Structured Logging

**BEFORE**: Inconsistent logging
```python
logger.info("Starting")
print("Backend initialized")
logger.debug("Value: " + str(data))
```

**AFTER**: Structured with timestamps and levels
```python
[2024-01-15 10:30:45] [INFO    ] app.core: Starting
[2024-01-15 10:30:46] [WARNING ] app.infra: Nmap not found
[2024-01-15 10:30:47] [ERROR   ] app.ui: Failed to load events

# Qt signal adapter for QML notifications
adapter.logEmitted.connect(lambda lvl, name, msg: show_toast(lvl, msg))
```

---

## 💻 Common Usage Patterns

### Pattern 1: Live System Monitoring

```python
from app.ui.backend_bridge import BackendBridge

backend = BackendBridge()
backend.snapshotUpdated.connect(on_snapshot)
backend.startLive()  # Emits snapshot every 3s
backend.stopLive()   # Stop monitoring
```

### Pattern 2: Async Scanning

```python
# File scan (non-blocking)
backend.scanFile("/path/to/file.exe")

# Network scan with caching
backend.runNetworkScan("192.168.1.0/24", fast=True)

# Connected signals
backend.scanProgress.connect(update_progress_bar)
backend.scanFinished.connect(display_results)
backend.toast.connect(show_notification)
```

### Pattern 3: Worker with Progress

```python
def long_task(worker: CancellableWorker, items: list, **kwargs):
    total = len(items)
    for i, item in enumerate(items):
        if worker.is_cancelled():
            return None
        
        # Do work on item
        process(item)
        
        # Send heartbeat (for watchdog)
        worker.emit_heartbeat()
        
        # Update progress
        worker.emit_progress((i + 1) * 100 // total)
    
    return "completed"

worker = CancellableWorker(
    "process-items",
    long_task,
    items=data_list,
    timeout_ms=120000
)
worker.signals.progress.connect(lambda wid, pct: progress_bar.setValue(pct))
worker.signals.finished.connect(lambda wid, res: on_complete())
worker.signals.error.connect(lambda wid, err: on_error(err))

watchdog = get_watchdog()
watchdog.register_worker(worker.worker_id)
QThreadPool.globalInstance().start(worker)
```

### Pattern 4: Error Handling with Notifications

```python
def on_error(worker_id: str, error_msg: str):
    logger.error(f"Worker failed: {error_msg}")
    backend.toast.emit("error", f"Operation failed: {error_msg}")
    
    # Optional: retry logic
    if "network" in error_msg:
        QTimer.singleShot(2000, lambda: retry_operation())

backend.toast.connect(on_toast)
```

---

## 📊 Signal Emission Reference

### When Signals Are Emitted

| Signal | Emitted By | Conditions | Threading |
|--------|-----------|-----------|-----------|
| `snapshotUpdated` | live_timer | Every 3s (when live is active) | Main thread |
| `eventsLoaded` | loadRecentEvents worker | After loading from DB | Auto-queued |
| `scansLoaded` | loadScanHistory worker | After DB query | Auto-queued |
| `scanFinished` | scan workers | On scan completion/error | Auto-queued |
| `scanProgress` | scan workers | For long operations | Auto-queued |
| `toast` | All operations | On success/error/warning | Both threads |

### Threading Model

```
Main Thread (UI)
  ├─ snapshotUpdated (live timer)
  ├─ GUI event handling
  └─ Signal delivery

Worker Threads
  ├─ eventsLoaded (emitted from thread)
  ├─ scansLoaded (emitted from thread)
  ├─ scanFinished (emitted from thread)
  ├─ scanProgress (emitted from thread)
  └─ toast (emitted from thread)
      → Qt automatically queues to main thread
```

---

## ⚙️ Configuration & Startup

### Basic Startup

```python
from app.core.startup_orchestrator import StartupOrchestrator
from app.ui.backend_bridge import BackendBridge
from app.ui.gpu_service import get_gpu_service

orchestrator = StartupOrchestrator()

# Add tasks
orchestrator.add_immediate("backend", lambda: BackendBridge())
orchestrator.add_background("gpu", 300, lambda: get_gpu_service().start())

# Connect signals
orchestrator.taskFailed.connect(lambda name, err, phase: 
    print(f"[{phase}] {name} failed: {err}"))
orchestrator.startupComplete.connect(lambda ok, err, tot:
    print(f"Startup complete: {ok}/{tot}"))

# Execute
orchestrator.execute()
```

### Shutdown

```python
def on_app_quit():
    backend.cleanup()      # Cancel all workers
    gpu_service.cleanup()  # Stop GPU subprocess
    orchestrator.cleanup() # Stop pending timers
```

---

## 🐛 Debugging & Monitoring

### Check Worker Health

```python
watchdog = get_watchdog()

# Workers currently monitored
workers = watchdog._workers.keys()

# Listen for stalls
watchdog.workerStalled.connect(
    lambda wid, elapsed: logger.warning(f"{wid} stalled ({elapsed:.1f}s)")
)
```

### Monitor Logs

```python
# All logs appear in sentinel.log
# Check for errors
tail -f logs/sentinel.log | grep ERROR

# Watch startup
grep "STARTUP" logs/sentinel.log
```

### Verify Signal Delivery

```python
# Connect to all signals
backend.snapshotUpdated.connect(lambda d: print(f"snapshot: {d['cpu']}"))
backend.eventsLoaded.connect(lambda e: print(f"events: {len(e)}"))
backend.scanFinished.connect(lambda t, r: print(f"scan done: {t}"))
backend.toast.connect(lambda l, m: print(f"[{l}] {m}"))
```

---

## 🎯 Performance Tuning

### Reduce Update Frequency

```python
# Default: 3s interval
# To reduce: 5s interval
backend.live_timer.setInterval(5000)

# To reduce log volume
logging.getLogger().setLevel(logging.WARNING)
```

### Tune Watchdog

```python
from app.core.workers import WorkerWatchdog

# More responsive (check every 2s, stale after 10s)
watchdog = WorkerWatchdog(
    check_interval_ms=2000,
    stale_threshold_sec=10
)
```

### Cache Configuration

```python
from app.core.result_cache import get_scan_cache

cache = get_scan_cache()
cache.ttl = 1800  # 30 minutes
cache.max_size = 1000  # Max cached results
```

---

## 📦 Deployment Notes

### File Sizes
- `startup_orchestrator_refactored.py`: ~420 lines
- `workers_refactored.py`: ~450 lines
- `logging_setup_refactored.py`: ~300 lines
- `backend_bridge_refactored.py`: ~650 lines
- **Total**: ~1820 lines of production-ready code

### Dependencies (No New)
- PySide6 (existing)
- psutil (existing)
- sentry_sdk (optional, already supported)

### Backward Compatibility
✅ All imports remain the same  
✅ Signal names unchanged  
✅ QML bindings work without changes  
✅ Optional: Add new signals for enhanced features  

---

## 🚀 Next Steps

1. **Review** refactored files in `app/*_refactored.py`
2. **Test** with `python main.py` (requires backup of originals)
3. **Compare** performance before/after
4. **Deploy** by replacing original files
5. **Monitor** logs and signal delivery

---

*For complete details, see `BACKEND_REFACTORING_REPORT.md`*
