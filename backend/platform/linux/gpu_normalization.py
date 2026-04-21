"""Linux GPU metric normalization helpers."""

from __future__ import annotations

from typing import Any

KEY_MAP = {
    "gpu_util":      "usage",
    "mem_util":      "memControllerUtil",
    "temp_c":        "tempC",
    "mem_total_mb":  "memTotalMB",
    "mem_used_mb":   "memUsedMB",
    "mem_free_mb":   "memFreeMB",
    "mem_percent":   "memPercent",
    "clock_core_mhz": "clockMHz",
    "clock_mem_mhz": "clockMemMHz",
    "power_draw_w":  "powerW",
    "power_limit_w": "powerLimitW",
    "fan_speed_pct": "fanPercent",
    "fan_rpm":       "fanRPM",
    "driver_version": "driverVersion",
    "pcie_gen":      "pcieGen",
    "pcie_width":    "pcieWidth",
    "encoder_util":  "encoderUtil",
    "decoder_util":  "decoderUtil",
}

NUMERIC_METRICS = {
    "usage",
    "memControllerUtil",
    "tempC",
    "tempHotspot",
    "tempMemC",
    "memUsedMB",
    "memTotalMB",
    "memFreeMB",
    "memPercent",
    "clockMHz",
    "clockMemMHz",
    "clockSMMHz",
    "powerW",
    "powerLimitW",
    "powerPercent",
    "fanPercent",
    "fanRPM",
    "pcieGen",
    "pcieWidth",
    "encoderUtil",
    "decoderUtil",
    "voltageMV",
    "maxClockMHz",
    "maxClockMemMHz",
}

STATUS_OK            = "ok"
STATUS_UNAVAILABLE   = "unavailable"
STATUS_UNSUPPORTED   = "unsupported"
STATUS_PERMISSION    = "permission_denied"
STATUS_NOT_EXPOSED   = "not_exposed"
STATUS_BACKEND_ERROR = "backend_error"
# Used by AMD iGPU / APU where memory is shared with system RAM and
# no dedicated VRAM figure is available from sysfs.
STATUS_SHARED_MEMORY = "shared_memory"

NA_TOKENS = {"", "n/a", "na", "[not supported]", "not supported", "unsupported", "--"}


def parse_numeric(value: Any) -> float | int | None:
    """Parse a possibly-missing numeric token."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if text.lower() in NA_TOKENS:
        return None
    try:
        num = float(text)
    except ValueError:
        return None
    return int(num) if num.is_integer() else num


def _default_metric_status(metric: str, vendor: str, provider: str) -> str:
    if provider == "lspci":
        return STATUS_UNSUPPORTED
    if metric in {"encoderUtil", "decoderUtil", "clockSMMHz", "cudaVersion", "perfState"}:
        return STATUS_UNSUPPORTED if vendor != "NVIDIA" else STATUS_NOT_EXPOSED
    if metric in {"tempHotspot", "tempMemC", "fanRPM", "voltageMV"}:
        return STATUS_NOT_EXPOSED
    return STATUS_UNAVAILABLE


def _provider_status(provider: str, raw: dict[str, Any]) -> tuple[str, str]:
    detail = str(raw.get("providerDetail") or "")
    explicit = raw.get("providerStatus")
    if explicit:
        return str(explicit), detail
    if provider == "lspci":
        return STATUS_UNSUPPORTED, detail or "Device detected, but no telemetry backend is available."
    # amdgpu-sysfs is a live native provider — treat identically to nvml / nvidia-smi
    return STATUS_OK, detail


_NON_OVERRIDABLE_STATUSES = frozenset({STATUS_SHARED_MEMORY, STATUS_PERMISSION})


def _normalize_metric_status(out: dict[str, Any], metric_status: dict[str, str], vendor: str, provider: str) -> None:
    for metric in NUMERIC_METRICS:
        # Preserve statuses that carry explicit semantic meaning (e.g., shared_memory
        # set by the AMD sysfs provider) even when the metric value is None.
        if metric_status.get(metric) in _NON_OVERRIDABLE_STATUSES:
            continue
        value = out.get(metric)
        if value is not None:
            metric_status.setdefault(metric, STATUS_OK)
        else:
            metric_status.setdefault(metric, _default_metric_status(metric, vendor, provider))


def normalise_gpu(raw: dict[str, Any]) -> dict[str, Any]:
    """Translate Linux collector payloads into the shared QML schema."""
    out: dict[str, Any] = {}
    metric_status = {str(k): str(v) for k, v in (raw.get("metricStatus") or {}).items()}
    metric_messages = {str(k): str(v) for k, v in (raw.get("metricMessages") or {}).items()}

    for key, value in raw.items():
        mapped = KEY_MAP.get(key, key)
        if mapped in NUMERIC_METRICS:
            out[mapped] = parse_numeric(value)
        else:
            out[mapped] = value

    out.setdefault("id", 0)
    out.setdefault("name", "Unknown GPU")
    out.setdefault("vendor", "Unknown")
    out.setdefault("driverVersion", "Unknown")
    out.setdefault("provider", raw.get("provider", "unknown"))
    for metric in NUMERIC_METRICS:
        out.setdefault(metric, None)

    provider_status, provider_detail = _provider_status(str(out["provider"]), raw)
    out["providerStatus"] = provider_status
    out["providerDetail"] = provider_detail

    _normalize_metric_status(out, metric_status, str(out.get("vendor", "Unknown")), str(out.get("provider", "unknown")))

    mem_total = out.get("memTotalMB")
    mem_used = out.get("memUsedMB")
    # Skip computed percent when the provider explicitly annotated memory
    # with a non-overridable status (e.g., shared_memory on AMD iGPU).
    _mem_status_pre = metric_status.get("memPercent")
    if _mem_status_pre not in _NON_OVERRIDABLE_STATUSES:
        if mem_total is not None and mem_used is not None and mem_total > 0:
            out["memPercent"] = round((float(mem_used) / float(mem_total)) * 100.0, 1)
            metric_status["memPercent"] = STATUS_OK
        else:
            out.setdefault("memPercent", None)
            metric_status.setdefault("memPercent", _default_metric_status("memPercent", str(out["vendor"]), str(out["provider"])))

    power_w = out.get("powerW")
    power_limit = out.get("powerLimitW")
    if power_w is not None and power_limit is not None and power_limit > 0:
        out["powerPercent"] = round((float(power_w) / float(power_limit)) * 100.0, 1)
        metric_status["powerPercent"] = STATUS_OK
    else:
        out.setdefault("powerPercent", None)
        metric_status.setdefault("powerPercent", _default_metric_status("powerPercent", str(out["vendor"]), str(out["provider"])))

    out["metricStatus"] = metric_status
    out["metricMessages"] = metric_messages
    return out
