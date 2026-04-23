"""Tests for cross-platform Sentinel runtime path selection."""

from __future__ import annotations

import sys
from pathlib import Path

from backend.engines.scancenter.export import default_export_dir
from backend.platform import paths as paths_mod


def _clear_paths_cache() -> None:
    paths_mod.get_app_paths.cache_clear()


def test_linux_paths_follow_xdg_directories(tmp_path, monkeypatch):
    home = tmp_path / "home"
    xdg_config = tmp_path / "xdg-config"
    xdg_data = tmp_path / "xdg-data"
    xdg_cache = tmp_path / "xdg-cache"
    xdg_state = tmp_path / "xdg-state"

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(paths_mod.Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data))
    monkeypatch.setenv("XDG_CACHE_HOME", str(xdg_cache))
    monkeypatch.setenv("XDG_STATE_HOME", str(xdg_state))

    _clear_paths_cache()
    app_paths = paths_mod.get_app_paths()

    assert app_paths.config_dir == xdg_config / "sentinel"
    assert app_paths.data_dir == xdg_data / "sentinel"
    assert app_paths.cache_dir == xdg_cache / "sentinel"
    assert app_paths.state_dir == xdg_state / "sentinel"
    assert app_paths.log_dir == xdg_state / "sentinel" / "logs"
    assert app_paths.crash_dir == xdg_state / "sentinel" / "crashes"
    assert app_paths.quarantine_dir == xdg_data / "sentinel" / "quarantine"
    assert app_paths.config_dir.exists()
    assert app_paths.log_dir.exists()


def test_linux_config_candidates_include_legacy_locations(tmp_path, monkeypatch):
    home = tmp_path / "home"

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(paths_mod.Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)

    _clear_paths_cache()
    app_paths = paths_mod.get_app_paths()
    candidates = app_paths.config_candidates("settings.json")

    assert candidates[0] == home / ".config" / "sentinel" / "settings.json"
    assert home / ".config" / "Sentinel" / "settings.json" in candidates
    assert home / ".sentinel" / "settings.json" in candidates


def test_windows_paths_keep_appdata_and_programdata_layout(tmp_path, monkeypatch):
    roaming = tmp_path / "Roaming"
    local = tmp_path / "Local"
    program_data = tmp_path / "ProgramData"

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("PROGRAMDATA", str(program_data))

    _clear_paths_cache()
    app_paths = paths_mod.get_app_paths()

    assert app_paths.config_dir == roaming / "Sentinel"
    assert app_paths.data_dir == roaming / "Sentinel"
    assert app_paths.log_dir == roaming / "Sentinel" / "logs"
    assert app_paths.quarantine_dir == program_data / "Sentinel" / "Quarantine"
    assert app_paths.scan_reports_dir == roaming / "Sentinel" / "scan_reports"
    assert app_paths.quarantine_dir.exists()


def test_resolve_legacy_compatible_data_path_prefers_existing_legacy_db(
    tmp_path, monkeypatch
):
    home = tmp_path / "home"
    legacy_db = home / ".sentinel" / "sentinel.db"
    legacy_db.parent.mkdir(parents=True, exist_ok=True)
    legacy_db.write_text("legacy", encoding="utf-8")

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(paths_mod.Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    _clear_paths_cache()
    resolved = paths_mod.resolve_legacy_compatible_data_path("sentinel.db")

    assert resolved == legacy_db


def test_preferred_data_path_and_default_export_dir_use_platform_data_dir(
    tmp_path, monkeypatch
):
    home = tmp_path / "home"
    xdg_data = tmp_path / "xdg-data"

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(paths_mod.Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data))

    _clear_paths_cache()
    preferred = paths_mod.preferred_data_path("sentinel.db")
    export_dir = default_export_dir("job:123/report")

    assert preferred == xdg_data / "sentinel" / "sentinel.db"
    assert export_dir == xdg_data / "sentinel" / "reports" / "job_123_report"
