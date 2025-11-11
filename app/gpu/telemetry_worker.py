#!/usr/bin/env python3
"""
GPU Telemetry Worker - Subprocess that safely polls GPU metrics
Runs in separate process, never crashes main UI
Emits newline-delimited JSON to stdout
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


def init_amd() -> bool:
    """Initialize AMD monitoring (WMI Performance Counters)"""
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
    """Collect NVIDIA GPU metrics safely"""
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

                # Utilization
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)

                # Memory
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)

                # Temperature (safe)
                temp = 0
                with contextlib.suppress(Exception):
                    temp = pynvml.nvmlDeviceGetTemperature(
                        handle, pynvml.NVML_TEMPERATURE_GPU
                    )

                # Clocks (safe)
                clock_gfx = 0
                with contextlib.suppress(Exception):
                    clock_gfx = pynvml.nvmlDeviceGetClockInfo(
                        handle, pynvml.NVML_CLOCK_GRAPHICS
                    )

                # Power (safe)
                power = 0.0
                power_limit = 0.0
                try:
                    power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
                except Exception:  # noqa: BLE001, S110 - GPU-specific error, expected failure
                    pass  # Power usage not supported on this GPU

                try:
                    power_limit = (
                        pynvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000.0
                    )
                except Exception:  # noqa: BLE001, S110 - GPU-specific error, expected failure
                    pass  # Power limit not supported on this GPU

                # Fan (safe)
                fan_speed = 0
                with contextlib.suppress(Exception):
                    fan_speed = pynvml.nvmlDeviceGetFanSpeed(handle)

                gpus.append(
                    {
                        "id": i,
                        "name": name,
                        "vendor": "NVIDIA",
                        "usage": round(float(util.gpu), 1),
                        "memUsedMB": mem.used // (1024**2),
                        "memTotalMB": mem.total // (1024**2),
                        "memPercent": round(mem.used / mem.total * 100, 1)
                        if mem.total > 0
                        else 0.0,
                        "tempC": temp,
                        "powerW": round(power, 1),
                        "powerLimitW": round(power_limit, 1),
                        "clockMHz": clock_gfx,
                        "fanPercent": fan_speed,
                    }
                )
            except (RuntimeError, AttributeError, ValueError):
                continue  # Skip GPUs that fail to query
    except (RuntimeError, AttributeError):
        pass  # NVML not available or failed

    return gpus


def collect_amd_metrics(wmi_enabled: bool) -> list[dict[str, Any]]:
    """Collect AMD GPU metrics safely via WMI Performance Counters"""
    if not wmi_enabled:
        return []

    gpus = []
    try:
        import wmi

        c = wmi.WMI()
        perf_wmi = wmi.WMI(namespace=r"root\cimv2")

        # Get usage from Performance Counters
        gpu_usage = {}
        try:
            for (
                counter
            ) in perf_wmi.Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine():
                name = counter.Name
                if "phys_" in name:
                    try:
                        phys_idx = int(name.split("_phys_")[1].split("_")[0])
                        util = float(counter.UtilizationPercentage or 0)
                        gpu_usage[phys_idx] = max(gpu_usage.get(phys_idx, 0), util)
                    except (ValueError, IndexError, AttributeError):
                        pass  # Skip malformed counter names
        except (RuntimeError, AttributeError):
            pass  # WMI query failed

        # Build PNP to physical index mapping
        pnp_to_phys = {}
        for phys_idx, gpu in enumerate(c.Win32_VideoController()):
            pnp_id = gpu.PNPDeviceID or ""
            if pnp_id:
                pnp_to_phys[pnp_id] = phys_idx

        # Get AMD GPUs
        for gpu in c.Win32_VideoController():
            if "AMD" in gpu.Name.upper() or "ATI" in gpu.Name.upper():
                pass
            else:
                continue

            # Map to physical index
            usage = 0.0
            pnp_id = gpu.PNPDeviceID or ""
            if pnp_id in pnp_to_phys:
                phys_idx = pnp_to_phys[pnp_id]
                usage = gpu_usage.get(phys_idx, 0.0)

            adapter_ram = 0
            if gpu.AdapterRAM:
                adapter_ram = int(gpu.AdapterRAM) // (1024**2)

            gpus.append(
                {
                    "id": len(gpus),
                    "name": gpu.Name or "AMD GPU",
                    "vendor": "AMD",
                    "usage": round(usage, 1),
                    "memUsedMB": 0,  # Not available via WMI
                    "memTotalMB": adapter_ram,
                    "memPercent": 0.0,
                    "tempC": 0,  # Requires ADL SDK
                    "powerW": 0.0,
                    "powerLimitW": 0.0,
                    "clockMHz": 0,
                    "fanPercent": 0,
                }
            )
    except (RuntimeError, AttributeError, ValueError):
        pass  # WMI query failed or invalid AMD data

    return gpus


def collect_intel_metrics(wmi_enabled: bool) -> list[dict[str, Any]]:
    """Collect Intel GPU metrics safely via WMI"""
    if not wmi_enabled:
        return []

    gpus = []
    try:
        import wmi

        c = wmi.WMI()

        for gpu in c.Win32_VideoController():
            if "INTEL" not in gpu.Name.upper():
                continue

            adapter_ram = 0
            if gpu.AdapterRAM:
                adapter_ram = int(gpu.AdapterRAM) // (1024**2)

            gpus.append(
                {
                    "id": len(gpus),
                    "name": gpu.Name or "Intel GPU",
                    "vendor": "Intel",
                    "usage": 0.0,  # Not easily available
                    "memUsedMB": 0,
                    "memTotalMB": adapter_ram,
                    "memPercent": 0.0,
                    "tempC": 0,
                    "powerW": 0.0,
                    "powerLimitW": 0.0,
                    "clockMHz": 0,
                    "fanPercent": 0,
                }
            )
    except (RuntimeError, AttributeError, ValueError):
        pass  # WMI query failed or invalid Intel data

    return gpus


def main():
    """Main worker loop"""
    # Emit startup
    emit({"type": "startup", "ts": time.time(), "interval": INTERVAL})

    # Initialize vendors (safe, never crash)
    nvml_enabled = init_nvidia()
    amd_enabled = init_amd()
    intel_enabled = init_intel()

    emit(
        {
            "type": "init",
            "ts": time.time(),
            "vendors": {
                "nvidia": nvml_enabled,
                "amd": amd_enabled,
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
            all_gpus.extend(collect_amd_metrics(amd_enabled))
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
