"""Configuration management for Sentinel."""

import copy
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from backend.platform.paths import get_app_paths

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
        self.paths = get_app_paths()
        self.app_data_dir = self.paths.config_dir
        self.config_file = self.paths.config_dir / "settings.json"
        self.backup_file = self.paths.config_dir / "settings.backup.json"
        self.logs_dir = self.paths.log_dir

        # Create directories
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Load or initialize config
        self._config = self._load_or_initialize()

    @staticmethod
    def _get_app_data_dir() -> Path:
        """Get platform-appropriate app data directory."""
        return get_app_paths().config_dir

    def _candidate_config_files(self) -> tuple[Path, ...]:
        """Return primary and legacy config file locations.

        ``self.config_file`` is always first so that test code (or any caller)
        can override the path after construction and have ``_load_or_initialize``
        pick up the override.
        """
        primary = self.config_file
        rest = tuple(p for p in self.paths.config_candidates("settings.json") if p != primary)
        return (primary, *rest)

    def _load_or_initialize(self) -> dict[str, Any]:
        """Load config from file or create with defaults."""
        for candidate in self._candidate_config_files():
            if not candidate.exists():
                continue
            try:
                with open(candidate, encoding="utf-8") as f:
                    config = json.load(f)
                logger.info("Loaded config from %s", candidate)
                # Merge with defaults to ensure all keys present
                return self._merge_defaults(config)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(
                    "Failed to load config from %s: %s. Trying fallback locations.",
                    candidate,
                    e,
                )

        if self.backup_file.exists():
            try:
                with open(self.backup_file, encoding="utf-8") as f:
                    config = json.load(f)
                logger.info("Restored config from backup: %s", self.backup_file)
                return self._merge_defaults(config)
            except (OSError, json.JSONDecodeError):
                logger.warning("Backup config at %s is not readable", self.backup_file)
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
            logger.exception("Failed to save configuration: %s", e)
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
            logger.exception("Failed to export configuration: %s", e)
            raise


# Global singleton instance
_config_instance: Config | None = None


def get_config() -> Config:
    """Get or create the global config instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
