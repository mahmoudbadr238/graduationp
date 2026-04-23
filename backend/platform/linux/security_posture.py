"""Platform-native Linux security posture collection."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil


@dataclass(frozen=True)
class CommandResult:
    """Captured command execution result."""

    args: tuple[str, ...]
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    timed_out: bool = False
    not_found: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.error and not self.timed_out


def run_command(args: list[str], timeout: int = 5) -> CommandResult:
    """Run a command with safe defaults and structured error reporting."""
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(
            args=tuple(args),
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )
    except FileNotFoundError:
        return CommandResult(tuple(args), None, not_found=True, error="not_found")
    except subprocess.TimeoutExpired:
        return CommandResult(tuple(args), None, timed_out=True, error="timed_out")
    except OSError as exc:
        return CommandResult(tuple(args), None, error=str(exc))


def _provider(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def detect_firewall(runner: Any = run_command) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Detect Linux firewall status across common stacks."""
    providers: list[dict[str, str]] = []

    ufw_status = runner(["ufw", "status", "verbose"])
    if not ufw_status.not_found:
        if ufw_status.ok:
            output = ufw_status.stdout.lower()
            if "status: active" in output:
                detail = "UFW is active"
                default_line = next(
                    (
                        line.strip()
                        for line in ufw_status.stdout.splitlines()
                        if line.lower().startswith("default:")
                    ),
                    "",
                )
                if default_line:
                    detail = f"{detail}. {default_line}"
                providers.append(_provider("ufw", "ok", detail))
                return {
                    "name": "UFW",
                    "enabled": True,
                    "status": "Enabled",
                    "detail": detail,
                    "level": "good",
                }, providers
            if "status: inactive" in output:
                detail = "UFW is installed but inactive"
                providers.append(_provider("ufw", "warning", detail))
                return {
                    "name": "UFW",
                    "enabled": False,
                    "status": "Disabled",
                    "detail": detail,
                    "level": "error",
                }, providers
        detail = ufw_status.stderr.strip() or ufw_status.error or "UFW status unavailable"
        providers.append(_provider("ufw", "error", detail))

    firewalld = runner(["systemctl", "is-active", "firewalld"])
    if firewalld.returncode == 0:
        detail = "firewalld service is active"
        providers.append(_provider("firewalld", "ok", detail))
        return {
            "name": "firewalld",
            "enabled": True,
            "status": "Enabled",
            "detail": detail,
            "level": "good",
        }, providers
    if not firewalld.not_found:
        providers.append(
            _provider(
                "firewalld",
                "info",
                firewalld.stderr.strip() or firewalld.stdout.strip() or "firewalld inactive",
            )
        )

    nftables = runner(["systemctl", "is-active", "nftables"])
    if nftables.returncode == 0:
        detail = "nftables service is active"
        providers.append(_provider("nftables", "ok", detail))
        return {
            "name": "nftables",
            "enabled": True,
            "status": "Enabled",
            "detail": detail,
            "level": "good",
        }, providers
    if not nftables.not_found:
        providers.append(
            _provider(
                "nftables",
                "info",
                nftables.stderr.strip() or nftables.stdout.strip() or "nftables inactive",
            )
        )

    iptables = runner(["iptables", "-S"])
    if iptables.ok and iptables.stdout.strip():
        detail = "iptables rules are present"
        providers.append(_provider("iptables", "ok", detail))
        return {
            "name": "iptables",
            "enabled": True,
            "status": "Enabled",
            "detail": detail,
            "level": "good",
        }, providers
    if not iptables.not_found:
        providers.append(
            _provider(
                "iptables",
                "info",
                iptables.stderr.strip() or iptables.error or "iptables rules unavailable",
            )
        )

    providers.append(_provider("firewall", "warning", "No supported firewall service detected"))
    return {
        "name": "None detected",
        "enabled": False,
        "status": "Not installed",
        "detail": "No supported firewall service was detected (UFW, firewalld, nftables, or iptables).",
        "level": "error",
    }, providers


def detect_antivirus(runner: Any = run_command) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Detect ClamAV presence and daemon state."""
    providers: list[dict[str, str]] = []

    scanner_path = shutil.which("clamscan") or shutil.which("clamdscan")
    scanner_name = Path(scanner_path).name if scanner_path else ""
    version_result = runner([scanner_name or "clamscan", "--version"])
    if version_result.not_found:
        providers.append(_provider("clamav", "warning", "ClamAV CLI not installed"))
        return {
            "name": "ClamAV",
            "installed": False,
            "realtime": False,
            "status": "Not installed",
            "detail": "ClamAV CLI tools were not found on PATH.",
            "level": "error",
        }, providers

    version_line = (version_result.stdout or "").splitlines()[0].strip() if version_result.stdout else "ClamAV"
    providers.append(_provider("clamav", "ok", version_line))

    daemon_state = runner(["systemctl", "is-active", "clamav-daemon"])
    realtime = daemon_state.returncode == 0
    if realtime:
        providers.append(_provider("clamav-daemon", "ok", "clamav-daemon service is active"))
        return {
            "name": "ClamAV",
            "installed": True,
            "realtime": True,
            "status": "Realtime active",
            "detail": f"{version_line}. clamd is running.",
            "level": "good",
        }, providers

    pgrep = runner(["pgrep", "-x", "clamd"])
    realtime = bool(pgrep.stdout.strip())
    if realtime:
        providers.append(_provider("clamd", "ok", "clamd process is active"))
        return {
            "name": "ClamAV",
            "installed": True,
            "realtime": True,
            "status": "Realtime active",
            "detail": f"{version_line}. clamd is running.",
            "level": "good",
        }, providers

    providers.append(_provider("clamd", "warning", "ClamAV installed without active daemon"))
    return {
        "name": "ClamAV",
        "installed": True,
        "realtime": False,
        "status": "Scanner only",
        "detail": f"{version_line}. On-demand scanning available, but clamd is not active.",
        "level": "warning",
    }, providers


def detect_package_updates(runner: Any = run_command) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Detect package manager and whether updates are pending."""
    providers: list[dict[str, str]] = []

    if shutil.which("apt"):
        result = runner(["apt", "list", "--upgradable"], timeout=12)
        if result.ok:
            lines = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip() and not line.lower().startswith("listing")
            ]
            pending = len(lines)
            providers.append(_provider("apt", "ok", f"{pending} upgradable packages"))
            return {
                "manager": "apt",
                "pending_count": pending,
                "status": "Up to date" if pending == 0 else f"{pending} pending",
                "detail": "No pending package updates detected." if pending == 0 else f"{pending} package updates are available via apt.",
                "level": "good" if pending == 0 else "warning",
                "ui_status": "UpToDate" if pending == 0 else "PendingUpdates",
            }, providers
        providers.append(_provider("apt", "error", result.stderr.strip() or result.error or "apt update check failed"))
        return {
            "manager": "apt",
            "pending_count": None,
            "status": "Unavailable",
            "detail": "Sentinel could not determine package update status via apt.",
            "level": "unknown",
            "ui_status": "Unknown",
        }, providers

    if shutil.which("dnf"):
        result = runner(["dnf", "check-update"], timeout=15)
        if result.returncode in (0, 100):
            lines = [line for line in result.stdout.splitlines() if line.strip() and not line.startswith("Last metadata")]
            pending = 0 if result.returncode == 0 else len(lines)
            providers.append(_provider("dnf", "ok", f"{pending} pending updates"))
            return {
                "manager": "dnf",
                "pending_count": pending,
                "status": "Up to date" if pending == 0 else f"{pending} pending",
                "detail": "No pending package updates detected." if pending == 0 else f"{pending} package updates are available via dnf.",
                "level": "good" if pending == 0 else "warning",
                "ui_status": "UpToDate" if pending == 0 else "PendingUpdates",
            }, providers

    if shutil.which("pacman"):
        cmd = ["checkupdates"] if shutil.which("checkupdates") else ["pacman", "-Qu"]
        result = runner(cmd, timeout=15)
        if result.ok or result.returncode == 2:
            lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            pending = len(lines)
            providers.append(_provider("pacman", "ok", f"{pending} pending updates"))
            return {
                "manager": "pacman",
                "pending_count": pending,
                "status": "Up to date" if pending == 0 else f"{pending} pending",
                "detail": "No pending package updates detected." if pending == 0 else f"{pending} package updates are available via pacman.",
                "level": "good" if pending == 0 else "warning",
                "ui_status": "UpToDate" if pending == 0 else "PendingUpdates",
            }, providers

    providers.append(_provider("package-manager", "warning", "No supported package manager probe available"))
    return {
        "manager": "unknown",
        "pending_count": None,
        "status": "Unavailable",
        "detail": "Sentinel could not determine a supported package manager for update status.",
        "level": "unknown",
        "ui_status": "Unknown",
    }, providers


def detect_secure_boot(runner: Any = run_command) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Detect Secure Boot state via EFI variables or mokutil."""
    providers: list[dict[str, str]] = []
    efivar_root = Path("/sys/firmware/efi/efivars")
    secureboot_entries = list(efivar_root.glob("SecureBoot-*")) if efivar_root.exists() else []
    if secureboot_entries:
        try:
            raw = secureboot_entries[0].read_bytes()
            enabled = bool(raw[-1])
            detail = "Detected from EFI SecureBoot variable."
            providers.append(_provider("efivars", "ok", detail))
            return {
                "enabled": enabled,
                "status": "Enabled" if enabled else "Disabled",
                "detail": detail,
                "level": "good" if enabled else "warning",
            }, providers
        except OSError as exc:
            providers.append(_provider("efivars", "error", str(exc)))

    mokutil = runner(["mokutil", "--sb-state"])
    if mokutil.ok:
        output = mokutil.stdout.lower()
        enabled = "enabled" in output and "disabled" not in output
        detail = mokutil.stdout.strip()
        providers.append(_provider("mokutil", "ok", detail))
        return {
            "enabled": enabled,
            "status": "Enabled" if enabled else "Disabled",
            "detail": detail,
            "level": "good" if enabled else "warning",
        }, providers

    providers.append(_provider("secure-boot", "warning", "Secure Boot state unavailable"))
    return {
        "enabled": None,
        "status": "Unknown",
        "detail": "Secure Boot state could not be determined on this system.",
        "level": "unknown",
    }, providers


def detect_disk_encryption(runner: Any = run_command) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Detect whether root or home is backed by encrypted block devices."""
    providers: list[dict[str, str]] = []
    result = runner(
        [
            "lsblk",
            "-J",
            "-o",
            "NAME,PATH,TYPE,FSTYPE,MOUNTPOINT,PKNAME",
        ],
        timeout=8,
    )
    if not result.ok:
        providers.append(_provider("lsblk", "warning", result.stderr.strip() or result.error or "lsblk unavailable"))
        return {
            "enabled": None,
            "status": "Unknown",
            "detail": "Disk encryption could not be determined because lsblk output was unavailable.",
            "level": "unknown",
        }, providers

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        providers.append(_provider("lsblk", "error", "Invalid JSON output"))
        return {
            "enabled": None,
            "status": "Unknown",
            "detail": "Disk encryption could not be determined from lsblk output.",
            "level": "unknown",
        }, providers

    parent_by_path: dict[str, str] = {}
    node_by_path: dict[str, dict[str, Any]] = {}

    def visit(node: dict[str, Any], parent_path: str | None = None) -> None:
        path = node.get("path")
        if path:
            node_by_path[path] = node
            if parent_path:
                parent_by_path[path] = parent_path
        for child in node.get("children", []) or []:
            if isinstance(child, dict):
                visit(child, path)

    for root in payload.get("blockdevices", []) or []:
        if isinstance(root, dict):
            visit(root)

    protected_mounts: list[str] = []
    checked_mounts = {"/", "/home"}
    for node in node_by_path.values():
        mountpoint = node.get("mountpoint")
        if mountpoint not in checked_mounts:
            continue
        current_path = node.get("path", "")
        while current_path:
            current = node_by_path.get(current_path, {})
            if current.get("type") == "crypt" or str(current.get("fstype", "")).lower() == "crypto_luks":
                protected_mounts.append(mountpoint)
                break
            current_path = parent_by_path.get(current_path, "")

    if protected_mounts:
        detail = f"Encrypted backing device detected for {', '.join(sorted(protected_mounts))}."
        providers.append(_provider("lsblk", "ok", detail))
        return {
            "enabled": True,
            "status": "Enabled",
            "detail": detail,
            "level": "good",
        }, providers

    providers.append(_provider("lsblk", "warning", "No encrypted root or home volume detected"))
    return {
        "enabled": False,
        "status": "Not detected",
        "detail": "No encrypted backing device was detected for the root or home volume.",
        "level": "warning",
    }, providers


def detect_remote_access(runner: Any = run_command) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Detect remote administration services and listening ports."""
    providers: list[dict[str, str]] = []
    services: list[str] = []

    for unit, label in (("ssh", "SSH"), ("sshd", "SSH"), ("xrdp", "XRDP")):
        state = runner(["systemctl", "is-active", unit])
        if state.returncode == 0 and label not in services:
            services.append(label)
            providers.append(_provider(unit, "ok", f"{unit} service is active"))

    exposed_ports: list[int] = []
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.status != psutil.CONN_LISTEN:
                continue
            if not conn.laddr:
                continue
            if conn.laddr.port in (22, 3389) and conn.laddr.port not in exposed_ports:
                exposed_ports.append(conn.laddr.port)
    except (psutil.AccessDenied, OSError):
        providers.append(_provider("net_connections", "warning", "Listening-port visibility is limited"))

    enabled = bool(services or exposed_ports)
    if enabled:
        details: list[str] = []
        if services:
            details.append("services: " + ", ".join(services))
        if exposed_ports:
            details.append("ports: " + ", ".join(str(port) for port in sorted(exposed_ports)))
        detail = "Remote administration surface is exposed (" + "; ".join(details) + ")."
        return {
            "enabled": True,
            "status": "Exposed",
            "detail": detail,
            "level": "warning",
            "services": services,
            "ports": sorted(exposed_ports),
        }, providers

    detail = "No SSH, XRDP, or related listening admin ports were detected."
    providers.append(_provider("remote-access", "ok", detail))
    return {
        "enabled": False,
        "status": "Minimized",
        "detail": detail,
        "level": "good",
        "services": [],
        "ports": [],
    }, providers


def detect_mandatory_access_control(runner: Any = run_command) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Detect AppArmor and SELinux enforcement state."""
    providers: list[dict[str, str]] = []

    apparmor_enabled = False
    apparmor_file = Path("/sys/module/apparmor/parameters/enabled")
    if apparmor_file.exists():
        try:
            apparmor_enabled = apparmor_file.read_text(encoding="utf-8").strip().lower().startswith("y")
        except OSError:
            apparmor_enabled = False
    else:
        aa_status = runner(["aa-status", "--enabled"])
        apparmor_enabled = aa_status.returncode == 0
        if not aa_status.not_found:
            providers.append(_provider("aa-status", "ok" if apparmor_enabled else "info", aa_status.stdout.strip() or aa_status.stderr.strip()))

    selinux = runner(["getenforce"])
    selinux_mode = selinux.stdout.strip() if selinux.ok else "Not installed"
    if not selinux.not_found:
        providers.append(_provider("selinux", "ok" if selinux.ok else "info", selinux_mode))

    any_enforced = apparmor_enabled or selinux_mode == "Enforcing"
    return {
        "apparmor": "Enabled" if apparmor_enabled else ("Not installed" if not apparmor_file.exists() and selinux.not_found else "Disabled"),
        "selinux": selinux_mode,
        "status": "Active" if any_enforced else "Inactive",
        "detail": "Mandatory access control is active." if any_enforced else "Neither AppArmor nor SELinux is enforcing policy.",
        "level": "good" if any_enforced else "warning",
    }, providers


def compose_security_info(
    detections: dict[str, dict[str, Any]],
    *,
    is_admin: bool,
    os_name: str,
    kernel: str,
    uptime: str,
    providers: list[dict[str, str]],
) -> dict[str, Any]:
    """Map Linux security detections into the UI-facing snapshot structure."""
    firewall = detections["firewall"]
    antivirus = detections["antivirus"]
    updates = detections["updates"]
    secure_boot = detections["secure_boot"]
    encryption = detections["disk_encryption"]
    remote = detections["remote_access"]
    mac = detections["mandatory_access_control"]

    capabilities = {
        "firewall": True,
        "antivirus": True,
        "secureBoot": secure_boot.get("enabled") is not None,
        "tpm": False,
        "diskEncryption": encryption.get("enabled") is not None,
        "updates": updates.get("manager") != "unknown",
        "remoteDesktop": True,
        "localAdmins": False,
        "uac": False,
        "smartScreen": False,
        "memoryIntegrity": False,
        "mandatoryAccessControl": True,
    }

    score = 100
    for name, finding in (
        ("firewall", firewall),
        ("antivirus", antivirus),
        ("updates", updates),
        ("secureBoot", secure_boot),
        ("diskEncryption", encryption),
        ("remoteDesktop", remote),
        ("mandatoryAccessControl", mac),
    ):
        if not capabilities.get(name, False):
            continue
        if finding["level"] == "error":
            score -= 25
        elif finding["level"] == "warning":
            score -= 12
        elif finding["level"] == "unknown":
            score -= 5

    score = max(0, score)
    if score >= 80:
        overall_status = "Protected"
        overall_detail = "Core controls are active and the Linux host posture looks healthy."
        overall_good = True
        overall_warning = False
    elif score >= 60:
        overall_status = "Needs attention"
        overall_detail = "The host is usable, but some security controls need review."
        overall_good = False
        overall_warning = True
    else:
        overall_status = "Degraded"
        overall_detail = "Multiple Linux security controls are missing, inactive, or unverifiable."
        overall_good = False
        overall_warning = False

    device_detail_parts: list[str] = []
    unsupported_device_checks: list[str] = []

    if capabilities["antivirus"]:
        device_detail_parts.append(antivirus["detail"])
    if capabilities["secureBoot"]:
        device_detail_parts.append(secure_boot["detail"])
    else:
        unsupported_device_checks.append("Secure Boot")
    if capabilities["diskEncryption"]:
        device_detail_parts.append(encryption["detail"])
    else:
        unsupported_device_checks.append("disk encryption")
    if capabilities["mandatoryAccessControl"]:
        device_detail_parts.append(mac["detail"])

    supported_device_checks = 0
    passing_device_checks = 0
    supported_device_has_risk = False

    if capabilities["antivirus"]:
        supported_device_checks += 1
        if antivirus["level"] == "good":
            passing_device_checks += 1
        else:
            supported_device_has_risk = True

    if capabilities["secureBoot"]:
        supported_device_checks += 1
        if secure_boot.get("enabled") is True:
            passing_device_checks += 1
        else:
            supported_device_has_risk = True

    if capabilities["diskEncryption"]:
        supported_device_checks += 1
        if encryption.get("enabled") is True:
            passing_device_checks += 1
        else:
            supported_device_has_risk = True

    if capabilities["mandatoryAccessControl"]:
        supported_device_checks += 1
        if mac["status"] == "Active":
            passing_device_checks += 1
        else:
            supported_device_has_risk = True

    if supported_device_checks == 0:
        device_status = "Unknown"
        device_good = False
        device_warning = True
    elif not supported_device_has_risk:
        device_status = "Strong"
        device_good = True
        device_warning = False
    elif passing_device_checks > 0:
        device_status = "Okay"
        device_good = False
        device_warning = True
    else:
        device_status = "Degraded"
        device_good = False
        device_warning = False

    device_detail = " ".join(part for part in device_detail_parts if part)
    if unsupported_device_checks:
        note = "Additional checks unavailable: " + ", ".join(unsupported_device_checks) + "."
        device_detail = f"{device_detail} {note}".strip()

    remote_status = "Minimized" if not remote["enabled"] else "Exposed"

    return {
        "firewallStatus": firewall["status"],
        "antivirus": antivirus["status"],
        "antivirusEnabled": antivirus.get("installed", False),
        "secureBoot": secure_boot["status"],
        "tpmPresent": "N/A",
        "tpmEnabled": False,
        "tpmVersion": "N/A",
        "appArmorEnabled": mac["apparmor"],
        "selinuxEnabled": mac["selinux"],
        "osName": os_name,
        "kernel": kernel,
        "uptime": uptime,
        "diskEncryption": encryption["status"],
        "diskEncryptionDetail": encryption["detail"],
        "windowsUpdateStatus": updates["ui_status"],
        "windowsUpdateLastInstall": "",
        "windowsUpdateDetail": updates["detail"],
        "remoteDesktopEnabled": remote["enabled"],
        "remoteDesktopNla": False,
        "remoteDesktopDetail": remote["detail"],
        "adminAccountCount": 0,
        "adminAccountDetail": "Elevated session active." if is_admin else "Standard user session.",
        "uacLevel": "N/A",
        "uacDetail": "Not applicable on Linux.",
        "smartScreenEnabled": None,
        "smartScreenDetail": "Not applicable on Linux.",
        "memoryIntegrityEnabled": None,
        "memoryIntegrityDetail": "Not applicable on Linux.",
        "providers": providers,
        "simplified": {
            "overall": {
                "isGood": overall_good,
                "isWarning": overall_warning,
                "status": overall_status,
                "detail": overall_detail,
                "score": score,
            },
            "internetProtection": {
                "isGood": firewall["level"] == "good",
                "isWarning": firewall["level"] in {"warning", "unknown"},
                "status": firewall["status"],
                "detail": firewall["detail"],
            },
            "updates": {
                "isGood": updates["level"] == "good",
                "isWarning": updates["level"] in {"warning", "unknown"},
                "status": updates["status"],
                "detail": updates["detail"],
            },
            "deviceProtection": {
                "isGood": device_good,
                "isWarning": device_warning,
                "status": device_status,
                "detail": device_detail,
            },
            "remoteAndApps": {
                "isGood": remote["level"] == "good",
                "isWarning": remote["level"] in {"warning", "unknown"},
                "status": remote_status,
                "detail": remote["detail"],
            },
            "raw": {
                "firewallEnabled": firewall["enabled"],
                "firewallStatus": firewall["status"],
                "firewallName": firewall["name"],
                "antivirusEnabled": antivirus.get("installed", False),
                "antivirusStatus": antivirus["status"],
                "antivirusName": antivirus["name"],
                "antivirusRealtime": antivirus.get("realtime", False),
                "antivirusDetail": antivirus["detail"],
                "secureBoot": secure_boot["status"],
                "diskEncryption": encryption["status"],
                "diskEncryptionDetail": encryption["detail"],
                "windowsUpdateStatus": updates["ui_status"],
                "windowsUpdateLastInstall": "",
                "windowsUpdateDetail": updates["detail"],
                "remoteDesktopEnabled": remote["enabled"],
                "remoteDesktopStatus": remote["status"],
                "remoteDesktopDetail": remote["detail"],
                "remoteDesktopNla": False,
                "adminAccountCount": 0,
                "adminAccountDetail": "Elevated session active." if is_admin else "Standard user session.",
                "uacLevel": "N/A",
                "uacDetail": "Not applicable on Linux.",
                "smartScreenEnabled": None,
                "smartScreenStatus": "Not applicable",
                "smartScreenDetail": "Not applicable on Linux.",
                "memoryIntegrityEnabled": None,
                "memoryIntegrityStatus": "Not applicable",
                "memoryIntegrityDetail": "Not applicable on Linux.",
                "capabilities": capabilities,
                "linuxUpdateManager": updates["manager"],
                "linuxUpdatePendingCount": updates.get("pending_count"),
                "linuxRemoteServices": remote.get("services", []),
                "linuxRemotePorts": remote.get("ports", []),
                "linuxMandatoryAccessControl": mac["status"],
                "linuxMandatoryAccessControlDetail": mac["detail"],
                "linuxAppArmor": mac["apparmor"],
                "linuxSELinux": mac["selinux"],
            },
        },
    }


def collect_security_info(
    *,
    runner: Any = run_command,
    is_admin: bool,
    os_name: str,
    kernel: str,
    uptime: str,
) -> dict[str, Any]:
    """Collect platform-native Linux security posture information."""
    firewall, firewall_providers = detect_firewall(runner)
    antivirus, antivirus_providers = detect_antivirus(runner)
    updates, update_providers = detect_package_updates(runner)
    secure_boot, secure_boot_providers = detect_secure_boot(runner)
    encryption, encryption_providers = detect_disk_encryption(runner)
    remote, remote_providers = detect_remote_access(runner)
    mac, mac_providers = detect_mandatory_access_control(runner)

    detections = {
        "firewall": firewall,
        "antivirus": antivirus,
        "updates": updates,
        "secure_boot": secure_boot,
        "disk_encryption": encryption,
        "remote_access": remote,
        "mandatory_access_control": mac,
    }
    providers = [
        *firewall_providers,
        *antivirus_providers,
        *update_providers,
        *secure_boot_providers,
        *encryption_providers,
        *remote_providers,
        *mac_providers,
    ]
    return compose_security_info(
        detections,
        is_admin=is_admin,
        os_name=os_name,
        kernel=kernel,
        uptime=uptime,
        providers=providers,
    )
