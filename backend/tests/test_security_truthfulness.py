"""Focused truthfulness tests for security posture, ClamAV, and RTP."""

from __future__ import annotations

import builtins
from pathlib import Path
from types import SimpleNamespace

import backend.api.system_snapshot_service as snapshot_module
from backend.api.system_snapshot_service import SystemSnapshotService
from backend.platform.linux.security_posture import compose_security_info
from backend.core.realtime_protection import _probe_rtp_capability
from backend.infra.integrations import get_clamav_status
from backend.utils.security_info import SecurityInfo


def test_clamav_status_uses_windows_fallback_path() -> None:
    status = get_clamav_status(
        which=lambda _name: None,
        path_exists=lambda path: path.endswith(r"ClamAV\clamscan.exe"),
        is_windows=True,
    )

    assert status["available"] is True
    assert status["status"] == "scanner_available"
    assert status["scannerPath"].endswith("clamscan.exe")


def test_clamav_status_reports_active_daemon_on_linux() -> None:
    def runner(args: list[str]) -> SimpleNamespace:
        return SimpleNamespace(returncode=0 if args == ["pgrep", "-x", "clamd"] else 1)

    status = get_clamav_status(
        which=lambda name: "/usr/bin/clamscan" if name == "clamscan" else None,
        runner=runner,
        is_windows=False,
    )

    assert status["available"] is True
    assert status["status"] == "daemon_available"


def test_smartscreen_unknown_when_probe_returns_nothing(monkeypatch) -> None:
    monkeypatch.setattr(
        SecurityInfo,
        "_run_powershell",
        staticmethod(lambda *_args, **_kwargs: None),
    )

    status = SecurityInfo.get_smartscreen_status()

    assert status["status"] == "Unknown"
    assert status["enabled"] is None


def test_disk_encryption_unknown_without_admin_when_registry_probe_is_empty(monkeypatch) -> None:
    monkeypatch.setattr(
        SecurityInfo,
        "_run_powershell",
        staticmethod(lambda *_args, **_kwargs: None),
    )
    monkeypatch.setattr(SecurityInfo, "_check_admin", staticmethod(lambda: False))

    status = SecurityInfo.get_disk_encryption_status()

    assert status["status"] == "Unknown"
    assert status["enabled"] is None


def test_refresh_security_info_clears_windows_security_cache(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        SecurityInfo,
        "clear_cache",
        staticmethod(lambda: calls.append("clear")),
    )

    service = SystemSnapshotService.__new__(SystemSnapshotService)
    service._update_security_info = lambda: calls.append("update")

    SystemSnapshotService.refreshSecurityInfo(service)

    assert calls == ["clear", "update"]


def test_system_snapshot_service_preserves_unknown_extended_windows_security_fields(monkeypatch) -> None:
    captured: list[dict] = []

    monkeypatch.setattr(snapshot_module.sys, "platform", "win32")
    monkeypatch.setattr(
        snapshot_module.platform,
        "system",
        lambda: "Windows",
    )
    monkeypatch.setattr(
        snapshot_module.platform,
        "release",
        lambda: "11",
    )
    monkeypatch.setattr(
        snapshot_module.platform,
        "version",
        lambda: "build",
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_all_security_status",
        staticmethod(lambda: {"firewall": {"enabled": True, "name": "WF", "status": "Enabled"}, "antivirus": {"enabled": True, "name": "Defender", "status": "enabled", "realtime_protection": True}}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_tpm_status",
        staticmethod(lambda: {"present": None, "enabled": None, "version": "Unknown"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_extended_security_status",
        staticmethod(
            lambda: {
                "diskEncryption": {"enabled": None, "status": "Unknown", "detail": "Unable to determine"},
                "windowsUpdate": {"status": "UpToDate", "lastInstallDate": "", "detail": "Current"},
                "remoteDesktop": {"enabled": None, "nlaEnabled": None, "status": "Unknown", "detail": "Unable to determine"},
                "adminAccounts": {"count": None, "status": "Unknown", "detail": "Unable to determine"},
                "uacLevel": {"level": "Unknown", "status": "Unknown", "detail": "Unable to determine"},
                "smartScreen": {"enabled": None, "status": "Unknown", "detail": "Unable to determine"},
                "memoryIntegrity": {"enabled": None, "status": "Unknown", "detail": "Unable to determine"},
            }
        ),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_simplified_security_status",
        staticmethod(lambda: {"overall": {}, "raw": {}}),
    )

    service = SystemSnapshotService.__new__(SystemSnapshotService)
    service._get_system_uptime = lambda: "1d"
    service._securityInfoReadyInternal = SimpleNamespace(
        emit=lambda payload: captured.append(payload)
    )

    SystemSnapshotService._do_update_security_info(service)

    assert captured
    info = captured[0]
    assert info["tpmPresent"] == "Unknown"
    assert info["tpmEnabled"] is None
    assert info["remoteDesktopEnabled"] is None
    assert info["remoteDesktopNla"] is None
    assert info["adminAccountCount"] is None
    assert info["smartScreenEnabled"] is None
    assert info["memoryIntegrityEnabled"] is None


def test_simplified_windows_status_preserves_unknown_states(monkeypatch) -> None:
    monkeypatch.setattr(SecurityInfo, "_cache", {})
    monkeypatch.setattr(SecurityInfo, "_cache_time", 0.0)
    monkeypatch.setattr(SecurityInfo, "_check_admin", staticmethod(lambda: False))
    monkeypatch.setattr(
        SecurityInfo,
        "get_windows_defender_status",
        staticmethod(
            lambda: {
                "enabled": None,
                "realtime_protection": None,
                "name": "",
                "status": "requires_admin",
                "definition_status": "Unknown",
            }
        ),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_firewall_status",
        staticmethod(lambda: {"enabled": None, "name": "", "status": "Requires Admin"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_tpm_status",
        staticmethod(lambda: {"present": None, "enabled": None, "version": "Unknown", "status": "Unknown", "detail": "Unable to determine"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_disk_encryption_status",
        staticmethod(lambda: {"enabled": None, "status": "Unknown", "detail": "Unable to determine"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_windows_update_status",
        staticmethod(lambda: {"status": "Unknown", "lastInstallDate": "", "detail": "Unable to determine"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_rdp_status",
        staticmethod(lambda: {"enabled": None, "nlaEnabled": None, "status": "Unknown", "detail": "Unable to determine"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_admin_account_count",
        staticmethod(lambda: {"count": None, "status": "Unknown", "detail": "Unable to determine"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_uac_level",
        staticmethod(lambda: {"level": "Unknown", "status": "Unknown", "detail": "Unable to determine"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_smartscreen_status",
        staticmethod(lambda: {"enabled": None, "status": "Unknown", "detail": "Unable to determine"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_memory_integrity_status",
        staticmethod(lambda: {"enabled": None, "status": "Unknown", "detail": "Unable to determine"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "_run_powershell",
        staticmethod(lambda *_args, **_kwargs: None),
    )

    simplified = SecurityInfo.get_simplified_security_status()
    raw = simplified["raw"]

    assert raw["firewallStatus"] == "Requires Admin"
    assert raw["antivirusStatus"] == "Admin required"
    assert raw["remoteDesktopStatus"] == "Unknown"
    assert raw["smartScreenStatus"] == "Unknown"
    assert raw["memoryIntegrityStatus"] == "Unknown"
    assert simplified["overall"]["status"] == "Needs attention"


def test_windows_summary_excludes_unsupported_optional_security_checks(monkeypatch) -> None:
    monkeypatch.setattr(SecurityInfo, "_cache", {})
    monkeypatch.setattr(SecurityInfo, "_cache_time", 0.0)
    monkeypatch.setattr(SecurityInfo, "_check_admin", staticmethod(lambda: False))
    monkeypatch.setattr(
        SecurityInfo,
        "get_windows_defender_status",
        staticmethod(
            lambda: {
                "enabled": True,
                "realtime_protection": True,
                "name": "Windows Defender",
                "status": "enabled",
                "definition_status": "Current",
            }
        ),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_firewall_status",
        staticmethod(lambda: {"enabled": True, "name": "Windows Defender Firewall", "status": "Enabled"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_tpm_status",
        staticmethod(lambda: {"present": True, "enabled": True, "version": "2.0", "status": "Present", "detail": "TPM 2.0 active"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_disk_encryption_status",
        staticmethod(lambda: {"enabled": None, "status": "Unknown", "detail": "Run as administrator to verify."}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_windows_update_status",
        staticmethod(lambda: {"status": "UpToDate", "lastInstallDate": "2026-04-20 21:34", "detail": "Current"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_rdp_status",
        staticmethod(lambda: {"enabled": False, "nlaEnabled": True, "status": "Disabled", "detail": "Remote Desktop is disabled"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_admin_account_count",
        staticmethod(lambda: {"count": 2, "status": "Good", "detail": "2 admin(s)"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_uac_level",
        staticmethod(lambda: {"level": "Medium", "status": "Medium", "detail": "Prompts without secure desktop"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_smartscreen_status",
        staticmethod(lambda: {"enabled": None, "status": "Unknown", "detail": "Unable to determine"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_memory_integrity_status",
        staticmethod(lambda: {"enabled": True, "status": "Enabled", "detail": "Memory Integrity is active"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "_run_powershell",
        staticmethod(lambda *_args, **_kwargs: None),
    )

    simplified = SecurityInfo.get_simplified_security_status()
    raw = simplified["raw"]

    assert simplified["deviceProtection"]["status"] == "Strong"
    assert simplified["deviceProtection"]["isGood"] is True
    assert simplified["remoteAndApps"]["status"] == "Safe"
    assert simplified["remoteAndApps"]["isGood"] is True
    assert simplified["overall"]["status"] == "Protected"
    assert raw["capabilities"]["smartScreen"] is False
    assert raw["capabilities"]["diskEncryption"] is False
    assert raw["capabilities"]["tpm"] is True
    assert raw["windowsUpdateDetail"] == "Current"
    assert raw["adminAccountDetail"] == "2 admin(s)"


def test_windows_summary_ignores_fully_unsupported_device_and_remote_categories(monkeypatch) -> None:
    monkeypatch.setattr(SecurityInfo, "_cache", {})
    monkeypatch.setattr(SecurityInfo, "_cache_time", 0.0)
    monkeypatch.setattr(SecurityInfo, "_check_admin", staticmethod(lambda: False))
    monkeypatch.setattr(
        SecurityInfo,
        "get_windows_defender_status",
        staticmethod(
            lambda: {
                "enabled": True,
                "realtime_protection": True,
                "name": "Windows Defender",
                "status": "enabled",
                "definition_status": "Current",
            }
        ),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_firewall_status",
        staticmethod(lambda: {"enabled": True, "name": "Windows Defender Firewall", "status": "Enabled"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_tpm_status",
        staticmethod(lambda: {"present": None, "enabled": None, "version": "Unknown", "status": "Unknown", "detail": "Unable to determine"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_disk_encryption_status",
        staticmethod(lambda: {"enabled": None, "status": "Unknown", "detail": "Unable to determine"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_windows_update_status",
        staticmethod(lambda: {"status": "UpToDate", "lastInstallDate": "2026-04-20 21:34", "detail": "Current"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_rdp_status",
        staticmethod(lambda: {"enabled": None, "nlaEnabled": None, "status": "Unknown", "detail": "Unable to determine"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_admin_account_count",
        staticmethod(lambda: {"count": None, "status": "Unknown", "detail": "Unable to determine"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_uac_level",
        staticmethod(lambda: {"level": "Unknown", "status": "Unknown", "detail": "Unable to determine"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_smartscreen_status",
        staticmethod(lambda: {"enabled": None, "status": "Unknown", "detail": "Unable to determine"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "get_memory_integrity_status",
        staticmethod(lambda: {"enabled": None, "status": "Unknown", "detail": "Unable to determine"}),
    )
    monkeypatch.setattr(
        SecurityInfo,
        "_run_powershell",
        staticmethod(lambda *_args, **_kwargs: None),
    )

    simplified = SecurityInfo.get_simplified_security_status()

    assert simplified["deviceProtection"]["status"] == "Unavailable"
    assert simplified["remoteAndApps"]["status"] == "Unavailable"
    assert simplified["overall"]["status"] == "Protected"


def test_linux_summary_excludes_unsupported_optional_checks() -> None:
    detections = {
        "firewall": {"enabled": True, "name": "UFW", "status": "Enabled", "detail": "UFW active", "level": "good"},
        "antivirus": {"installed": True, "realtime": True, "name": "ClamAV", "status": "Realtime active", "detail": "clamd is running.", "level": "good"},
        "updates": {"manager": "unknown", "pending_count": None, "status": "Unavailable", "detail": "Unsupported package manager.", "level": "unknown", "ui_status": "Unknown"},
        "secure_boot": {"enabled": None, "status": "Unknown", "detail": "Secure Boot unavailable.", "level": "unknown"},
        "disk_encryption": {"enabled": None, "status": "Unknown", "detail": "Disk encryption unavailable.", "level": "unknown"},
        "remote_access": {"enabled": False, "status": "Minimized", "detail": "No remote surface.", "level": "good", "services": [], "ports": []},
        "mandatory_access_control": {"apparmor": "Enabled", "selinux": "Disabled", "status": "Active", "detail": "Mandatory access control is active.", "level": "good"},
    }

    info = compose_security_info(
        detections,
        is_admin=False,
        os_name="Ubuntu 24.04",
        kernel="6.8.0",
        uptime="3 days",
        providers=[],
    )

    assert info["simplified"]["overall"]["status"] == "Protected"
    assert info["simplified"]["deviceProtection"]["status"] == "Strong"
    assert info["simplified"]["deviceProtection"]["isGood"] is True
    assert info["simplified"]["raw"]["capabilities"]["secureBoot"] is False
    assert info["simplified"]["raw"]["capabilities"]["diskEncryption"] is False
    assert info["simplified"]["raw"]["capabilities"]["updates"] is False


def test_probe_rtp_capability_marks_missing_windows_dependency_as_degraded(monkeypatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: ANN001
        if name == "wmi":
            raise ImportError("missing wmi")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    capability = _probe_rtp_capability("win32")

    assert capability["state"] == "degraded"
    assert "wmi" in capability["detail"]


def test_system_snapshot_security_cards_bind_to_status_keys() -> None:
    content = Path("frontend/qml/pages/SystemSnapshot.qml").read_text(encoding="utf-8")

    for token in (
        "raw.firewallStatus",
        "raw.antivirusStatus",
        "raw.remoteDesktopStatus",
        "raw.smartScreenStatus",
        "raw.memoryIntegrityStatus",
        'raw.uacLevel || "Unknown"',
        'raw.windowsUpdateDetail || ""',
        'raw.adminAccountDetail || ""',
    ):
        assert token in content


def test_system_snapshot_uses_capability_gating_for_optional_security_cards() -> None:
    content = Path("frontend/qml/pages/SystemSnapshot.qml").read_text(encoding="utf-8")

    for token in (
        'property var capabilities: (raw && raw.capabilities) ? raw.capabilities : {}',
        "readonly property bool securityControllerAvailable",
        "function canToggle(featureName)",
        'visible: securityColumn.supports("secureBoot")',
        'visible: !root.isLinux && securityColumn.supports("tpm")',
        'visible: securityColumn.supports("diskEncryption")',
        'visible: !root.isLinux && securityColumn.supports("smartScreen")',
        'visible: !root.isLinux && securityColumn.supports("memoryIntegrity")',
        'toggleable: securityColumn.canToggle("firewall")',
        'securityColumn.canToggle("rdp")',
        'securityColumn.canToggle("uac")',
    ):
        assert token in content

    assert "All security features available" not in content
    assert "Showing verifiable Windows security controls." in content


def test_scan_center_uses_normalized_clamav_status() -> None:
    content = Path("frontend/qml/pages/ScanCenter.qml").read_text(encoding="utf-8")

    assert "backend.clamAvStatus" in content
    assert "ClamAV (" in content
