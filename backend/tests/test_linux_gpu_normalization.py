"""Tests for Linux GPU metric normalization."""

from __future__ import annotations

from backend.platform.linux.gpu_normalization import (
    STATUS_OK,
    STATUS_UNAVAILABLE,
    STATUS_UNSUPPORTED,
    normalise_gpu,
    parse_numeric,
)


def test_parse_numeric_handles_missing_tokens():
    assert parse_numeric("N/A") is None
    assert parse_numeric("--") is None
    assert parse_numeric("42") == 42
    assert parse_numeric("13.5") == 13.5


def test_normalise_gpu_preserves_missing_metrics_without_fake_zeros():
    gpu = normalise_gpu(
        {
            "id": 0,
            "name": "RTX 4070",
            "vendor": "NVIDIA",
            "provider": "nvidia-smi",
            "gpu_util": "12",
            "temp_c": None,
            "mem_used_mb": 1024,
            "mem_total_mb": 4096,
            "power_draw_w": None,
        }
    )

    assert gpu["usage"] == 12
    assert gpu["tempC"] is None
    assert gpu["powerW"] is None
    assert gpu["memPercent"] == 25.0
    assert gpu["metricStatus"]["usage"] == STATUS_OK
    assert gpu["metricStatus"]["tempC"] == STATUS_UNAVAILABLE
    assert gpu["metricStatus"]["powerW"] == STATUS_UNAVAILABLE


def test_normalise_gpu_marks_lspci_detection_as_unsupported():
    gpu = normalise_gpu(
        {
            "id": 1,
            "name": "Intel UHD Graphics",
            "vendor": "Intel",
            "provider": "lspci",
        }
    )

    assert gpu["providerStatus"] == STATUS_UNSUPPORTED
    assert gpu["usage"] is None
    assert gpu["metricStatus"]["usage"] == STATUS_UNSUPPORTED
    assert gpu["metricStatus"]["encoderUtil"] == STATUS_UNSUPPORTED

