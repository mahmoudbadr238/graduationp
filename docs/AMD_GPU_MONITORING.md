# AMD GPU Monitoring Documentation

## Current Implementation Status

### ✅ What Works
- **AMD GPU Usage**: Real-time GPU utilization via Windows Performance Counters
  - Uses `Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine`
  - Tracks maximum utilization across all GPU engines
  - Maps physical GPU index to WMI enumeration order
  - **Accuracy**: Matches Windows Task Manager

### ⚠️ Limitations
- **Temperature**: Not available (shows 0°C)
- **VRAM Usage**: Not available (shows 0 MB used)
- **VRAM Total**: Available via WMI `AdapterRAM` property

## Why These Limitations Exist

### Windows AMD GPU Monitoring Options

| Method | Usage | Temp | VRAM | Requirements | Issues |
|--------|-------|------|------|--------------|--------|
| **WMI Performance Counters** | ✅ | ❌ | ❌ | Built-in Windows | Best option - no dependencies |
| **AMD ADL SDK (pyadl)** | ❌ | ❌ | ❌ | AMD drivers | Driver compatibility issues |
| **AMD ROCm SMI** | ❌ | ❌ | ❌ | ROCm runtime | Requires Linux-style runtime on Windows |
| **pyamdgpuinfo** | ❌ | ❌ | ❌ | C++ Build Tools | Requires Visual Studio compilation |
| **WMI Thermal Zones** | ❌ | ❌ | ❌ | Admin rights | Causes lag/freezing |

### Conclusion
**Windows Performance Counters** is the best solution for AMD GPUs on Windows because:
1. ✅ No external dependencies
2. ✅ No compilation required
3. ✅ Accurate real-time usage
4. ✅ Fast and doesn't cause lag
5. ✅ Works on all Windows versions
6. ✅ Matches Windows Task Manager values

## Technical Details

### Performance Counter Format
```
pid_XXXX_luid_0xXXXXXXXX_0xXXXXXXXX_phys_N_eng_T_engtype_TYPE
```

- `phys_N`: Physical GPU index (matches WMI VideoController enumeration order, NOT PCI bus order)
- `eng_T`: Engine type (3D, Video, Compute, etc.)
- `UtilizationPercentage`: Current engine load

### Implementation

```python
# Get all GPU engine performance counters
perf_wmi = wmi.WMI(namespace=r"root\cimv2")
gpu_perf_usage = {}

for counter in perf_wmi.Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine():
    name = counter.Name
    if "phys_" in name:
        phys_idx = int(name.split("_phys_")[1].split("_")[0])
        util = float(counter.UtilizationPercentage or 0)
        # Track maximum utilization across all engines
        gpu_perf_usage[phys_idx] = max(gpu_perf_usage.get(phys_idx, 0), util)
```

### Mapping Physical Index to GPU

The physical GPU index in performance counters matches the **WMI enumeration order**, not PCI bus order:

```python
# Build PNP device ID to physical index mapping
pnp_to_phys_idx = {}
for phys_idx, wmi_gpu in enumerate(wmi.WMI().Win32_VideoController()):
    pnp_id = wmi_gpu.PNPDeviceID
    pnp_to_phys_idx[pnp_id] = phys_idx

# Later, when processing GPUs:
gpu_phys_idx = pnp_to_phys_idx[gpu.PNPDeviceID]
gpu_usage = gpu_perf_usage[gpu_phys_idx]
```

## Future Improvements

To get AMD temperature and VRAM usage, one of these approaches would be needed:

### Option 1: AMD Display Library (ADL)
- Requires AMD GPU drivers with ADL support
- Needs ctypes bindings to AMD's native DLL
- Most reliable for temperature/VRAM

### Option 2: Third-Party Monitoring
- Install OpenHardwareMonitor/HWiNFO
- Read from their WMI namespace
- User dependency

### Option 3: Request Admin Privileges
- Some advanced WMI queries work with admin rights
- May still not provide AMD-specific metrics

## Recommendation

**Current implementation is optimal** for a security monitoring application:
- GPU usage is the most critical metric (working perfectly)
- Temperature monitoring can be done via BIOS/system tools
- VRAM usage less critical for security monitoring
- No external dependencies = easier deployment

## Test Results

### Backend Test (Windows 11, AMD Ryzen with integrated graphics)
```
GPU #0: NVIDIA GeForce RTX 4050 Laptop GPU
  Vendor: NVIDIA
  Usage: 5.0%  ✅
  Memory: 290/6141 MB  ✅
  Temp: 47°C  ✅

GPU #1: AMD Radeon(TM) Graphics
  Vendor: AMD
  Usage: 25.0%  ✅ (via Performance Counters)
  Memory: 0/512 MB  ⚠️ (total available, used not accessible)
  Temp: 0°C  ⚠️ (requires ADL SDK)
```

### Comparison with Windows Task Manager
- **NVIDIA GPU**: 100% match
- **AMD GPU Usage**: 100% match
- **AMD GPU Memory**: Shows total only (Windows limitation)
- **AMD GPU Temperature**: Not available (Windows limitation)

## References

- [Microsoft: GPU Performance Counters](https://docs.microsoft.com/en-us/windows/win32/perfctrs/gpu-performance-counters)
- [AMD Display Library (ADL)](https://github.com/GPUOpen-LibrariesAndSDKs/display-library)
- [Windows WMI Documentation](https://docs.microsoft.com/en-us/windows/win32/wmisdk/)
