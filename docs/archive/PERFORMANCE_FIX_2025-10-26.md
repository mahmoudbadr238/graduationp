# Performance Fixes - October 26, 2025

## Issues Resolved

### 1. Severe UI Lag (20s freezes)
**Root Cause:** WMI GPU queries in `_get_gpu_info()` took 14-20 seconds per call, blocking the main thread.

**Solution:**
- Removed GPU detection from `snapshot()` method
- Changed to stub GPU data: `{"available": False, "gpus": [], "count": 0}`
- **GPU metrics now exclusively via GPUService** (QProcess-based, async)
- **Performance improvement:** 20,000ms → 140ms per snapshot (142x faster)

**Files Changed:**
- `app/infra/system_monitor_psutil.py`: Disabled GPU in snapshot()
- `app/ui/backend_bridge.py`: Adjusted polling interval to 3 seconds

### 2. Only C: Drive Visible
**Root Cause:** OverviewPageFixed.qml only displayed first disk from array (`disks[0]`)

**Solution:**
- Updated Disk tile to calculate **average usage across all drives**
- Shows total capacity: "450 GB / 1407 GB (2 drives)"
- HardwarePage Repeater continues to show individual drive cards

**Files Changed:**
- `qml/pages/snapshot/OverviewPageFixed.qml`: Added aggregate calculation for all disks

### 3. Toast Warning: "Could not set initial property duration"
**Root Cause:** Backend emits `toast(level, message)` but ToastManager.show expects `(message, duration, type)`

**Solution:**
- Fixed argument order in `qml/main.qml` onToast handler
- Now calls: `globalToast.show(message, 3000, level)`

**Files Changed:**
- `qml/main.qml`: Fixed toast parameter mapping

## Performance Metrics

### Before
- Snapshot call: **20,000ms** (20 seconds)
- UI updates: Blocked, severe lag
- Disks shown: 1 (C: only)

### After
- First snapshot: **6,300ms** (initial WMI connection)
- Subsequent snapshots: **140ms** (142x faster)
- UI updates: Smooth at 3-second intervals
- Disks shown: All drives (averaged)

## Architecture Changes

### GPU Monitoring Strategy
- **Backend snapshot:** No GPU data (stub only)
- **GPUService:** Handles all GPU metrics via QProcess worker
- **GPUMonitoring page:** Uses GPUService directly
- **Overview/Hardware:** Show GPU via separate GPUService binding

### Disk Display Strategy
- **Overview tab:** Average usage across all drives
- **Hardware tab:** Individual cards per drive (via Repeater)

## Testing

Run performance validation:
```powershell
python test_fast_snapshot.py
```

Expected output:
```
Iteration 1: ~6000ms | Disks: 2
Iteration 2: ~140ms | Disks: 2
Iteration 3: ~140ms | Disks: 2
```

## Notes

- GPU data still cached for 10s in `_get_gpu_info_cached()` if needed by other components
- Backend polling interval: 3 seconds (balanced for smooth UI without lag)
- GPUService runs independently with its own update interval (configurable)
