#!/usr/bin/env python3
"""
GPU Telemetry Worker — Linux version.

Replaces backend/engines/gpu/telemetry_worker.py on Linux.
Only supports NVIDIA (pynvml) and AMD (pyadl) — no WMI, no WMIC fallback.
Same JSON output protocol so gpu_service.py can consume it unchanged.
"""

import contextlib
import json
import logging
import os
import platform
import re
import subprocess
import sys
import time
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

from backend.platform.linux.amd_sysfs_provider import collect_amd_sysfs
from backend.platform.linux.gpu_normalization import normalise_gpu, parse_numeric

INTERVAL = float(sys.argv[1]) / 1000.0 if len(sys.argv) > 1 else 1.0

# On WSL, Windows .exe files are reachable via the interop path.
# Detect once at import time so every collector can branch on _IS_WSL.
def _detect_wsl() -> bool:
    if platform.system() != "Linux":
        return False
    try:
        with open("/proc/version") as _f:
            return "microsoft" in _f.read().lower()
    except OSError:
        return False

_IS_WSL    = _detect_wsl()
_NVIDIA_SMI  = "nvidia-smi.exe"  if _IS_WSL else "nvidia-smi"
_AMD_ROCM_SMI = "rocm-smi.exe"   if _IS_WSL else "rocm-smi"

T = TypeVar("T")


def run_with_timeout(func: Callable[[], T], timeout: float, default: T) -> T:
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            return future.result(timeout=timeout)
    except (FuturesTimeoutError, Exception):
        return default


def emit(obj: dict[str, Any]) -> None:
    try:
        sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
        sys.stdout.flush()
    except (OSError, ValueError):
        pass


# ── NVIDIA (pynvml) ─────────────────────────────────────────────────────

def init_nvidia() -> bool:
    try:
        import pynvml
        pynvml.nvmlInit()
        return True
    except (ImportError, RuntimeError, OSError):
        return False


def collect_nvidia_metrics(nvml_enabled: bool) -> list[dict[str, Any]]:
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

                gpu: dict[str, Any] = {
                    "id": i,
                    "name": name,
                    "vendor": "NVIDIA",
                    "provider": "nvml",
                }

                # Utilization
                with contextlib.suppress(Exception):
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    gpu["gpu_util"] = util.gpu
                    gpu["mem_util"] = util.memory

                # Temperature
                with contextlib.suppress(Exception):
                    gpu["temp_c"] = pynvml.nvmlDeviceGetTemperature(
                        handle, pynvml.NVML_TEMPERATURE_GPU
                    )

                # Memory
                with contextlib.suppress(Exception):
                    mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    gpu["mem_total_mb"] = round(mem.total / (1024 * 1024))
                    gpu["mem_used_mb"] = round(mem.used / (1024 * 1024))
                    gpu["mem_free_mb"] = round(mem.free / (1024 * 1024))

                # Clocks
                with contextlib.suppress(Exception):
                    gpu["clock_core_mhz"] = pynvml.nvmlDeviceGetClockInfo(
                        handle, pynvml.NVML_CLOCK_GRAPHICS
                    )
                with contextlib.suppress(Exception):
                    gpu["clock_mem_mhz"] = pynvml.nvmlDeviceGetClockInfo(
                        handle, pynvml.NVML_CLOCK_MEM
                    )

                # Power
                with contextlib.suppress(Exception):
                    gpu["power_draw_w"] = round(
                        pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0, 1
                    )
                with contextlib.suppress(Exception):
                    gpu["power_limit_w"] = round(
                        pynvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000.0, 1
                    )

                # Fan
                with contextlib.suppress(Exception):
                    gpu["fan_speed_pct"] = pynvml.nvmlDeviceGetFanSpeed(handle)

                # Driver
                with contextlib.suppress(Exception):
                    gpu["driver_version"] = pynvml.nvmlSystemGetDriverVersion()
                    if isinstance(gpu["driver_version"], bytes):
                        gpu["driver_version"] = gpu["driver_version"].decode()

                gpus.append(gpu)
            except Exception:
                pass
    except Exception:
        pass
    return gpus


def collect_nvidia_smi_fallback() -> list[dict[str, Any]]:
    """Fallback: parse nvidia-smi CSV when pynvml is unavailable."""
    gpus = []
    try:
        result = subprocess.run(
            [
                _NVIDIA_SMI,
                "--query-gpu=index,name,driver_version,"
                "utilization.gpu,temperature.gpu,power.draw,"
                "memory.used,memory.total,memory.free,"
                "clocks.current.graphics,clocks.current.memory,"
                "fan.speed,pcie.link.gen.current,pcie.link.width.current",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []

        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 8:
                continue

            idx = int(parse_numeric(parts[0]) or 0)
            name = parts[1] if len(parts) > 1 else "NVIDIA GPU"
            driver = parts[2] if len(parts) > 2 else "Unknown"
            usage = parse_numeric(parts[3]) if len(parts) > 3 else None
            temp = parse_numeric(parts[4]) if len(parts) > 4 else None
            power = parse_numeric(parts[5]) if len(parts) > 5 else None
            mem_used = parse_numeric(parts[6]) if len(parts) > 6 else None
            mem_total = parse_numeric(parts[7]) if len(parts) > 7 else None
            mem_free = parse_numeric(parts[8]) if len(parts) > 8 else None
            clock_core = parse_numeric(parts[9]) if len(parts) > 9 else None
            clock_mem = parse_numeric(parts[10]) if len(parts) > 10 else None
            fan_pct = parse_numeric(parts[11]) if len(parts) > 11 else None
            pcie_gen = parse_numeric(parts[12]) if len(parts) > 12 else None
            pcie_width = parse_numeric(parts[13]) if len(parts) > 13 else None

            mem_percent = None
            if mem_total is not None and mem_used is not None and mem_total > 0:
                mem_percent = round(float(mem_used) / float(mem_total) * 100, 1)

            gpus.append({
                "id": idx,
                "name": name,
                "vendor": "NVIDIA",
                "provider": "nvidia-smi",
                "gpu_util": usage,
                "temp_c": temp,
                "mem_used_mb": mem_used,
                "mem_total_mb": mem_total,
                "mem_free_mb": mem_free,
                "mem_percent": mem_percent,
                "power_draw_w": round(float(power), 1) if power is not None else None,
                "clock_core_mhz": clock_core,
                "clock_mem_mhz": clock_mem,
                "fan_speed_pct": fan_pct,
                "pcie_gen": pcie_gen,
                "pcie_width": pcie_width,
                "driver_version": driver,
            })
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return gpus


# ── AMD SMI / PowerShell fallback (WSL-aware) ───────────────────────────

def collect_amd_smi_fallback() -> list[dict[str, Any]]:
    """
    WSL-aware AMD GPU fallback.
    Pass 1 — rocm-smi(.exe) --json  (full stats when ROCm drivers are installed)
    Pass 2 — powershell.exe WMI     (name + VRAM when ROCm is absent)
    Returns [] on total failure so the caller can chain further fallbacks.
    """
    try:
        def _sf(v: Any, default: float | None = None) -> float | None:
            try:
                return float(str(v).rstrip("cCwW%"))
            except (ValueError, TypeError):
                return default

        def _si(v: Any, default: int | None = None) -> int | None:
            try:
                return int(float(str(v).rstrip("cCwW%")))
            except (ValueError, TypeError):
                return default

        # ── Pass 1: rocm-smi ────────────────────────────────────────────
        try:
            result = subprocess.run(
                [
                    _AMD_ROCM_SMI,
                    "--showuse", "--showtemp", "--showpower",
                    "--showmeminfo", "vram",
                    "--json",
                ],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                gpus: list[dict[str, Any]] = []
                for i, (_card, info) in enumerate(data.items()):
                    if not isinstance(info, dict):
                        continue

                    def _pick(keys: list[str]) -> Any:
                        for dk, dv in info.items():
                            if any(k.lower() in dk.lower() for k in keys):
                                return dv
                        return None

                    vram_used_b  = _sf(_pick(["vram total used memory"]))
                    vram_total_b = _sf(_pick(["vram total memory"]))
                    name = (
                        info.get("Card series")
                        or info.get("Card model")
                        or info.get("Card vendor")
                        or f"AMD GPU {i}"
                    )
                    gpus.append({
                        "id": i,
                        "name": name,
                        "vendor": "AMD",
                        "provider": "rocm-smi",
                        "gpu_util": _sf(_pick(["gpu use"])),
                        "temp_c":   _si(_pick(["temperature (sensor edge)",
                                               "temperature (sensor junction)"])),
                        "power_draw_w": _sf(_pick(["average graphics package power",
                                                    "current socket graphics package power"])),
                        "mem_used_mb":  round(vram_used_b  / (1024 * 1024)) if vram_used_b is not None else None,
                        "mem_total_mb": round(vram_total_b / (1024 * 1024)) if vram_total_b is not None else None,
                    })
                if gpus:
                    return gpus
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            pass

        # ── Pass 2: powershell.exe WMI (Windows host, works from WSL) ───
        try:
            ps_script = (
                "Get-CimInstance Win32_VideoController "
                "| Where-Object {$_.Name -match 'AMD|Radeon|ATI'} "
                "| Select-Object Name, AdapterRAM "
                "| ConvertTo-Json -Compress"
            )
            result = subprocess.run(
                ["powershell.exe", "-NonInteractive", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                raw = json.loads(result.stdout)
                if isinstance(raw, dict):
                    raw = [raw]
                gpus = []
                for i, item in enumerate(raw):
                    if not isinstance(item, dict):
                        continue
                    vram_total_b = item.get("AdapterRAM") or 0
                    gpus.append({
                        "id": i,
                        "name": item.get("Name") or f"AMD GPU {i}",
                        "vendor": "AMD",
                        "provider": "powershell-wmi",
                        "gpu_util":     None,
                        "temp_c":       None,
                        "power_draw_w": None,
                        "mem_used_mb":  None,
                        "mem_total_mb": round(vram_total_b / (1024 * 1024)) if vram_total_b else None,
                    })
                if gpus:
                    return gpus
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            pass

    except Exception:
        pass

    return []


# ── AMD (pyadl) ─────────────────────────────────────────────────────────

def init_amd_adl() -> bool:
    try:
        from pyadl import ADLManager
        ADLManager.getInstance()
        return True
    except (ImportError, RuntimeError, OSError, Exception):
        return False


def collect_amd_metrics(amd_adl_enabled: bool) -> list[dict[str, Any]]:
    if not amd_adl_enabled:
        return []

    gpus = []
    try:
        from pyadl import ADLManager

        mgr = ADLManager.getInstance()
        devices = mgr.getDevices()

        for dev in devices:
            try:
                gpu: dict[str, Any] = {
                    "id": 0,
                    "name": dev.adapterName if hasattr(dev, "adapterName") else "AMD GPU",
                    "vendor": "AMD",
                    "provider": "pyadl",
                }

                with contextlib.suppress(Exception):
                    gpu["temp_c"] = dev.getCurrentTemperature()
                with contextlib.suppress(Exception):
                    gpu["fan_speed_pct"] = dev.getCurrentFanSpeed(ADLManager.ADL_DEVICE_FAN_SPEED_PERCENTAGE)
                with contextlib.suppress(Exception):
                    gpu["clock_core_mhz"] = dev.getCurrentEngineClock()
                with contextlib.suppress(Exception):
                    gpu["clock_mem_mhz"] = dev.getCurrentMemoryClock()
                with contextlib.suppress(Exception):
                    gpu["gpu_util"] = dev.getCurrentUsage()

                gpus.append(gpu)
            except Exception:
                pass
    except Exception:
        pass
    return gpus


# ── lspci fallback (Linux native) ──────────────────────────────────────

def collect_lspci_fallback() -> list[dict[str, Any]]:
    """Fallback: detect GPU names via lspci."""
    gpus = []
    try:
        import subprocess
        result = subprocess.run(
            ["lspci", "-nn"],
            capture_output=True, text=True, timeout=5,
        )
        for line in (result.stdout or "").splitlines():
            lower = line.lower()
            if "vga" in lower or "3d" in lower or "display" in lower:
                # Extract GPU name from lspci output
                parts = line.split(": ", 1)
                name = parts[1].strip() if len(parts) > 1 else line.strip()
                vendor = "Unknown"
                if "nvidia" in lower:
                    vendor = "NVIDIA"
                elif "amd" in lower or "radeon" in lower:
                    vendor = "AMD"
                elif "intel" in lower:
                    vendor = "Intel"
                gpus.append({
                    "id": len(gpus),
                    "name": name,
                    "vendor": vendor,
                    "provider": "lspci",
                    "gpu_util": None,
                    "temp_c": None,
                    "mem_total_mb": None,
                    "mem_used_mb": None,
                })
    except Exception:
        pass
    return gpus


# ── VM GPU name resolver ────────────────────────────────────────────────

# Strings that indicate a virtual / generic GPU name that should be overridden
_VM_NAME_INDICATORS: frozenset[str] = frozenset([
    "basic render driver", "vmware svga", "microsoft", "virtual",
    "llvmpipe", "softpipe", "virgl", "qxl", "bochs", "cirrus",
])

_HEX_CODE_RE = re.compile(r"\[[\da-fA-F:]+\]")


def _vm_name(name: str) -> bool:
    nl = name.lower()
    return any(ind in nl for ind in _VM_NAME_INDICATORS)


def _resolve_display_names(gpus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    When all GPU names look like VM / generic drivers, query lshw or glxinfo
    for the real VGA controller string and substitute it in.
    Only runs on bare-metal Linux (not WSL) where these tools are meaningful.
    """
    if _IS_WSL or not gpus:
        return gpus
    if not any(_vm_name(g.get("name", "")) for g in gpus):
        return gpus  # names already look real

    real_name = ""

    # Pass 1 — lshw -C display → first "product:" line
    if not real_name:
        try:
            result = subprocess.run(
                ["lshw", "-C", "display"],
                capture_output=True, text=True, timeout=8,
            )
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if stripped.lower().startswith("product:"):
                    candidate = stripped.split(":", 1)[1].strip()
                    candidate = _HEX_CODE_RE.sub("", candidate).strip()
                    if candidate and not _vm_name(candidate):
                        real_name = candidate
                        break
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

    # Pass 2 — glxinfo → "OpenGL renderer string:"
    if not real_name:
        try:
            result = subprocess.run(
                ["glxinfo"],
                capture_output=True, text=True, timeout=8,
            )
            for line in result.stdout.splitlines():
                if "opengl renderer string" in line.lower():
                    candidate = line.split(":", 1)[1].strip()
                    if not _vm_name(candidate):
                        real_name = candidate
                        break
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

    if not real_name:
        return gpus

    for g in gpus:
        if _vm_name(g.get("name", "")):
            g["name"] = real_name
    return gpus


# ── DRM supplement ─────────────────────────────────────────────────────

_REV_RE   = re.compile(r"\s*\(rev\s+[0-9a-fA-F]+\)\s*$")
_PCI_ID_RE = re.compile(r"\[[\da-fA-F]{4}:[\da-fA-F]{4}\]$")


def _lspci_name(pci_address: str) -> str:
    """Return a cleaned GPU name from lspci for *pci_address*, or empty string."""
    if not pci_address:
        return ""
    try:
        result = subprocess.run(
            ["lspci", "-s", pci_address, "-nn"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return ""
        line = result.stdout.strip()
        line = _REV_RE.sub("", line)
        m = _PCI_ID_RE.search(line)
        if m:
            line = line[: m.start()].strip()
        parts = line.split(": ", 2)
        if len(parts) >= 3:
            return parts[2].strip().rstrip(":")
        if len(parts) == 2:
            return parts[1].strip().rstrip(":")
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return ""


def _supplement_undetected_gpus(all_gpus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Add any GPU vendor that primary collectors missed.

    Two-pass scan so that GPUs are found regardless of driver state:
      Pass 1 — /sys/class/drm: catches GPUs with any kernel driver loaded
                (nvidia, nouveau, amdgpu, i915, …)
      Pass 2 — lspci: catches GPUs that have NO driver loaded at all,
                e.g. NVIDIA dGPU in PRIME offload / power-off state on Ubuntu

    Deduplication is by vendor name — one entry per distinct vendor is enough
    for the most common multi-GPU laptop configurations.
    """
    found_vendors: set[str] = {g.get("vendor", "").upper() for g in all_gpus}
    found_vendors.discard("")

    # ── Pass 1: DRM cards ────────────────────────────────────────────────
    try:
        from backend.platform.linux.drm_enumeration import enumerate_drm_cards
        for card in enumerate_drm_cards():
            if card.vendor_name.upper() in found_vendors:
                continue
            name = _lspci_name(card.pci_address) or f"{card.vendor_name} GPU"
            all_gpus.append({
                "id": 0, "name": name, "vendor": card.vendor_name,
                "provider": "lspci", "driver": card.driver, "pci_bus": card.pci_address,
            })
            found_vendors.add(card.vendor_name.upper())
            logger.debug("GPU supplement (DRM): added %s %s", card.vendor_name, name)
    except Exception:
        logger.debug("GPU supplement pass 1 (DRM) failed", exc_info=True)

    # ── Pass 2: lspci scan ───────────────────────────────────────────────
    # Catches GPUs with no driver at all (e.g. NVIDIA in Optimus power-off).
    try:
        result = subprocess.run(
            ["lspci", "-nn"], capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            lower = line.lower()
            if not ("vga" in lower or "3d" in lower or "display" in lower):
                continue

            if "nvidia" in lower:
                vendor = "NVIDIA"
            elif "amd" in lower or "radeon" in lower or "ati" in lower:
                vendor = "AMD"
            elif "intel" in lower:
                vendor = "Intel"
            else:
                continue  # unknown vendor — skip

            if vendor.upper() in found_vendors:
                continue

            # Extract PCI address (first token, e.g. "01:00.0")
            pci_short = line.split()[0] if line.split() else ""
            name = _lspci_name(pci_short) if pci_short else ""
            if not name:
                line_c = _REV_RE.sub("", line)
                m = _PCI_ID_RE.search(line_c)
                if m:
                    line_c = line_c[: m.start()].strip()
                parts = line_c.split(": ", 1)
                name = parts[1].strip() if len(parts) > 1 else f"{vendor} GPU"

            all_gpus.append({
                "id": 0, "name": name, "vendor": vendor,
                "provider": "lspci", "pci_bus": pci_short,
            })
            found_vendors.add(vendor.upper())
            logger.debug("GPU supplement (lspci): added %s %s", vendor, name)
    except Exception:
        logger.debug("GPU supplement pass 2 (lspci) failed", exc_info=True)

    return all_gpus


# ── Main Loop ───────────────────────────────────────────────────────────

def main() -> None:
    nvml_enabled    = init_nvidia()
    amd_adl_enabled = init_amd_adl()

    emit({
        "type":        "init",
        "nvidia":      nvml_enabled,
        "amd_adl":     amd_adl_enabled,
        # amd_sysfs is always attempted; report whether the module loaded cleanly.
        "amd_sysfs":   True,
        "ts":          time.time(),
    })

    while True:
        start = time.time()

        try:
            all_gpus: list[dict[str, Any]] = []

            # ── NVIDIA (pynvml primary, nvidia-smi vendor fallback) ─────
            # nvidia-smi runs as a vendor-specific fallback whenever pynvml is
            # unavailable — independently of whether AMD was detected.  This
            # ensures both GPUs appear on hybrid AMD-iGPU + NVIDIA-dGPU laptops.
            if nvml_enabled:
                try:
                    all_gpus.extend(collect_nvidia_metrics(nvml_enabled))
                except Exception as exc:
                    emit({"type": "vendor_error", "vendor": "nvidia",
                          "msg": str(exc), "ts": time.time()})
            else:
                try:
                    nvidia_smi_gpus = collect_nvidia_smi_fallback()
                    if nvidia_smi_gpus:
                        all_gpus.extend(nvidia_smi_gpus)
                except Exception:
                    pass

            # ── AMD — native sysfs provider (amdgpu driver, no ROCm needed) ──
            # Runs unconditionally. If sysfs finds AMD cards, pyadl is skipped
            # to avoid duplicates (pyadl has no effect on bare-metal Linux).
            amd_sysfs_gpus: list[dict[str, Any]] = []
            try:
                amd_sysfs_gpus = collect_amd_sysfs()
                if amd_sysfs_gpus:
                    all_gpus.extend(amd_sysfs_gpus)
            except Exception as exc:
                emit({"type": "vendor_error", "vendor": "amd_sysfs",
                      "msg": str(exc), "ts": time.time()})

            if amd_adl_enabled and not amd_sysfs_gpus:
                try:
                    all_gpus.extend(collect_amd_metrics(amd_adl_enabled))
                except Exception as exc:
                    emit({"type": "vendor_error", "vendor": "amd_adl",
                          "msg": str(exc), "ts": time.time()})

            # ── GPU supplement ───────────────────────────────────────────
            # Add any GPU vendor that primary collectors missed.
            # DRM pass catches GPUs with a driver; lspci pass catches GPUs
            # with no driver loaded at all (NVIDIA in PRIME offload/power-off).
            all_gpus = _supplement_undetected_gpus(all_gpus)

            # Re-assign sequential IDs after all primary + supplement collection
            for idx, gpu in enumerate(all_gpus):
                gpu["id"] = idx

            # ── Absolute last resort: AMD SMI then lspci ─────────────────
            # Only when no vendor-specific path found anything at all.
            if not all_gpus:
                try:
                    all_gpus = collect_amd_smi_fallback()
                except Exception:
                    pass

            if not all_gpus:
                try:
                    all_gpus = collect_lspci_fallback()
                except Exception:
                    pass

            # Override VM / generic display names with real hardware names
            try:
                all_gpus = _resolve_display_names(all_gpus)
            except Exception:
                pass

            # Translate snake_case keys → camelCase QML schema
            all_gpus = [normalise_gpu(g) for g in all_gpus]

            emit({
                "type":  "metrics",
                "ts":    time.time(),
                "count": len(all_gpus),
                "gpus":  all_gpus,
            })

        except Exception as exc:
            emit({
                "type":  "error",
                "msg":   str(exc),
                "trace": traceback.format_exc()[:500],
                "ts":    time.time(),
            })

        emit({"type": "heartbeat", "ts": time.time()})

        elapsed    = time.time() - start
        sleep_time = max(0.0, INTERVAL - elapsed)
        time.sleep(sleep_time)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        emit({"type": "shutdown", "ts": time.time()})
        sys.exit(0)
    except Exception as e:
        emit({
            "type": "fatal",
            "msg": str(e),
            "trace": traceback.format_exc()[:500],
            "ts": time.time(),
        })
        sys.exit(1)
