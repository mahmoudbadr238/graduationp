"""Configuration management for Sentinel.

Handles app data storage, settings persistence, and safe load/save with backups.
Platform-aware paths: %APPDATA%/Sentinel (Windows) or ~/.local/share/sentinel (Linux).
"""

import copy
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Config:
    """Configuration manager with auto-backup and safe persistence."""

    # Default configuration schema
    DEFAULTS = {
        "sampling_rates": {
            "cpu_interval_ms": 1000,
            "memory_interval_ms": 1000,
            "gpu_interval_ms": 2000,
            "network_interval_ms": 2000,
        },
        "feature_toggles": {
            "enable_gpu_monitoring": True,
            "enable_network_scanner": False,  # Requires nmap
            "enable_virustotal": False,  # Requires API key
            "enable_crash_reporting": False,  # Requires SENTRY_DSN
        },
        "ui": {
            "theme": "dark",
            "window_width": 1400,
            "window_height": 900,
        },
    }

    def __init__(self):
        """Initialize configuration manager."""
        self.app_data_dir = self._get_app_data_dir()
        self.config_file = self.app_data_dir / "settings.json"
        self.backup_file = self.app_data_dir / "settings.backup.json"
        self.logs_dir = self.app_data_dir / "logs"

        # Create directories
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Load or initialize config
        self._config = self._load_or_initialize()

    @staticmethod
    def _get_app_data_dir() -> Path:
        """Get platform-specific app data directory."""
        if sys.platform == "win32":
            appdata = os.getenv("APPDATA")
            if appdata:
                return Path(appdata) / "Sentinel"
            # Fallback to local
            return Path.home() / "AppData" / "Roaming" / "Sentinel"
        # Linux, macOS
        data_home = os.getenv("XDG_DATA_HOME")
        if data_home:
            return Path(data_home) / "sentinel"
        return Path.home() / ".local" / "share" / "sentinel"

    def _load_or_initialize(self) -> dict[str, Any]:
        """Load config from file or create with defaults."""
        if self.config_file.exists():
            try:
                with open(self.config_file, encoding="utf-8") as f:
                    config = json.load(f)
                logger.info(f"Loaded config from {self.config_file}")
                # Merge with defaults to ensure all keys present
                return self._merge_defaults(config)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to load config: {e}. Using backup or defaults.")
                if self.backup_file.exists():
                    try:
                        with open(self.backup_file, encoding="utf-8") as f:
                            config = json.load(f)
                        logger.info("Restored config from backup")
                        return self._merge_defaults(config)
                    except (OSError, json.JSONDecodeError):
                        pass
        # Use defaults
        logger.info("Using default configuration")
        return copy.deepcopy(self.DEFAULTS)

    @staticmethod
    def _merge_defaults(config: dict[str, Any]) -> dict[str, Any]:
        """Merge loaded config with defaults, ensuring all keys present."""
        merged = copy.deepcopy(Config.DEFAULTS)
        for key, value in config.items():
            if isinstance(value, dict) and key in merged:
                merged[key].update(value)
            else:
                merged[key] = value
        return merged

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot notation (e.g., 'feature_toggles.enable_gpu_monitoring')."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """Set configuration value by dot notation."""
        keys = key.split(".")
        target = self._config
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    def save(self) -> None:
        """Save configuration to file with automatic backup."""
        try:
            # Create backup of existing config
            if self.config_file.exists():
                shutil.copy2(self.config_file, self.backup_file)

            # Write new config
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info(f"Configuration saved to {self.config_file}")
        except OSError as e:
            logger.exception(f"Failed to save configuration: {e}")
            raise

    def reset(self) -> None:
        """Reset configuration to defaults."""
        self._config = copy.deepcopy(self.DEFAULTS)
        self.save()
        logger.info("Configuration reset to defaults")

    def export_json(self, path: str | Path) -> None:
        """Export current configuration to a JSON file."""
        path = Path(path)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info(f"Configuration exported to {path}")
        except OSError as e:
            logger.exception(f"Failed to export configuration: {e}")
            raise


# Global singleton instance
_config_instance: Config | None = None


def get_config() -> Config:
    """Get or create the global config instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
