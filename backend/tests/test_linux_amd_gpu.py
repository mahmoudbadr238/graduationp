"""
Tests for Linux AMD GPU detection and normalization.

Covers:
  - DRM card enumeration (connector filtering, vendor/driver reading)
  - AMD sysfs provider (discrete VRAM, iGPU shared-memory, hwmon sensors)
  - gpu_normalization integration (shared_memory status, fan_rpm key, provider status)
  - Regression guards ensuring Windows normalization behavior is unaffected
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── DRM enumeration ──────────────────────────────────────────────────────────

from backend.platform.linux.drm_enumeration import (
    VENDOR_AMD,
    VENDOR_INTEL,
    VENDOR_NVIDIA,
    DRMCard,
    enumerate_drm_cards,
)


class _FakeDRMRoot:
    """Helper that builds a temporary /sys/class/drm-like directory tree."""

    def __init__(self, tmp_path: Path):
        self.root = tmp_path / "drm"
        self.root.mkdir()

    def add_card(
        self,
        name: str,
        vendor_id: int,
        device_id: int = 0x1234,
        driver: str = "amdgpu",
        pci_class: int = 0x038000,
    ) -> Path:
        card_dir = self.root / name
        device_dir = card_dir / "device"
        device_dir.mkdir(parents=True)

        (device_dir / "vendor").write_text(f"0x{vendor_id:04x}\n")
        (device_dir / "device").write_text(f"0x{device_id:04x}\n")
        (device_dir / "class").write_text(f"0x{pci_class:06x}\n")

        # Create a driver symlink target directory and symlink
        driver_dir = device_dir / "_driver_target" / driver
        driver_dir.mkdir(parents=True)
        driver_link = device_dir / "driver"
        driver_link.symlink_to(driver_dir)

        return card_dir

    def add_connector(self, name: str) -> Path:
        """Add a connector entry (card0-DP-1 style) that must be filtered out."""
        connector_dir = self.root / name
        connector_dir.mkdir()
        return connector_dir


def test_enumerate_drm_filters_connector_entries(tmp_path: Path):
    fake = _FakeDRMRoot(tmp_path)
    fake.add_card("card0", VENDOR_AMD)
    fake.add_connector("card0-DP-1")
    fake.add_connector("card0-HDMI-A-1")
    fake.add_connector("card0-eDP-1")

    cards = enumerate_drm_cards(fake.root)

    assert len(cards) == 1
    assert cards[0].card_name == "card0"


def test_enumerate_drm_returns_empty_when_no_drm_dir(tmp_path: Path):
    cards = enumerate_drm_cards(tmp_path / "nonexistent")
    assert cards == []


def test_enumerate_drm_skips_card_without_vendor_file(tmp_path: Path):
    fake = _FakeDRMRoot(tmp_path)
    card_dir = fake.root / "card0" / "device"
    card_dir.mkdir(parents=True)
    # No vendor file written

    cards = enumerate_drm_cards(fake.root)
    assert cards == []


def test_enumerate_drm_reads_amd_vendor(tmp_path: Path):
    fake = _FakeDRMRoot(tmp_path)
    fake.add_card("card0", VENDOR_AMD, device_id=0x1636, driver="amdgpu")

    cards = enumerate_drm_cards(fake.root)

    assert len(cards) == 1
    c = cards[0]
    assert c.vendor_id == VENDOR_AMD
    assert c.vendor_name == "AMD"
    assert c.device_id == 0x1636
    assert c.driver == "amdgpu"


def test_enumerate_drm_reads_nvidia_vendor(tmp_path: Path):
    fake = _FakeDRMRoot(tmp_path)
    fake.add_card("card0", VENDOR_NVIDIA, driver="nvidia")

    cards = enumerate_drm_cards(fake.root)
    assert cards[0].vendor_name == "NVIDIA"
    assert cards[0].driver == "nvidia"


def test_enumerate_drm_marks_igpu_class(tmp_path: Path):
    fake = _FakeDRMRoot(tmp_path)
    # Display controller class → iGPU
    fake.add_card("card0", VENDOR_AMD, pci_class=0x038000)

    cards = enumerate_drm_cards(fake.root)
    assert cards[0].is_integrated is True


def test_enumerate_drm_marks_discrete_vga_class(tmp_path: Path):
    fake = _FakeDRMRoot(tmp_path)
    # VGA compatible controller class → discrete
    fake.add_card("card0", VENDOR_NVIDIA, pci_class=0x030000, driver="nvidia")

    cards = enumerate_drm_cards(fake.root)
    assert cards[0].is_integrated is False


def test_enumerate_drm_multiple_cards(tmp_path: Path):
    fake = _FakeDRMRoot(tmp_path)
    fake.add_card("card0", VENDOR_NVIDIA, driver="nvidia", pci_class=0x030000)
    fake.add_card("card1", VENDOR_AMD,    driver="amdgpu", pci_class=0x038000)
    fake.add_connector("card0-DP-1")
    fake.add_connector("card1-HDMI-A-1")

    cards = enumerate_drm_cards(fake.root)

    assert len(cards) == 2
    names = {c.card_name for c in cards}
    assert names == {"card0", "card1"}


# ── AMD sysfs provider ───────────────────────────────────────────────────────

from backend.platform.linux.amd_sysfs_provider import (
    STATUS_SHARED_MEMORY,
    _MIN_DEDICATED_VRAM_BYTES,
    collect_amd_sysfs,
)


def _make_amd_card(tmp_path: Path, card_name: str = "card0") -> tuple[DRMCard, Path]:
    device_dir = tmp_path / card_name / "device"
    device_dir.mkdir(parents=True)
    card = DRMCard(
        card_name=card_name,
        drm_path=tmp_path / card_name,
        device_path=device_dir,
        pci_address="0000:00:08.1",
        vendor_id=VENDOR_AMD,
        device_id=0x1636,
        vendor_name="AMD",
        driver="amdgpu",
        is_integrated=True,
    )
    return card, device_dir


def test_amd_sysfs_reports_discrete_vram(tmp_path: Path):
    from backend.platform.linux.amd_sysfs_provider import _collect_card_metrics

    card, device = _make_amd_card(tmp_path)
    card = DRMCard(**{**card.__dict__, "is_integrated": False})

    vram_total = 4 * 1024 * 1024 * 1024  # 4 GiB
    vram_used  = 512 * 1024 * 1024        # 512 MiB

    (device / "gpu_busy_percent").write_text("42\n")
    (device / "mem_info_vram_total").write_text(str(vram_total))
    (device / "mem_info_vram_used").write_text(str(vram_used))

    with patch("backend.platform.linux.amd_sysfs_provider._resolve_gpu_name", return_value="AMD RX 6600"):
        metrics = _collect_card_metrics(card, 0)

    assert metrics["gpu_util"] == 42
    assert metrics["mem_total_mb"] == 4096
    assert metrics["mem_used_mb"] == 512
    assert "metricStatus" not in metrics or metrics.get("metricStatus", {}).get("memTotalMB") != STATUS_SHARED_MEMORY


def test_amd_sysfs_igpu_no_fake_vram(tmp_path: Path):
    from backend.platform.linux.amd_sysfs_provider import _collect_card_metrics

    card, device = _make_amd_card(tmp_path)
    # iGPU: vram_total below threshold (e.g., 0 or a tiny BIOS reservation)
    (device / "mem_info_vram_total").write_text("0")
    (device / "mem_info_vram_used").write_text("0")
    (device / "gpu_busy_percent").write_text("5\n")

    with patch("backend.platform.linux.amd_sysfs_provider._resolve_gpu_name", return_value="AMD Radeon"):
        metrics = _collect_card_metrics(card, 0)

    # Must not fabricate dedicated VRAM
    assert metrics["mem_total_mb"] is None
    assert metrics["mem_used_mb"] is None
    # Must carry shared_memory status
    assert metrics["metricStatus"]["memTotalMB"] == STATUS_SHARED_MEMORY
    assert metrics["metricStatus"]["memUsedMB"] == STATUS_SHARED_MEMORY
    assert metrics["metricStatus"]["memPercent"] == STATUS_SHARED_MEMORY


def test_amd_sysfs_igpu_small_bios_reservation_no_fake_vram(tmp_path: Path):
    from backend.platform.linux.amd_sysfs_provider import _collect_card_metrics

    card, device = _make_amd_card(tmp_path)
    # 16 MiB BIOS framebuffer — below threshold → treat as shared
    (device / "mem_info_vram_total").write_text(str(16 * 1024 * 1024))
    (device / "mem_info_vram_used").write_text(str(4 * 1024 * 1024))

    with patch("backend.platform.linux.amd_sysfs_provider._resolve_gpu_name", return_value="AMD Renoir"):
        metrics = _collect_card_metrics(card, 0)

    assert metrics["mem_total_mb"] is None
    assert metrics["metricStatus"]["memTotalMB"] == STATUS_SHARED_MEMORY


def test_amd_sysfs_hwmon_temperature(tmp_path: Path):
    from backend.platform.linux.amd_sysfs_provider import _collect_card_metrics

    card, device = _make_amd_card(tmp_path)
    hwmon_dir = device / "hwmon" / "hwmon0"
    hwmon_dir.mkdir(parents=True)
    (hwmon_dir / "temp1_input").write_text("55000\n")  # 55 000 milli-°C = 55 °C

    with patch("backend.platform.linux.amd_sysfs_provider._resolve_gpu_name", return_value="AMD GPU"):
        metrics = _collect_card_metrics(card, 0)

    assert metrics["temp_c"] == 55


def test_amd_sysfs_hwmon_power(tmp_path: Path):
    from backend.platform.linux.amd_sysfs_provider import _collect_card_metrics

    card, device = _make_amd_card(tmp_path)
    hwmon_dir = device / "hwmon" / "hwmon0"
    hwmon_dir.mkdir(parents=True)
    (hwmon_dir / "power1_average").write_text("15000000\n")  # 15 W in µW

    with patch("backend.platform.linux.amd_sysfs_provider._resolve_gpu_name", return_value="AMD GPU"):
        metrics = _collect_card_metrics(card, 0)

    assert metrics["power_draw_w"] == 15.0


def test_amd_sysfs_hwmon_fan(tmp_path: Path):
    from backend.platform.linux.amd_sysfs_provider import _collect_card_metrics

    card, device = _make_amd_card(tmp_path)
    hwmon_dir = device / "hwmon" / "hwmon0"
    hwmon_dir.mkdir(parents=True)
    (hwmon_dir / "pwm1").write_text("128\n")       # ~50 %
    (hwmon_dir / "fan1_input").write_text("1500\n") # 1500 RPM

    with patch("backend.platform.linux.amd_sysfs_provider._resolve_gpu_name", return_value="AMD GPU"):
        metrics = _collect_card_metrics(card, 0)

    assert metrics["fan_speed_pct"] == round(128 * 100 / 255)
    assert metrics["fan_rpm"] == 1500


def test_amd_sysfs_missing_hwmon_no_crash(tmp_path: Path):
    from backend.platform.linux.amd_sysfs_provider import _collect_card_metrics

    card, device = _make_amd_card(tmp_path)
    # No hwmon directory at all

    with patch("backend.platform.linux.amd_sysfs_provider._resolve_gpu_name", return_value="AMD GPU"):
        metrics = _collect_card_metrics(card, 0)

    # Fields are absent — not fake zeros
    assert metrics.get("temp_c") is None
    assert metrics.get("power_draw_w") is None
    assert metrics.get("fan_speed_pct") is None


def test_collect_amd_sysfs_returns_empty_when_no_amd_cards(tmp_path: Path):
    with patch(
        "backend.platform.linux.amd_sysfs_provider.enumerate_drm_cards",
        return_value=[],
    ):
        result = collect_amd_sysfs()
    assert result == []


def test_collect_amd_sysfs_skips_non_amdgpu_driver(tmp_path: Path):
    card, _ = _make_amd_card(tmp_path)
    # Same vendor ID but different driver (e.g., radeon)
    card = DRMCard(**{**card.__dict__, "driver": "radeon"})

    with patch(
        "backend.platform.linux.amd_sysfs_provider.enumerate_drm_cards",
        return_value=[card],
    ):
        result = collect_amd_sysfs()

    assert result == []


# ── Normalization integration ─────────────────────────────────────────────────

from backend.platform.linux.gpu_normalization import (
    STATUS_OK,
    STATUS_UNAVAILABLE,
    STATUS_UNSUPPORTED,
    normalise_gpu,
)


def test_normalise_gpu_amd_sysfs_provider_is_ok():
    gpu = normalise_gpu({
        "id": 0,
        "name": "AMD Radeon RX 6600",
        "vendor": "AMD",
        "provider": "amdgpu-sysfs",
        "gpu_util": 30,
        "temp_c": 60,
        "mem_total_mb": 8192,
        "mem_used_mb": 2048,
        "driver_version": "6.7.0",
    })

    assert gpu["providerStatus"] == STATUS_OK
    assert gpu["usage"] == 30
    assert gpu["tempC"] == 60
    assert gpu["memTotalMB"] == 8192
    assert gpu["memUsedMB"] == 2048
    assert gpu["memPercent"] == 25.0
    assert gpu["driverVersion"] == "6.7.0"
    assert gpu["metricStatus"]["usage"] == STATUS_OK
    assert gpu["metricStatus"]["tempC"] == STATUS_OK


def test_normalise_gpu_fan_rpm_key_mapped():
    gpu = normalise_gpu({
        "id": 0,
        "name": "AMD RX 7900 XTX",
        "vendor": "AMD",
        "provider": "amdgpu-sysfs",
        "fan_rpm": 1800,
        "fan_speed_pct": 45,
    })

    assert gpu["fanRPM"] == 1800
    assert gpu["fanPercent"] == 45
    assert gpu["metricStatus"]["fanRPM"] == STATUS_OK
    assert gpu["metricStatus"]["fanPercent"] == STATUS_OK


def test_normalise_gpu_shared_memory_status_preserved():
    """shared_memory status pre-set by AMD sysfs provider must survive normalise_gpu."""
    gpu = normalise_gpu({
        "id": 0,
        "name": "AMD Radeon 680M",
        "vendor": "AMD",
        "provider": "amdgpu-sysfs",
        "gpu_util": 10,
        "mem_total_mb": None,
        "mem_used_mb": None,
        "metricStatus": {
            "memTotalMB":  "shared_memory",
            "memUsedMB":   "shared_memory",
            "memPercent":  "shared_memory",
            "memFreeMB":   "shared_memory",
        },
        "metricMessages": {
            "memTotalMB": "Shared memory — no dedicated VRAM on this integrated GPU",
        },
    })

    assert gpu["metricStatus"]["memTotalMB"] == "shared_memory"
    assert gpu["metricStatus"]["memUsedMB"] == "shared_memory"
    assert gpu["metricStatus"]["memPercent"] == "shared_memory"
    # memPercent must NOT be computed as 0.0 when shared_memory
    assert gpu.get("memPercent") is None
    assert "Shared memory" in gpu["metricMessages"].get("memTotalMB", "")


def test_normalise_gpu_amd_encoder_unsupported():
    """Encoder/decoder util must be unsupported for non-NVIDIA on Linux."""
    gpu = normalise_gpu({
        "id": 0,
        "name": "AMD GPU",
        "vendor": "AMD",
        "provider": "amdgpu-sysfs",
    })

    assert gpu["metricStatus"]["encoderUtil"] == STATUS_UNSUPPORTED
    assert gpu["metricStatus"]["decoderUtil"] == STATUS_UNSUPPORTED


# ── Windows normalization regression guards ───────────────────────────────────

def test_windows_style_payload_normalizes_unchanged():
    """
    Simulate what a Windows worker would emit and ensure normalise_gpu still
    produces correct camelCase output.  This guards against regressions in
    shared normalization logic.
    """
    gpu = normalise_gpu({
        "id": 0,
        "name": "RTX 3080",
        "vendor": "NVIDIA",
        "provider": "nvml",
        "gpu_util": 75,
        "temp_c": 72,
        "mem_used_mb": 5120,
        "mem_total_mb": 10240,
        "power_draw_w": 280.5,
        "power_limit_w": 320.0,
        "fan_speed_pct": 65,
        "clock_core_mhz": 1800,
        "clock_mem_mhz": 9000,
        "driver_version": "535.86.05",
    })

    assert gpu["usage"] == 75
    assert gpu["tempC"] == 72
    assert gpu["memUsedMB"] == 5120
    assert gpu["memTotalMB"] == 10240
    assert gpu["memPercent"] == 50.0
    assert gpu["powerW"] == 280.5
    assert gpu["powerLimitW"] == 320.0
    assert gpu["powerPercent"] == pytest.approx(280.5 / 320.0 * 100.0, abs=0.1)
    assert gpu["fanPercent"] == 65
    assert gpu["clockMHz"] == 1800
    assert gpu["clockMemMHz"] == 9000
    assert gpu["driverVersion"] == "535.86.05"
    assert gpu["providerStatus"] == STATUS_OK
    # NVIDIA encoder/decoder should default to not_exposed (not unsupported)
    assert gpu["metricStatus"]["encoderUtil"] == "not_exposed"


def test_lspci_provider_still_marks_unsupported():
    """lspci-detected GPU must still have providerStatus=unsupported."""
    gpu = normalise_gpu({
        "id": 0,
        "name": "AMD Radeon [lspci]",
        "vendor": "AMD",
        "provider": "lspci",
    })

    assert gpu["providerStatus"] == STATUS_UNSUPPORTED
    assert gpu["metricStatus"]["usage"] == STATUS_UNSUPPORTED


def test_shared_memory_does_not_leak_into_nvidia_payload():
    """shared_memory status must never appear for an NVIDIA card."""
    gpu = normalise_gpu({
        "id": 0,
        "name": "RTX 4090",
        "vendor": "NVIDIA",
        "provider": "nvml",
        "mem_total_mb": 24576,
        "mem_used_mb": 4096,
    })

    for metric, status in gpu["metricStatus"].items():
        assert status != "shared_memory", (
            f"shared_memory leaked into NVIDIA metric: {metric}"
        )
