"""Cross-platform runtime paths for Sentinel.

This module centralizes platform-specific path selection so services do not
scatter Windows or Linux filesystem assumptions throughout the codebase.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

APP_NAME = "Sentinel"
APP_SLUG = "sentinel"


def _env_path(name: str) -> Path | None:
    value = os.getenv(name)
    if not value:
        return None
    return Path(value).expanduser()


def _xdg_path(env_name: str, fallback: Path) -> Path:
    return _env_path(env_name) or fallback


def _unique_paths(paths: list[Path]) -> tuple[Path, ...]:
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.expanduser()
        if resolved in seen:
            continue
        unique.append(resolved)
        seen.add(resolved)
    return tuple(unique)


@dataclass(frozen=True)
class AppPaths:
    """Resolved Sentinel runtime paths for the current platform."""

    config_dir: Path
    data_dir: Path
    cache_dir: Path
    state_dir: Path
    log_dir: Path
    crash_dir: Path
    quarantine_dir: Path
    nmap_reports_dir: Path
    scan_reports_dir: Path
    sandbox_runs_dir: Path
    sandbox_sessions_dir: Path
    shredder_logs_dir: Path
    legacy_config_dirs: tuple[Path, ...]
    legacy_data_dirs: tuple[Path, ...]

    def ensure(self) -> "AppPaths":
        """Create the directories needed for runtime state."""
        for path in (
            self.config_dir,
            self.data_dir,
            self.cache_dir,
            self.state_dir,
            self.log_dir,
            self.crash_dir,
            self.quarantine_dir,
            self.nmap_reports_dir,
            self.scan_reports_dir,
            self.sandbox_runs_dir,
            self.sandbox_sessions_dir,
            self.shredder_logs_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        return self

    def config_candidates(self, filename: str) -> tuple[Path, ...]:
        """Return the primary and legacy config file candidates."""
        return _unique_paths(
            [self.config_dir / filename, *[path / filename for path in self.legacy_config_dirs]]
        )

    def data_candidates(self, relative_path: str) -> tuple[Path, ...]:
        """Return the primary and legacy data file candidates."""
        return _unique_paths(
            [self.data_dir / relative_path, *[path / relative_path for path in self.legacy_data_dirs]]
        )


def _windows_paths() -> AppPaths:
    home = Path.home()
    roaming = _env_path("APPDATA") or home / "AppData" / "Roaming"
    local = _env_path("LOCALAPPDATA") or home / "AppData" / "Local"
    program_data = _env_path("PROGRAMDATA") or local

    root = roaming / APP_NAME
    legacy_roots = _unique_paths([root, local / APP_NAME])

    return AppPaths(
        config_dir=root,
        data_dir=root,
        cache_dir=local / APP_NAME / "cache",
        state_dir=root,
        log_dir=root / "logs",
        crash_dir=root / "crashes",
        quarantine_dir=program_data / APP_NAME / "Quarantine",
        nmap_reports_dir=root / "nmap_reports",
        scan_reports_dir=root / "scan_reports",
        sandbox_runs_dir=root / "sandbox_runs",
        sandbox_sessions_dir=root / "sandbox_sessions",
        shredder_logs_dir=root / "logs" / "shredder",
        legacy_config_dirs=legacy_roots,
        legacy_data_dirs=legacy_roots,
    )


def _linux_paths() -> AppPaths:
    home = Path.home()
    config_root = _env_path("SENTINEL_CONFIG_DIR") or (
        _xdg_path("XDG_CONFIG_HOME", home / ".config") / APP_SLUG
    )
    data_root = _env_path("SENTINEL_DATA_DIR") or (
        _xdg_path("XDG_DATA_HOME", home / ".local" / "share") / APP_SLUG
    )
    cache_root = _env_path("SENTINEL_CACHE_DIR") or (
        _xdg_path("XDG_CACHE_HOME", home / ".cache") / APP_SLUG
    )
    state_root = _env_path("SENTINEL_STATE_DIR") or (
        _xdg_path("XDG_STATE_HOME", home / ".local" / "state") / APP_SLUG
    )
    log_root = _env_path("SENTINEL_LOG_DIR") or state_root / "logs"
    crash_root = _env_path("SENTINEL_CRASH_DIR") or state_root / "crashes"

    legacy_config_dirs = _unique_paths(
        [
            home / ".config" / APP_NAME,
            home / ".config" / APP_SLUG,
            home / f".{APP_SLUG}",
        ]
    )
    legacy_data_dirs = _unique_paths(
        [
            home / ".local" / "share" / APP_NAME,
            home / ".local" / "share" / APP_SLUG,
            home / f".{APP_SLUG}",
            home / ".config" / APP_NAME,
        ]
    )

    return AppPaths(
        config_dir=config_root,
        data_dir=data_root,
        cache_dir=cache_root,
        state_dir=state_root,
        log_dir=log_root,
        crash_dir=crash_root,
        quarantine_dir=_env_path("SENTINEL_QUARANTINE_DIR") or data_root / "quarantine",
        nmap_reports_dir=data_root / "nmap_reports",
        scan_reports_dir=data_root / "scan_reports",
        sandbox_runs_dir=data_root / "sandbox_runs",
        sandbox_sessions_dir=state_root / "sandbox_sessions",
        shredder_logs_dir=log_root / "shredder",
        legacy_config_dirs=legacy_config_dirs,
        legacy_data_dirs=legacy_data_dirs,
    )


def _generic_paths() -> AppPaths:
    home = Path.home()
    root = home / f".{APP_SLUG}"
    return AppPaths(
        config_dir=root / "config",
        data_dir=root / "data",
        cache_dir=root / "cache",
        state_dir=root / "state",
        log_dir=root / "logs",
        crash_dir=root / "crashes",
        quarantine_dir=root / "quarantine",
        nmap_reports_dir=root / "nmap_reports",
        scan_reports_dir=root / "scan_reports",
        sandbox_runs_dir=root / "sandbox_runs",
        sandbox_sessions_dir=root / "sandbox_sessions",
        shredder_logs_dir=root / "logs" / "shredder",
        legacy_config_dirs=(root,),
        legacy_data_dirs=(root,),
    )


@lru_cache(maxsize=1)
def get_app_paths() -> AppPaths:
    """Return the current platform's Sentinel runtime paths."""
    if sys.platform == "win32":
        return _windows_paths().ensure()
    if sys.platform.startswith("linux"):
        return _linux_paths().ensure()
    return _generic_paths().ensure()


def preferred_data_path(relative_path: str) -> Path:
    """Return the canonical writable data path for *relative_path*."""
    path = get_app_paths().data_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def resolve_legacy_compatible_data_path(relative_path: str) -> Path:
    """Return an existing data path or the canonical writable path.

    This preserves access to older locations such as ``~/.sentinel`` while new
    installs use the platform-native data directory from ``get_app_paths()``.
    """
    candidates = get_app_paths().data_candidates(relative_path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return preferred_data_path(relative_path)
