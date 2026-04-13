"""Regression tests for the psutil-backed system monitor."""

# nosec B101 - assert statements are expected in pytest test files

import sys
import types

from backend.infra import system_monitor_psutil as sm


class _BrokenWmiConnection:
    """Fake WMI connection that denies GPU-related access."""

    def Win32_VideoController(self):
        raise PermissionError("Access denied")

    def Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine(self):
        raise PermissionError("Access denied")


def test_monitor_init_ignores_wmi_gpu_access_denied(monkeypatch):
    """Constructor should not fail when WMI blocks GPU enumeration."""
    fake_wmi = types.SimpleNamespace(
        WMI=lambda namespace=None: _BrokenWmiConnection()
    )

    monkeypatch.setattr(sm, "HAS_WMI", True)
    monkeypatch.setattr(sm, "HAS_NVIDIA", False)
    monkeypatch.setitem(sys.modules, "wmi", fake_wmi)

    monitor = sm.PsutilSystemMonitor()

    assert monitor._wmi_cache is None
    assert monitor._pnp_to_phys_cache is None


def test_get_gpu_info_ignores_runtime_wmi_gpu_access_denied():
    """GPU info lookup should degrade cleanly when cached WMI access breaks."""
    monitor = sm.PsutilSystemMonitor()
    monitor._wmi_cache = _BrokenWmiConnection()
    monitor._pnp_to_phys_cache = {}
    monitor._nvml_initialized = False

    result = monitor._get_gpu_info()

    assert result["count"] == 0
    assert result["gpus"] == []
    assert monitor._wmi_cache is None
    assert monitor._pnp_to_phys_cache is None
