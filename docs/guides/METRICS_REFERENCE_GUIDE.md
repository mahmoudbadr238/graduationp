# System Snapshot Page - Metrics & Data Reference

## Real-Time Metrics Displayed

### Quick Stats (Top Row)
| Metric | Source | Update Interval | Unit | Example |
|--------|--------|-----------------|------|---------|
| CPU Usage | `SnapshotService.cpuUsage` | 2 sec | % | 56% |
| Memory Usage | `SnapshotService.memoryUsage` | 2 sec | % | 64% |
| System Uptime | `SnapshotService.systemUptime` | 2 sec | Format | 5d 4h 23m |
| CPU Health Badge | Auto-calculated | 2 sec | Color | Green/Yellow/Red |
| Memory Capacity | `SnapshotService.memoryUsed` | 2 sec | GB | 8.2 GB |

### Historical Charting
| Chart | Color | Data Points | Time Window | Update |
|-------|-------|------------|-------------|--------|
| CPU Usage | Purple (#7C3AED) | 60 samples | 2 minutes | Every 2 sec |
| Memory Usage | Orange (#F59E0B) | 60 samples | 2 minutes | Every 2 sec |
| Grid Overlay | ThemeManager.border() | 5 horizontal lines | Auto | Every 2 sec |
| Time Labels | 6 intervals | Dynamic | Last 2 min | Every 2 sec |

### CPU Metrics - Overall View
| Card | Property | Source | Unit | Example |
|------|----------|--------|------|---------|
| Physical Cores | `cpuCount` | cpuinfo | # | 8 |
| Logical Threads | `cpuCountLogical` | cpuinfo | # | 16 |
| Clock Speed | `cpuFrequency` | cpuinfo | GHz | 3.2 GHz |
| Model Name | `cpuName` | Windows Registry | String | Intel Core i7-12700KF |

### CPU Metrics - Per-Core View
| Field | Data | Range | Color Coding |
|-------|------|-------|--------------|
| Core # | 0-127 | Per system | Numeric |
| Usage % | Per-core usage | 0-100% | Green→Yellow→Red |
| Health Bar | Visual bar | Proportional | Auto-colored |

**Color Scale**:
- Green: 0-25% (idle)
- Blue: 26-50% (normal)
- Yellow: 51-75% (warning)
- Red: 76-100% (critical)

### Memory Details
| Card | Property | Source | Unit | Format | Example |
|------|----------|--------|------|--------|---------|
| Total | `memoryTotal` | psutil | Bytes | GB | 16 GB |
| Used | `memoryUsed` | psutil | Bytes | GB | 10.2 GB |
| Available | `memoryAvailable` | psutil | Bytes | GB | 5.8 GB |
| Usage % | Calculated | memoryUsed/Total | % | Percentage | 64.1% |

### Storage Details
| Column | Property | Source | Format | Example |
|--------|----------|--------|--------|---------|
| Drive Letter | Device | psutil.disk_partitions | String | C:, D:, E: |
| Used Space | Calculated | total - free | GB | 230 GB |
| Total Space | Reported | disk_usage | GB | 931 GB |
| Usage % | Calculated | used/total | Percentage + Bar | 24.7% ████░░░░ |
| Color Code | Status | Usage % | Color | Red/Yellow/Green |

---

## Backend Data Model

### Signal/Slot Connections (QML Bridge)

```
SnapshotService (Backend)
├─ cpuUsageChanged → QML update
├─ memoryUsageChanged → QML update
├─ diskUsageChanged → QML update
├─ networkStatsChanged → QML update
├─ cpuPerCoreChanged → QML update
├─ cpuNameChanged → QML update
├─ cpuCountChanged → QML update
├─ cpuCountLogicalChanged → QML update
├─ cpuFrequencyChanged → QML update
├─ memoryAvailableChanged → QML update
└─ systemUptimeChanged → QML update
```

### Update Mechanisms

**Automatic (Every 2 Seconds)**:
```python
# In system_snapshot_service.py
Timer interval: 2000ms
Updates:
- cpuUsage
- memoryUsage
- memoryAvailable
- diskUsage (all drives)
- networkStats (if enabled)
- cpuPerCore (per-core percentages)
- systemUptime (uptime recalculation)
```

**On Demand**:
```qml
// In SystemSnapshot.qml
Properties accessed: When QML requests them
Examples:
- SnapshotService.cpuName (immutable, cached)
- SnapshotService.cpuCount (immutable, cached)
- SnapshotService.cpuFrequency (immutable, cached)
```

---

## Formatting & Display

### Time Format Conversions

**Uptime Display**:
```javascript
// systemUptime in seconds → formatted string
function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    
    if (days > 0) return `${days}d ${hours}h ${minutes}m`
    if (hours > 0) return `${hours}h ${minutes}m`
    return `${minutes}m ${seconds % 60}s`
}
// Example: 459780 seconds → "5d 4h 43m"
```

**Chart Time Labels**:
```javascript
// Update every 2 seconds
const now = new Date()
const timeStr = now.getHours().toString().padStart(2, '0') + ':' +
                now.getMinutes().toString().padStart(2, '0')
// Example: "14:23", "14:25", "14:27"
```

### Memory Formatting

**Bytes to GB Conversion**:
```javascript
// Standard conversion: bytes ÷ 1024³
const gb = (bytes / 1024 / 1024 / 1024).toFixed(1)
// Example: 10737418240 bytes → "10.0 GB"
```

**Memory Cards Display**:
```
Total: 16 GB (from memoryTotal)
Used: 10.2 GB (from memoryUsed)
Available: 5.8 GB (from memoryAvailable)
Usage: 64.1% (from memoryUsed / memoryTotal * 100)
```

### Storage Progress Bars

**Percentage Calculation**:
```javascript
const percentUsed = (used / total) * 100
```

**Color Mapping**:
```
0-30%:   Green (#10b981)   - Plenty of space
31-70%:  Yellow (#f59e0b)  - Monitor closely
71-100%: Red (#ef4444)     - Urgent cleanup
```

**Example Display**:
```
C: [████████░░░░░░░░░░░░░░░░░░░░] 230 GB / 931 GB (24.7%)
D: [██░░░░░░░░░░░░░░░░░░░░░░░░░░░]  15 GB / 2000 GB (0.75%)
E: [████████████░░░░░░░░░░░░░░░░░] 750 GB / 1000 GB (75%)
```

---

## Canvas Chart Implementation

### CPU Chart Rendering

```javascript
onPaint: {
    // 1. Clear canvas
    ctx.fillStyle = ThemeManager.background()
    ctx.fillRect(0, 0, width, height)
    
    // 2. Draw grid lines (5 horizontal at 25% intervals)
    ctx.strokeStyle = ThemeManager.border()
    ctx.lineWidth = 0.5
    for (let i = 0; i <= 4; i++) {
        const y = (height / 4) * i
        ctx.beginPath()
        ctx.moveTo(0, y)
        ctx.lineTo(width, y)
        ctx.stroke()
        
        // Label: "100%", "75%", "50%", "25%", "0%"
        ctx.fillStyle = ThemeManager.muted()
        ctx.font = "11px sans-serif"
        ctx.fillText((100 - i * 25) + "%", 5, y - 5)
    }
    
    // 3. Draw data line
    ctx.strokeStyle = "#7C3AED"  // Purple
    ctx.lineWidth = 3
    ctx.beginPath()
    
    const padding = 40
    const chartWidth = width - padding
    const chartHeight = height - padding
    const step = chartWidth / (cpuHistory.length - 1 || 1)
    
    for (let i = 0; i < cpuHistory.length; i++) {
        const x = padding + i * step
        const y = height - 30 - (cpuHistory[i] / 100) * chartHeight
        
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
    }
    ctx.stroke()
    
    // 4. Draw time labels
    ctx.fillStyle = ThemeManager.muted()
    ctx.font = "10px sans-serif"
    const interval = Math.max(1, Math.floor(timeLabels.length / 6))
    for (let i = 0; i < timeLabels.length; i += interval) {
        const x = padding + i * step
        ctx.fillText(timeLabels[i], x - 15, height - 5)
    }
}
```

### Memory Chart Rendering
Same as CPU chart, but:
- Color: Orange (#F59E0B)
- Data: `memoryHistory[]` (same scale: 0-100%)
- Labels: "Memory Usage Over Time"

---

## Performance Metrics

### Update Frequency
```
Component              Update Interval    Data Points    Memory
─────────────────────────────────────────────────────────────────
Quick Stats            2 seconds          4 values       ~1 KB
CPU Chart              2 seconds          60 samples     ~2 KB
Memory Chart           2 seconds          60 samples     ~2 KB
Per-Core CPU           2 seconds          128 cores      ~4 KB
Memory Details         2 seconds          4 values       ~1 KB
Storage Details        On load            10 drives      ~2 KB
─────────────────────────────────────────────────────────────────
Total                                                    ~12 KB
```

### Rendering Performance
```
Component              Render Time        Refresh Rate   GPU Load
─────────────────────────────────────────────────────────────────
Canvas Chart           <5ms               60 FPS         <2%
Theme Update           <1ms               Instant        <1%
Layout Update          <2ms               Smooth         <1%
Data Binding           <1ms               Reactive       <1%
─────────────────────────────────────────────────────────────────
Total                  <10ms              Smooth         <5%
```

---

## Troubleshooting Reference

### Metric Display Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| "N/A" displayed | SnapshotService not initialized | Wait 2-3 seconds |
| NaN on frequency | cpuFrequency wrong type | Verify float type in backend |
| Uptime shows 0 | systemUptime calculation error | Check boot time detection |
| Charts empty | No historical data yet | Wait for first 2-second update |
| Colors wrong | ThemeManager not connected | Check theme signal connections |

### Common Values

**Typical Healthy Values** (Windows 10/11):
```
CPU Usage:          10-30% (at rest)
Memory Usage:       40-60% (typical)
Available Memory:   >2 GB (minimum comfortable)
Storage:           <80% used (safe)
Uptime:            Varies (displayed in d/h/m)
Per-Core Usage:    Varies by core
```

**Warning Thresholds**:
```
CPU Usage:         >80% sustained = investigate
Memory Usage:      >85% sustained = add RAM
Storage:          >90% full = cleanup
```

---

## Data Flow Diagram

```
Physical System (Windows)
         │
         ▼
    psutil library
    ├─ CPU metrics (cores, usage, freq)
    ├─ Memory metrics (total, used, available)
    ├─ Disk metrics (partitions, usage)
    └─ Network stats (if enabled)
         │
         ▼
Backend: system_snapshot_service.py
├─ _update_metrics() [Every 2 sec]
│  ├─ Collect CPU/Memory/Disk data
│  ├─ Store in cpuHistory[60]
│  ├─ Store in memoryHistory[60]
│  └─ Emit signals (cpuUsageChanged, etc.)
│
├─ Properties (QML-exposed)
│  ├─ cpuUsage, memoryUsage
│  ├─ cpuName, cpuCount, cpuFrequency
│  ├─ cpuPerCore[]
│  └─ systemUptime, memoryAvailable
│
└─ Signals (Connected to QML)
   ├─ Automatic connections registered
   └─ QML slots triggered on emit
         │
         ▼
QML: SystemSnapshot.qml
├─ Properties
│  ├─ cpuHistory[60] - local copy
│  ├─ memoryHistory[60] - local copy
│  ├─ timeLabels[60] - time markers
│  └─ historyIndex - update trigger
│
├─ Timers
│  └─ 2-second update timer
│     ├─ Append new values
│     ├─ Shift if >60 points
│     └─ Trigger chart redraw
│
├─ Components
│  ├─ Quick Stats (displays current values)
│  ├─ Charts (Canvas rendering historical data)
│  ├─ CPU Metrics (Overall or Per-Core)
│  ├─ Memory Details (grid display)
│  └─ Storage Details (scrollable list)
│
└─ Theme System
   ├─ ThemeManager singleton
   ├─ Reactive color updates
   └─ Automatic chart redraw
         │
         ▼
Visual Display (GPU)
├─ Chart lines rendered
├─ Cards displayed
├─ Text rendered
└─ Real-time animation
```

---

## Integration Checklist

When adding new metrics:

- [ ] Add property to `system_snapshot_service.py`
- [ ] Create QML-exposed property with `@Property(type=...)`
- [ ] Create corresponding signal `*Changed`
- [ ] Update `_update_metrics()` method
- [ ] Add QML binding in `SystemSnapshot.qml`
- [ ] Create display component (Card, Text, etc.)
- [ ] Test light/dark mode compatibility
- [ ] Verify no performance degradation
- [ ] Update this reference document
- [ ] Add unit tests for new metric

---

**Reference Guide Version**: 1.0  
**Last Updated**: 2025-11-25  
**Compatibility**: Sentinel v1.0.0+
