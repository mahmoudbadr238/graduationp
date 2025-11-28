#!/usr/bin/env python3
"""
GPU Telemetry Worker - Subprocess that safely polls GPU metrics
Runs in separate process, never crashes main UI
Emits newline-delimited JSON to stdout

Enhanced version with detailed metrics like MSI Afterburner:
- GPU utilization, memory utilization
- Core clock, memory clock, shader clock
- Temperature (GPU, hotspot, memory junction)
- Power draw, voltage, TDP percentage
- Fan speed (RPM and percentage)
- Memory bandwidth utilization
- PCIe bandwidth
"""

import contextlib
import json
import sys
import time
import traceback
from typing import Any

# Configure interval from environment or default
INTERVAL = float(sys.argv[1]) / 1000.0 if len(sys.argv) > 1 else 1.0


def emit(obj: dict[str, Any]) -> None:
    """Emit JSON object to stdout (one line)"""
    try:
        sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
        sys.stdout.flush()
    except (OSError, ValueError):
        pass  # Never crash on emit failure - parent may have closed pipe


def init_nvidia() -> bool:
    """Initialize NVIDIA NVML library"""
    try:
        import pynvml

        pynvml.nvmlInit()
        return True
    except (ImportError, RuntimeError, OSError):
        return False


def init_amd_adl() -> bool:
    """Initialize AMD ADL SDK via pyadl"""
    try:
        from pyadl import ADLManager
        ADLManager.getInstance()
        return True
    except (ImportError, RuntimeError, OSError, Exception):
        return False


def init_amd_wmi() -> bool:
    """Initialize AMD monitoring via WMI Performance Counters (fallback)"""
    try:
        import wmi
        wmi.WMI(namespace=r"root\cimv2")
        return True
    except (ImportError, RuntimeError, OSError):
        return False


def init_intel() -> bool:
    """Initialize Intel monitoring (WMI)"""
    try:
        import wmi
        wmi.WMI()
        return True
    except (ImportError, RuntimeError, OSError):
        return False


def collect_nvidia_metrics(nvml_enabled: bool) -> list[dict[str, Any]]:
    """Collect comprehensive NVIDIA GPU metrics safely - MSI Afterburner style"""
    if not nvml_enabled:
        return []

    gpus = []
    try:
        import pynvml

        device_count = pynvml.nvmlDeviceGetCount()

        for i in range(device_count):
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")

                # === UTILIZATION ===
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_util = round(float(util.gpu), 1)
                mem_util = round(float(util.memory), 1)  # Memory controller utilization

                # === MEMORY ===
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                mem_used_mb = mem.used // (1024**2)
                mem_total_mb = mem.total // (1024**2)
                mem_free_mb = mem.free // (1024**2)
                mem_percent = round(mem.used / mem.total * 100, 1) if mem.total > 0 else 0.0

                # === TEMPERATURE ===
                temp_gpu = 0
                temp_hotspot = 0  # GPU hotspot (junction temp)
                temp_memory = 0   # Memory temperature (GDDR6X)
                
                with contextlib.suppress(Exception):
                    temp_gpu = pynvml.nvmlDeviceGetTemperature(
                        handle, pynvml.NVML_TEMPERATURE_GPU
                    )
                
                # Try to get additional temperature sensors
                with contextlib.suppress(Exception):
                    # Some GPUs support hotspot/junction temperature
                    try:
                        sensors = pynvml.nvmlDeviceGetFieldValues(handle, [
                            pynvml.NVML_FI_DEV_MEMORY_TEMP,  # Memory temp
                        ])
                        for sensor in sensors:
                            if sensor.fieldId == pynvml.NVML_FI_DEV_MEMORY_TEMP and sensor.nvmlReturn == 0:
                                temp_memory = sensor.value.siVal
                    except (AttributeError, pynvml.NVMLError):
                        pass

                # === CLOCKS ===
                clock_graphics = 0
                clock_memory = 0
                clock_sm = 0  # Shader/SM clock
                clock_video = 0
                
                with contextlib.suppress(Exception):
                    clock_graphics = pynvml.nvmlDeviceGetClockInfo(
                        handle, pynvml.NVML_CLOCK_GRAPHICS
                    )
                with contextlib.suppress(Exception):
                    clock_memory = pynvml.nvmlDeviceGetClockInfo(
                        handle, pynvml.NVML_CLOCK_MEM
                    )
                with contextlib.suppress(Exception):
                    clock_sm = pynvml.nvmlDeviceGetClockInfo(
                        handle, pynvml.NVML_CLOCK_SM
                    )
                with contextlib.suppress(Exception):
                    clock_video = pynvml.nvmlDeviceGetClockInfo(
                        handle, pynvml.NVML_CLOCK_VIDEO
                    )

                # Max clocks
                max_clock_graphics = 0
                max_clock_memory = 0
                with contextlib.suppress(Exception):
                    max_clock_graphics = pynvml.nvmlDeviceGetMaxClockInfo(
                        handle, pynvml.NVML_CLOCK_GRAPHICS
                    )
                with contextlib.suppress(Exception):
                    max_clock_memory = pynvml.nvmlDeviceGetMaxClockInfo(
                        handle, pynvml.NVML_CLOCK_MEM
                    )

                # === POWER ===
                power = 0.0
                power_limit = 0.0
                power_default = 0.0
                power_min = 0.0
                power_max = 0.0
                
                with contextlib.suppress(pynvml.NVMLError):
                    power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
                    # Sanity check - power shouldn't be > 500W for consumer GPUs
                    if power > 500:
                        power = 0.0

                with contextlib.suppress(pynvml.NVMLError):
                    power_limit = pynvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000.0

                with contextlib.suppress(pynvml.NVMLError):
                    power_default = pynvml.nvmlDeviceGetPowerManagementDefaultLimit(handle) / 1000.0

                with contextlib.suppress(pynvml.NVMLError):
                    constraints = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(handle)
                    power_min = constraints[0] / 1000.0
                    power_max = constraints[1] / 1000.0

                # Use power_default if power_limit is not available
                effective_limit = power_limit if power_limit > 0 else power_default
                # Power percentage (TDP%)
                power_percent = round((power / effective_limit * 100), 1) if effective_limit > 0 else 0.0

                # === FAN ===
                fan_speed = 0
                fan_rpm = 0
                fan_count = 0
                
                with contextlib.suppress(Exception):
                    fan_speed = pynvml.nvmlDeviceGetFanSpeed(handle)
                
                # Try to get RPM for multiple fans
                with contextlib.suppress(Exception):
                    fan_count = pynvml.nvmlDeviceGetNumFans(handle)
                    if fan_count > 0:
                        # Get average RPM across all fans
                        total_rpm = 0
                        for fan_idx in range(fan_count):
                            with contextlib.suppress(Exception):
                                rpm = pynvml.nvmlDeviceGetFanSpeed_v2(handle, fan_idx)
                                total_rpm += rpm
                        fan_rpm = total_rpm // max(1, fan_count) if total_rpm > 0 else 0

                # === PCIe ===
                pcie_gen = 0
                pcie_width = 0
                pcie_tx = 0  # KB/s
                pcie_rx = 0  # KB/s
                
                with contextlib.suppress(Exception):
                    pcie_gen = pynvml.nvmlDeviceGetCurrPcieLinkGeneration(handle)
                with contextlib.suppress(Exception):
                    pcie_width = pynvml.nvmlDeviceGetCurrPcieLinkWidth(handle)
                with contextlib.suppress(Exception):
                    pcie_tx = pynvml.nvmlDeviceGetPcieThroughput(
                        handle, pynvml.NVML_PCIE_UTIL_TX_BYTES
                    )
                with contextlib.suppress(Exception):
                    pcie_rx = pynvml.nvmlDeviceGetPcieThroughput(
                        handle, pynvml.NVML_PCIE_UTIL_RX_BYTES
                    )

                # === DRIVER & CUDA ===
                driver_version = "Unknown"
                cuda_version = "Unknown"
                vbios_version = "Unknown"
                
                with contextlib.suppress(Exception):
                    driver_version = pynvml.nvmlSystemGetDriverVersion()
                    if isinstance(driver_version, bytes):
                        driver_version = driver_version.decode("utf-8")
                        
                with contextlib.suppress(Exception):
                    cuda_version = pynvml.nvmlSystemGetCudaDriverVersion_v2()
                    cuda_major = cuda_version // 1000
                    cuda_minor = (cuda_version % 1000) // 10
                    cuda_version = f"{cuda_major}.{cuda_minor}"
                    
                with contextlib.suppress(Exception):
                    vbios_version = pynvml.nvmlDeviceGetVbiosVersion(handle)
                    if isinstance(vbios_version, bytes):
                        vbios_version = vbios_version.decode("utf-8")

                # === PCI BUS ID ===
                pci_bus = ""
                with contextlib.suppress(Exception):
                    pci = pynvml.nvmlDeviceGetPciInfo(handle)
                    pci_bus = pci.busId.decode("utf-8") if isinstance(pci.busId, bytes) else str(pci.busId)

                # === PERFORMANCE STATE ===
                perf_state = "Unknown"
                with contextlib.suppress(Exception):
                    pstate = pynvml.nvmlDeviceGetPerformanceState(handle)
                    perf_state = f"P{pstate}"

                # === ENCODER/DECODER ===
                encoder_util = 0
                decoder_util = 0
                with contextlib.suppress(Exception):
                    enc = pynvml.nvmlDeviceGetEncoderUtilization(handle)
                    encoder_util = enc[0]
                with contextlib.suppress(Exception):
                    dec = pynvml.nvmlDeviceGetDecoderUtilization(handle)
                    decoder_util = dec[0]

                gpus.append(
                    {
                        "id": i,
                        "name": name,
                        "vendor": "NVIDIA",
                        # Utilization
                        "usage": gpu_util,
                        "memControllerUtil": mem_util,
                        "encoderUtil": encoder_util,
                        "decoderUtil": decoder_util,
                        # Memory
                        "memUsedMB": mem_used_mb,
                        "memTotalMB": mem_total_mb,
                        "memFreeMB": mem_free_mb,
                        "memPercent": mem_percent,
                        # Temperature
                        "tempC": temp_gpu,
                        "tempHotspot": temp_hotspot if temp_hotspot > 0 else temp_gpu,
                        "tempMemory": temp_memory,
                        # Clocks
                        "clockMHz": clock_graphics,
                        "clockMemMHz": clock_memory,
                        "clockSMMHz": clock_sm,
                        "clockVideoMHz": clock_video,
                        "maxClockMHz": max_clock_graphics,
                        "maxClockMemMHz": max_clock_memory,
                        # Power - use effective_limit for display if power_limit is 0
                        "powerW": round(power, 1),
                        "powerLimitW": round(effective_limit, 1),
                        "powerDefaultW": round(power_default, 1),
                        "powerMinW": round(power_min, 1),
                        "powerMaxW": round(power_max, 1),
                        "powerPercent": power_percent,
                        # Fan
                        "fanPercent": fan_speed,
                        "fanRPM": fan_rpm,
                        "fanCount": fan_count,
                        # PCIe
                        "pcieGen": pcie_gen,
                        "pcieWidth": pcie_width,
                        "pcieTxKBs": pcie_tx,
                        "pcieRxKBs": pcie_rx,
                        # Info
                        "driverVersion": driver_version,
                        "cudaVersion": cuda_version,
                        "vbiosVersion": vbios_version,
                        "pciBus": pci_bus,
                        "perfState": perf_state,
                    }
                )
            except (RuntimeError, AttributeError, ValueError):
                continue  # Skip GPUs that fail to query
    except (RuntimeError, AttributeError):
        pass  # NVML not available or failed

    return gpus


def get_luid_to_phys_mapping() -> dict:
    """Build mapping from LUID to physical GPU index using performance counters"""
    mapping = {}
    try:
        import wmi
        perf_wmi = wmi.WMI(namespace=r"root\cimv2")
        
        # Parse physical indices from GPU Engine counters
        for counter in perf_wmi.Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine():
            name = counter.Name or ""
            if "luid_" in name.lower() and "phys_" in name.lower():
                try:
                    # Extract LUID (format varies: luid_0x00000000_0x0000XXXX)
                    luid_part = name.lower().split("luid_")[1].split("_phys_")[0]
                    phys_idx = int(name.lower().split("_phys_")[1].split("_")[0])
                    if luid_part not in mapping:
                        mapping[luid_part] = phys_idx
                except (ValueError, IndexError):
                    pass
    except Exception:
        pass
    return mapping


def collect_amd_adl_metrics() -> list[dict[str, Any]]:
    """Collect AMD GPU metrics using ADL SDK via pyadl library"""
    gpus = []
    try:
        from pyadl import ADLManager
        
        devices = ADLManager.getInstance().getDevices()
        
        for idx, device in enumerate(devices):
            # Get adapter name
            name = device.adapterName
            if isinstance(name, bytes):
                name = name.decode('utf-8', errors='ignore')
            
            # Skip non-AMD devices (pyadl can incorrectly list other GPUs)
            name_upper = name.upper()
            if not ("AMD" in name_upper or "ATI" in name_upper or "RADEON" in name_upper):
                continue
            
            # Collect metrics with error handling for each
            temp_c = 0
            usage = 0
            clock_core = 0
            clock_mem = 0
            fan_percent = 0
            fan_rpm = 0
            voltage = 0
            
            # Temperature
            with contextlib.suppress(Exception):
                temp_c = device.getCurrentTemperature()
            
            # Usage/Load
            with contextlib.suppress(Exception):
                usage = device.getCurrentUsage()
            
            # Core Clock
            with contextlib.suppress(Exception):
                clock_core = device.getCurrentCoreClockFrequency()
            
            # Memory Clock  
            with contextlib.suppress(Exception):
                clock_mem = device.getCurrentMemoryClockFrequency()
            
            # Fan Speed (percentage)
            with contextlib.suppress(Exception):
                fan_percent = device.getCurrentFanSpeed(ADLManager.ADL_DEVICE_FAN_SPEED_TYPE_PERCENTAGE)
            
            # Fan RPM
            with contextlib.suppress(Exception):
                fan_rpm = device.getCurrentFanSpeed(ADLManager.ADL_DEVICE_FAN_SPEED_TYPE_RPM)
            
            # Core Voltage (mV)
            with contextlib.suppress(Exception):
                voltage = device.getCurrentCoreVoltage()
            
            # Max clocks
            max_clock_core = 0
            max_clock_mem = 0
            with contextlib.suppress(Exception):
                max_clock_core = device.adapterSpeed  # This is usually max engine clock
            
            gpus.append({
                "id": idx,
                "name": name,
                "vendor": "AMD",
                "source": "ADL",  # Mark source for debugging
                # Utilization
                "usage": float(usage) if usage else 0.0,
                "memControllerUtil": 0.0,
                "encoderUtil": 0,
                "decoderUtil": 0,
                # Memory - ADL doesn't provide memory usage easily
                "memUsedMB": 0,
                "memTotalMB": 0,
                "memFreeMB": 0,
                "memPercent": 0.0,
                # Temperature
                "tempC": temp_c if temp_c else 0,
                "tempHotspot": 0,
                "tempMemory": 0,
                # Clocks
                "clockMHz": clock_core if clock_core else 0,
                "clockMemMHz": clock_mem if clock_mem else 0,
                "clockSMMHz": 0,
                "clockVideoMHz": 0,
                "maxClockMHz": max_clock_core if max_clock_core else 0,
                "maxClockMemMHz": max_clock_mem if max_clock_mem else 0,
                # Power - ADL doesn't expose power easily without Overdrive
                "powerW": 0.0,
                "powerLimitW": 0.0,
                "powerDefaultW": 0.0,
                "powerMinW": 0.0,
                "powerMaxW": 0.0,
                "powerPercent": 0.0,
                "voltageV": (voltage / 1000.0) if voltage else 0.0,
                # Fan
                "fanPercent": fan_percent if fan_percent else 0,
                "fanRPM": fan_rpm if fan_rpm else 0,
                "fanCount": 1 if (fan_percent or fan_rpm) else 0,
                # PCIe
                "pcieGen": 0,
                "pcieWidth": 0,
                "pcieTxKBs": 0,
                "pcieRxKBs": 0,
                # Info
                "driverVersion": "Unknown",
                "cudaVersion": "N/A",
                "vbiosVersion": "Unknown",
                "pciBus": f"adapter_{device.adapterIndex}",
                "perfState": "Unknown",
                "_adlIndex": device.adapterIndex,
            })
    except Exception:
        pass
    
    return gpus


def collect_amd_wmi_metrics() -> list[dict[str, Any]]:
    """Collect AMD GPU metrics via WMI Performance Counters (fallback when ADL fails)"""
    gpus = []
    try:
        import wmi

        c = wmi.WMI()
        perf_wmi = wmi.WMI(namespace=r"root\cimv2")

        # Get GPU performance data keyed by physical index
        gpu_3d_usage = {}
        gpu_copy_usage = {}
        gpu_video_decode = {}
        gpu_video_encode = {}
        
        try:
            for counter in perf_wmi.Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine():
                name = counter.Name or ""
                if "phys_" not in name.lower():
                    continue
                    
                try:
                    phys_idx = int(name.lower().split("_phys_")[1].split("_")[0])
                    util = float(counter.UtilizationPercentage or 0)
                    
                    name_lower = name.lower()
                    if "_engtype_3d" in name_lower:
                        gpu_3d_usage[phys_idx] = max(gpu_3d_usage.get(phys_idx, 0), util)
                    elif "_engtype_copy" in name_lower:
                        gpu_copy_usage[phys_idx] = max(gpu_copy_usage.get(phys_idx, 0), util)
                    elif "_engtype_videodecode" in name_lower:
                        gpu_video_decode[phys_idx] = max(gpu_video_decode.get(phys_idx, 0), util)
                    elif "_engtype_videoencode" in name_lower:
                        gpu_video_encode[phys_idx] = max(gpu_video_encode.get(phys_idx, 0), util)
                except (ValueError, IndexError, AttributeError):
                    pass
        except Exception:
            pass

        # Get memory usage from Performance Counters
        gpu_mem_dedicated = {}
        gpu_mem_shared = {}
        
        try:
            for counter in perf_wmi.Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory():
                name = counter.Name or ""
                if "phys_" not in name.lower():
                    continue
                try:
                    phys_idx = int(name.lower().split("_phys_")[1].split("_")[0])
                    dedicated = int(counter.DedicatedUsage or 0)
                    shared = int(counter.SharedUsage or 0)
                    gpu_mem_dedicated[phys_idx] = dedicated
                    gpu_mem_shared[phys_idx] = shared
                except (ValueError, IndexError, AttributeError):
                    pass
        except Exception:
            pass

        # Build ordered list of all video controllers
        all_gpus_ordered = []
        for gpu in c.Win32_VideoController():
            name = gpu.Name or ""
            pnp_id = gpu.PNPDeviceID or ""
            all_gpus_ordered.append({
                "name": name,
                "pnp_id": pnp_id,
                "driver": gpu.DriverVersion or "Unknown",
                "adapter_ram": int(gpu.AdapterRAM or 0) // (1024**2) if gpu.AdapterRAM else 0
            })

        # Find AMD GPUs and match to physical indices
        amd_idx = 0
        for phys_idx, gpu_info in enumerate(all_gpus_ordered):
            name = gpu_info["name"].upper()
            if not ("AMD" in name or "ATI" in name or "RADEON" in name):
                continue

            # Get metrics for this physical index
            usage_3d = gpu_3d_usage.get(phys_idx, 0.0)
            usage_copy = gpu_copy_usage.get(phys_idx, 0.0)
            video_decode = gpu_video_decode.get(phys_idx, 0.0)
            video_encode = gpu_video_encode.get(phys_idx, 0.0)
            
            mem_used_bytes = gpu_mem_dedicated.get(phys_idx, 0)
            mem_used_mb = mem_used_bytes // (1024 * 1024)
            
            adapter_ram = gpu_info["adapter_ram"]
            mem_percent = round((mem_used_mb / adapter_ram * 100), 1) if adapter_ram > 0 else 0.0

            gpus.append({
                "id": amd_idx,
                "name": gpu_info["name"],
                "vendor": "AMD",
                "source": "WMI",  # Mark source for debugging
                # Utilization
                "usage": round(usage_3d, 1),
                "memControllerUtil": round(usage_copy, 1),
                "encoderUtil": int(video_encode),
                "decoderUtil": int(video_decode),
                # Memory
                "memUsedMB": mem_used_mb,
                "memTotalMB": adapter_ram,
                "memFreeMB": max(0, adapter_ram - mem_used_mb),
                "memPercent": mem_percent,
                # Temperature - not available via WMI
                "tempC": 0,
                "tempHotspot": 0,
                "tempMemory": 0,
                # Clocks - not available via WMI
                "clockMHz": 0,
                "clockMemMHz": 0,
                "clockSMMHz": 0,
                "clockVideoMHz": 0,
                "maxClockMHz": 0,
                "maxClockMemMHz": 0,
                # Power - not available via WMI
                "powerW": 0.0,
                "powerLimitW": 0.0,
                "powerDefaultW": 0.0,
                "powerMinW": 0.0,
                "powerMaxW": 0.0,
                "powerPercent": 0.0,
                # Fan - not available via WMI
                "fanPercent": 0,
                "fanRPM": 0,
                "fanCount": 0,
                # PCIe
                "pcieGen": 0,
                "pcieWidth": 0,
                "pcieTxKBs": 0,
                "pcieRxKBs": 0,
                # Info
                "driverVersion": gpu_info["driver"],
                "cudaVersion": "N/A",
                "vbiosVersion": "Unknown",
                "pciBus": gpu_info["pnp_id"],
                "perfState": "Unknown",
                "_physIdx": phys_idx,
            })
            amd_idx += 1
    except Exception:
        pass

    return gpus


def collect_amd_metrics(adl_enabled: bool, wmi_enabled: bool) -> list[dict[str, Any]]:
    """
    Collect AMD GPU metrics using best available method.
    Priority: 1) ADL SDK (pyadl) for detailed metrics, 2) WMI for usage/memory
    """
    # Try ADL first for discrete GPUs
    if adl_enabled:
        adl_gpus = collect_amd_adl_metrics()
        if adl_gpus:
            # ADL worked - now merge with WMI data for memory info
            if wmi_enabled:
                wmi_gpus = collect_amd_wmi_metrics()
                # Match by name and merge memory data
                for adl_gpu in adl_gpus:
                    adl_name = adl_gpu["name"].upper()
                    for wmi_gpu in wmi_gpus:
                        wmi_name = wmi_gpu["name"].upper()
                        # Fuzzy match on name
                        if adl_name in wmi_name or wmi_name in adl_name:
                            # ADL has clocks/temp/fan, WMI has memory usage
                            if adl_gpu["memUsedMB"] == 0 and wmi_gpu["memUsedMB"] > 0:
                                adl_gpu["memUsedMB"] = wmi_gpu["memUsedMB"]
                                adl_gpu["memTotalMB"] = wmi_gpu["memTotalMB"]
                                adl_gpu["memFreeMB"] = wmi_gpu["memFreeMB"]
                                adl_gpu["memPercent"] = wmi_gpu["memPercent"]
                            # Use WMI usage if ADL failed
                            if adl_gpu["usage"] == 0 and wmi_gpu["usage"] > 0:
                                adl_gpu["usage"] = wmi_gpu["usage"]
                            # Copy driver version from WMI
                            if adl_gpu["driverVersion"] == "Unknown":
                                adl_gpu["driverVersion"] = wmi_gpu["driverVersion"]
                            break
            return adl_gpus
    
    # Fall back to WMI only
    if wmi_enabled:
        return collect_amd_wmi_metrics()
    
    return []


def collect_intel_metrics(wmi_enabled: bool) -> list[dict[str, Any]]:
    """Collect Intel GPU metrics safely via WMI"""
    if not wmi_enabled:
        return []

    gpus = []
    try:
        import wmi

        c = wmi.WMI()
        perf_wmi = wmi.WMI(namespace=r"root\cimv2")

        # Get GPU performance data keyed by physical index
        gpu_usage = {}
        gpu_3d_usage = {}
        gpu_video_decode = {}
        gpu_video_encode = {}
        
        try:
            for counter in perf_wmi.Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine():
                name = counter.Name or ""
                if "phys_" not in name.lower():
                    continue
                try:
                    phys_idx = int(name.lower().split("_phys_")[1].split("_")[0])
                    util = float(counter.UtilizationPercentage or 0)
                    
                    name_lower = name.lower()
                    if "_engtype_3d" in name_lower:
                        gpu_3d_usage[phys_idx] = max(gpu_3d_usage.get(phys_idx, 0), util)
                    elif "_engtype_videodecode" in name_lower:
                        gpu_video_decode[phys_idx] = max(gpu_video_decode.get(phys_idx, 0), util)
                    elif "_engtype_videoencode" in name_lower:
                        gpu_video_encode[phys_idx] = max(gpu_video_encode.get(phys_idx, 0), util)
                    
                    gpu_usage[phys_idx] = max(gpu_usage.get(phys_idx, 0), util)
                except (ValueError, IndexError, AttributeError):
                    pass
        except Exception:
            pass

        # Get memory usage
        gpu_mem_dedicated = {}
        try:
            for counter in perf_wmi.Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory():
                name = counter.Name or ""
                if "phys_" not in name.lower():
                    continue
                try:
                    phys_idx = int(name.lower().split("_phys_")[1].split("_")[0])
                    dedicated = int(counter.DedicatedUsage or 0)
                    gpu_mem_dedicated[phys_idx] = dedicated
                except (ValueError, IndexError, AttributeError):
                    pass
        except Exception:
            pass

        # Build ordered list of all video controllers
        all_gpus_ordered = []
        for gpu in c.Win32_VideoController():
            name = gpu.Name or ""
            pnp_id = gpu.PNPDeviceID or ""
            all_gpus_ordered.append({
                "name": name,
                "pnp_id": pnp_id,
                "driver": gpu.DriverVersion or "Unknown",
                "adapter_ram": int(gpu.AdapterRAM or 0) // (1024**2) if gpu.AdapterRAM else 0
            })

        intel_idx = 0
        for phys_idx, gpu_info in enumerate(all_gpus_ordered):
            if "INTEL" not in gpu_info["name"].upper():
                continue

            usage_3d = gpu_3d_usage.get(phys_idx, 0.0)
            video_decode = gpu_video_decode.get(phys_idx, 0.0)
            video_encode = gpu_video_encode.get(phys_idx, 0.0)
            
            mem_used_bytes = gpu_mem_dedicated.get(phys_idx, 0)
            mem_used_mb = mem_used_bytes // (1024 * 1024)

            adapter_ram = gpu_info["adapter_ram"]
            mem_percent = round((mem_used_mb / adapter_ram * 100), 1) if adapter_ram > 0 else 0.0

            gpus.append(
                {
                    "id": intel_idx,
                    "name": gpu_info["name"],
                    "vendor": "Intel",
                    # Utilization
                    "usage": round(usage_3d, 1),
                    "memControllerUtil": 0.0,
                    "encoderUtil": int(video_encode),
                    "decoderUtil": int(video_decode),
                    # Memory
                    "memUsedMB": mem_used_mb,
                    "memTotalMB": adapter_ram,
                    "memFreeMB": max(0, adapter_ram - mem_used_mb),
                    "memPercent": mem_percent,
                    # Temperature
                    "tempC": 0,
                    "tempHotspot": 0,
                    "tempMemory": 0,
                    # Clocks
                    "clockMHz": 0,
                    "clockMemMHz": 0,
                    "clockSMMHz": 0,
                    "clockVideoMHz": 0,
                    "maxClockMHz": 0,
                    "maxClockMemMHz": 0,
                    # Power
                    "powerW": 0.0,
                    "powerLimitW": 0.0,
                    "powerDefaultW": 0.0,
                    "powerMinW": 0.0,
                    "powerMaxW": 0.0,
                    "powerPercent": 0.0,
                    # Fan
                    "fanPercent": 0,
                    "fanRPM": 0,
                    "fanCount": 0,
                    # PCIe
                    "pcieGen": 0,
                    "pcieWidth": 0,
                    "pcieTxKBs": 0,
                    "pcieRxKBs": 0,
                    # Info
                    "driverVersion": gpu_info["driver"],
                    "cudaVersion": "N/A",
                    "vbiosVersion": "Unknown",
                    "pciBus": gpu_info["pnp_id"],
                    "perfState": "Unknown",
                    "_physIdx": phys_idx,
                }
            )
            intel_idx += 1
    except Exception:
        pass

    return gpus


def main():
    """Main worker loop"""
    # Emit startup
    emit({"type": "startup", "ts": time.time(), "interval": INTERVAL})

    # Initialize vendors (safe, never crash)
    nvml_enabled = init_nvidia()
    amd_adl_enabled = init_amd_adl()
    amd_wmi_enabled = init_amd_wmi()
    intel_enabled = init_intel()

    emit(
        {
            "type": "init",
            "ts": time.time(),
            "vendors": {
                "nvidia": nvml_enabled,
                "amd_adl": amd_adl_enabled,
                "amd_wmi": amd_wmi_enabled,
                "intel": intel_enabled,
            },
        }
    )

    # Main polling loop
    while True:
        start = time.time()

        try:
            # Collect from all vendors
            all_gpus = []
            all_gpus.extend(collect_nvidia_metrics(nvml_enabled))
            all_gpus.extend(collect_amd_metrics(amd_adl_enabled, amd_wmi_enabled))
            all_gpus.extend(collect_intel_metrics(intel_enabled))

            # Re-assign IDs
            for idx, gpu in enumerate(all_gpus):
                gpu["id"] = idx

            # Emit metrics
            emit(
                {
                    "type": "metrics",
                    "ts": time.time(),
                    "count": len(all_gpus),
                    "gpus": all_gpus,
                }
            )
        except (RuntimeError, ValueError, OSError) as e:
            emit(
                {
                    "type": "error",
                    "msg": str(e),
                    "trace": traceback.format_exc()[:500],
                    "ts": time.time(),
                }
            )

        # Always emit heartbeat
        emit({"type": "heartbeat", "ts": time.time()})

        # Sleep for remaining interval
        elapsed = time.time() - start
        sleep_time = max(0.0, INTERVAL - elapsed)
        time.sleep(sleep_time)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        emit({"type": "shutdown", "ts": time.time()})
        sys.exit(0)
    except (RuntimeError, ValueError, OSError) as e:
        emit({"type": "fatal", "msg": str(e), "ts": time.time()})
        sys.exit(1)
