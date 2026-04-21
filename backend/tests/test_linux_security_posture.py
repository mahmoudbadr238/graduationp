"""Tests for Linux security posture collection and mapping."""

from __future__ import annotations

import shutil

import pytest

from backend.platform.linux.security_posture import (
    CommandResult,
    compose_security_info,
    detect_firewall,
    detect_package_updates,
)


def test_detect_firewall_prefers_active_ufw():
    def runner(args, timeout=5):  # noqa: ARG001
        if args == ["ufw", "status", "verbose"]:
            return CommandResult(
                args=tuple(args),
                returncode=0,
                stdout="Status: active\nDefault: deny (incoming), allow (outgoing)\n",
            )
        return CommandResult(args=tuple(args), returncode=None, not_found=True, error="not_found")

    firewall, providers = detect_firewall(runner)

    assert firewall["enabled"] is True
    assert firewall["status"] == "Enabled"
    assert providers[0]["name"] == "ufw"


def test_detect_package_updates_maps_apt_pending(monkeypatch):
    real_which = shutil.which

    def fake_which(name: str):
        if name == "apt":
            return "/usr/bin/apt"
        return None

    monkeypatch.setattr(shutil, "which", fake_which)

    def runner(args, timeout=5):  # noqa: ARG001
        assert args == ["apt", "list", "--upgradable"]
        return CommandResult(
            args=tuple(args),
            returncode=0,
            stdout="Listing...\nopenssl/stable 1\nglibc/stable 2\n",
        )

    updates, providers = detect_package_updates(runner)

    assert updates["manager"] == "apt"
    assert updates["pending_count"] == 2
    assert updates["ui_status"] == "PendingUpdates"
    assert providers[0]["detail"] == "2 upgradable packages"
    monkeypatch.setattr(shutil, "which", real_which)


def test_compose_security_info_linux_summary_uses_platform_native_statuses():
    detections = {
        "firewall": {"enabled": True, "name": "UFW", "status": "Enabled", "detail": "UFW active", "level": "good"},
        "antivirus": {"installed": True, "realtime": False, "name": "ClamAV", "status": "Scanner only", "detail": "Daemon inactive", "level": "warning"},
        "updates": {"manager": "apt", "pending_count": 0, "status": "Up to date", "detail": "No pending package updates detected.", "level": "good", "ui_status": "UpToDate"},
        "secure_boot": {"enabled": True, "status": "Enabled", "detail": "Detected from EFI variable.", "level": "good"},
        "disk_encryption": {"enabled": True, "status": "Enabled", "detail": "Encrypted backing device detected for /.", "level": "good"},
        "remote_access": {"enabled": True, "status": "Exposed", "detail": "Remote administration surface is exposed (services: SSH).", "level": "warning", "services": ["SSH"], "ports": [22]},
        "mandatory_access_control": {"apparmor": "Enabled", "selinux": "Disabled", "status": "Active", "detail": "Mandatory access control is active.", "level": "good"},
    }

    info = compose_security_info(
        detections,
        is_admin=False,
        os_name="Ubuntu 24.04",
        kernel="6.8.0",
        uptime="3 days",
        providers=[{"name": "ufw", "status": "ok", "detail": "UFW is active"}],
    )

    assert info["antivirus"] == "Scanner only"
    assert info["windowsUpdateStatus"] == "UpToDate"
    assert info["simplified"]["overall"]["status"] == "Needs attention"
    assert info["simplified"]["remoteAndApps"]["status"] == "Exposed"
    assert info["simplified"]["raw"]["linuxUpdateManager"] == "apt"
    assert info["simplified"]["raw"]["linuxRemoteServices"] == ["SSH"]
