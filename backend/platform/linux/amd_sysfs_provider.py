"""
AMD GPU telemetry provider for Linux — native sysfs / DRM / hwmon.

Reads GPU metrics directly from the kernel's sysfs interface exposed by the
amdgpu driver.  No ROCm, no pyadl, no external binaries required.

Supported hardware:
  - AMD discrete GPUs (RX 5xx / 6xx / 7xx series, Vega, …)
  - AMD integrated GPUs / APUs (Ryzen with Radeon graphics)

Data sources (all optional — missing nodes are handled gracefully):
  .../device/gpu_busy_percent         → GPU utilisation %
  .../device/mem_info_vram_total      → VRAM total (bytes)
  .../device/mem_info_vram_used       → VRAM used  (bytes)
  .../device/mem_info_gtt_total       → GTT / shared pool total (bytes)
  .../device/mem_info_gtt_used        → GTT / shared pool used  (bytes)
  .../device/hwmon/hwmonN/temp1_input → GPU edge temperature (milli-°C)
  .../device/hwmon/hwmonN/power1_average → average power draw (microwatts)
  .../device/hwmon/hwmonN/pwm1        → fan duty cycle (0-255)
  .../device/hwmon/hwmonN/fan1_input  → fan speed (RPM)
  /sys/module/amdgpu/version          → driver/DRM version string

GPU name is resolved via lspci (optional — fails gracefully to a synthetic ID).

iGPU / APU memory note:
  APUs may report a small VRAM reservation (the BIOS framebuffer) or zero.
  When vram_total < _MIN_DEDICATED_VRAM_BYTES the memory metrics are marked
  with status "shared_memory" so the UI can display an informative label
  rather than a misleading "0 B" or "Unavailable".
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from backend.platform.linux.drm_enumeration import VENDOR_AMD, DRMCard, enumerate_drm_cards

logger = logging.getLogger(__name__)

# Minimum dedicated VRAM to treat memory as distinct from shared system memory.
# Below this threshold the GPU is using shared (GTT) memory and we avoid
# fabricating a dedicated-VRAM figure.
_MIN_DEDICATED_VRAM_BYTES = 32 * 1024 * 1024  # 32 MiB

STATUS_SHARED_MEMORY = "shared_memory"


# ── sysfs read helpers ───────────────────────────────────────────────────────

def _sysfs_int(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def _sysfs_str(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


# ── hwmon helpers ────────────────────────────────────────────────────────────

def _find_hwmon(device_path: Path) -> Path | None:
    """Return the first hwmonN directory under device_path/hwmon/, or None."""
    hwmon_base = device_path / "hwmon"
    if not hwmon_base.exists():
        return None
    try:
        for entry in sorted(hwmon_base.iterdir()):
            if entry.name.startswith("hwmon"):
                return entry
    except OSError:
        pass
    return None


def _read_temp_c(hwmon: Path) -> int | None:
    """temp1_input is in milli-degrees C.  Returns whole degrees C."""
    raw = _sysfs_int(hwmon / "temp1_input")
    if raw is None:
        return None
    return round(raw / 1000)


def _read_power_w(hwmon: Path) -> float | None:
    """power1_average is in microwatts.  Returns watts with 1 decimal place."""
    raw = _sysfs_int(hwmon / "power1_average")
    if raw is None:
        return None
    return round(raw / 1_000_000, 1)


def _read_fan_pct(hwmon: Path) -> int | None:
    """pwm1 is a 0-255 duty cycle.  Returns percent 0-100."""
    raw = _sysfs_int(hwmon / "pwm1")
    if raw is None:
        return None
    return round(raw * 100 / 255)


def _read_fan_rpm(hwmon: Path) -> int | None:
    """fan1_input is raw RPM."""
    return _sysfs_int(hwmon / "fan1_input")


# ── GPU name resolution ──────────────────────────────────────────────────────

def _resolve_gpu_name(card: DRMCard) -> str:
    """
    Resolve a human-readable GPU name via lspci using the card's PCI address.

    Falls back to a synthesized "AMD GPU [VVVV:DDDD]" string when lspci is
    unavailable or returns nothing useful.
    """
    if card.pci_address:
        try:
            result = subprocess.run(
                ["lspci", "-s", card.pci_address, "-nn"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                line = result.stdout.strip()
                # Typical lspci -nn line:
                # "00:08.1 Display controller [0380]: AMD/ATI Rembrandt [Radeon 680M] [1002:1681] (rev 0a)"
                # 1. Strip trailing "(rev XX)" — must happen before the bracket search.
                line = re.sub(r"\s*\(rev\s+[0-9a-fA-F]+\)\s*$", "", line)
                # 2. Strip the trailing vendor:device ID bracket "[VVVV:DDDD]".
                match = re.search(r"\[[\da-fA-F]{4}:[\da-fA-F]{4}\]$", line)
                if match:
                    line = line[: match.start()].strip()
                # 3. Split on the first ": " after the bus address.
                parts = line.split(": ", 2)
                if len(parts) >= 3:
                    return parts[2].strip().rstrip(":")
                elif len(parts) == 2:
                    return parts[1].strip().rstrip(":")
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

    return f"AMD GPU [{card.vendor_id:04x}:{card.device_id:04x}]"


# ── driver version ───────────────────────────────────────────────────────────

def _read_driver_version() -> str:
    """
    Return the amdgpu kernel module version string.

    /sys/module/amdgpu/version is the preferred source (kernel 5.x+).
    Falls back to `modinfo amdgpu --field=version` if the sysfs node is absent.
    Returns an empty string when neither source is available.
    """
    version_path = Path("/sys/module/amdgpu/version")
    if version_path.exists():
        v = _sysfs_str(version_path)
        if v:
            return v

    try:
        result = subprocess.run(
            ["modinfo", "amdgpu", "--field=version"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            v = result.stdout.strip()
            if v:
                return v
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return ""


# ── per-card metric collection ───────────────────────────────────────────────

def _collect_card_metrics(card: DRMCard, card_index: int) -> dict[str, Any]:
    """
    Collect all available sysfs metrics for one AMD DRM card.

    Output keys use the same snake_case convention as the NVIDIA pynvml collector
    so that gpu_normalization.normalise_gpu() can map them to camelCase uniformly.

    Memory handling:
      - If vram_total >= _MIN_DEDICATED_VRAM_BYTES → report as dedicated VRAM.
      - Otherwise (iGPU / small BIOS reservation) → set both mem_total_mb and
        mem_used_mb to None and add "shared_memory" entries to metricStatus /
        metricMessages so the UI shows "Shared memory" instead of "Unavailable".
    """
    device = card.device_path

    metrics: dict[str, Any] = {
        "id":            card_index,
        "name":          _resolve_gpu_name(card),
        "vendor":        "AMD",
        "provider":      "amdgpu-sysfs",
        "driver":        card.driver,       # "amdgpu"
        "pci_bus":       card.pci_address,
        "is_integrated": card.is_integrated,
    }

    # GPU utilisation (0-100 %)
    metrics["gpu_util"] = _sysfs_int(device / "gpu_busy_percent")

    # Memory
    vram_total_b = _sysfs_int(device / "mem_info_vram_total")
    vram_used_b  = _sysfs_int(device / "mem_info_vram_used")
    gtt_total_b  = _sysfs_int(device / "mem_info_gtt_total")
    gtt_used_b   = _sysfs_int(device / "mem_info_gtt_used")

    has_dedicated_vram = (
        vram_total_b is not None and vram_total_b >= _MIN_DEDICATED_VRAM_BYTES
    )

    if has_dedicated_vram:
        metrics["mem_total_mb"] = round(vram_total_b / (1024 * 1024))  # type: ignore[arg-type]
        if vram_used_b is not None:
            metrics["mem_used_mb"] = round(vram_used_b / (1024 * 1024))
        # Expose GTT pool size as informational metadata (not shown in VRAM tiles)
        if gtt_total_b is not None:
            metrics["gtt_total_mb"] = round(gtt_total_b / (1024 * 1024))
    else:
        # iGPU / APU — no distinct dedicated VRAM
        metrics["mem_total_mb"] = None
        metrics["mem_used_mb"]  = None
        # Pre-seed metricStatus / metricMessages so normalise_gpu() carries them through
        _msg = "Shared memory"
        metrics["metricStatus"] = {
            "memTotalMB":  STATUS_SHARED_MEMORY,
            "memUsedMB":   STATUS_SHARED_MEMORY,
            "memPercent":  STATUS_SHARED_MEMORY,
            "memFreeMB":   STATUS_SHARED_MEMORY,
        }
        metrics["metricMessages"] = {
            "memTotalMB": _msg,
            "memUsedMB":  _msg,
            "memPercent": _msg,
            "memFreeMB":  _msg,
        }
        # Still surface GTT pool metadata
        if gtt_total_b is not None:
            metrics["gtt_total_mb"] = round(gtt_total_b / (1024 * 1024))
        if gtt_used_b is not None:
            metrics["gtt_used_mb"] = round(gtt_used_b / (1024 * 1024))

    # Hwmon sensors (temperature, power, fan)
    hwmon = _find_hwmon(device)
    if hwmon:
        metrics["temp_c"]        = _read_temp_c(hwmon)
        metrics["power_draw_w"]  = _read_power_w(hwmon)
        metrics["fan_speed_pct"] = _read_fan_pct(hwmon)
        metrics["fan_rpm"]       = _read_fan_rpm(hwmon)

    # Driver / DRM version — fall back to the kernel driver name ("amdgpu")
    # so QML always shows something meaningful instead of "Unknown".
    driver_version = _read_driver_version()
    metrics["driver_version"] = driver_version if driver_version else card.driver

    return metrics


# ── public API ───────────────────────────────────────────────────────────────

def collect_amd_sysfs() -> list[dict[str, Any]]:
    """
    Enumerate AMD DRM cards and return available metrics collected from sysfs.

    Returns an empty list when:
      - /sys/class/drm does not exist (non-Linux environment)
      - no AMD card with the amdgpu driver is found
      - an unexpected error occurs at the enumeration level

    Per-card errors are caught and logged individually; other cards still
    appear in the result.
    """
    try:
        all_cards = enumerate_drm_cards()
    except Exception:
        logger.exception("AMD sysfs provider: DRM enumeration failed")
        return []

    amd_cards = [
        c for c in all_cards
        if c.vendor_id == VENDOR_AMD and c.driver == "amdgpu"
    ]

    if not amd_cards:
        logger.debug("AMD sysfs provider: no amdgpu-backed DRM cards found")
        return []

    logger.info("AMD sysfs provider: found %d card(s)", len(amd_cards))

    results: list[dict[str, Any]] = []
    for idx, card in enumerate(amd_cards):
        try:
            gpu = _collect_card_metrics(card, idx)
            results.append(gpu)
            logger.debug(
                "AMD %s: usage=%s%% temp=%sC power=%sW vram=%s/%sMB pci=%s",
                card.card_name,
                gpu.get("gpu_util"),
                gpu.get("temp_c"),
                gpu.get("power_draw_w"),
                gpu.get("mem_used_mb"),
                gpu.get("mem_total_mb"),
                card.pci_address or "?",
            )
        except Exception:
            logger.exception(
                "AMD sysfs provider: failed to collect metrics for %s", card.card_name
            )

    return results
