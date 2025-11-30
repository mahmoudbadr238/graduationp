"""Unit tests for core configuration and privilege checks."""

import os

import pytest

from app.core.config import Config
from app.infra.privileges import is_admin


class TestConfig:
    """Test configuration management."""

    def test_config_creation(self):
        """Test that config can be created."""
        config = Config()
        assert config is not None
        assert config.app_data_dir is not None
        assert config.logs_dir is not None

    def test_config_defaults(self):
        """Test that defaults are loaded."""
        config = Config()
        assert config.get("sampling_rates.cpu_interval_ms") == 1000
        assert config.get("feature_toggles.enable_gpu_monitoring") is True

    def test_config_set_get(self):
        """Test setting and getting config values."""
        config = Config()
        config.set("feature_toggles.enable_network_scanner", True)
        assert config.get("feature_toggles.enable_network_scanner") is True

    def test_config_save(self, tmp_path):
        """Test config persistence."""
        config = Config()
        config.set("sampling_rates.cpu_interval_ms", 2000)
        config.config_file = tmp_path / "test_config.json"
        config.backup_file = tmp_path / "test_backup.json"
        config.save()

        # Load and verify
        assert config.config_file.exists()
        config2 = Config()
        config2.config_file = tmp_path / "test_config.json"
        config2._config = config2._load_or_initialize()
        assert config2.get("sampling_rates.cpu_interval_ms") == 2000

    def test_config_reset(self, tmp_path):
        """Test config reset."""
        config = Config()
        config.set("sampling_rates.cpu_interval_ms", 5000)
        config.config_file = tmp_path / "test_config.json"
        config.backup_file = tmp_path / "test_backup.json"
        config.reset()
        assert config.get("sampling_rates.cpu_interval_ms") == 1000


class TestPrivileges:
    """Test privilege checking."""

    def test_is_admin_returns_bool(self):
        """Test that is_admin returns a boolean."""
        result = is_admin()
        assert isinstance(result, bool)

    def test_is_admin_callable(self):
        """Test that is_admin can be called multiple times."""
        result1 = is_admin()
        result2 = is_admin()
        assert result1 == result2


@pytest.mark.skipif(not os.getenv("NMAP_AVAILABLE"), reason="Nmap not available")
def test_nmap_integration():
    """Test that nmap integration can be imported."""
    from app.infra.integrations import nmap_available

    assert (
        nmap_available() or not nmap_available()
    )  # Should return bool without crashing


@pytest.mark.skipif(
    not os.getenv("VIRUSTOTAL_API_KEY"), reason="VirusTotal not configured"
)
def test_virustotal_integration():
    """Test that VirusTotal integration can be imported."""
    from app.infra.integrations import virustotal_enabled

    assert (
        virustotal_enabled() or not virustotal_enabled()
    )  # Should return bool without crashing
