"""Linux storage normalization helpers for System Snapshot."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

NETWORK_FILESYSTEMS = {
    "9p",
    "afs",
    "ceph",
    "cifs",
    "davfs",
    "fuse.sshfs",
    "glusterfs",
    "nfs",
    "nfs4",
    "smb3",
    "smbfs",
    "sshfs",
}

PSEUDO_FILESYSTEMS = {
    "aufs",
    "autofs",
    "binfmt_misc",
    "bpf",
    "cgroup",
    "cgroup2",
    "configfs",
    "debugfs",
    "devpts",
    "devtmpfs",
    "efivarfs",
    "fuse.gvfsd-fuse",
    "fuse.lxcfs",
    "fusectl",
    "hugetlbfs",
    "mqueue",
    "nsfs",
    "overlay",
    "proc",
    "pstore",
    "ramfs",
    "rpc_pipefs",
    "securityfs",
    "selinuxfs",
    "squashfs",
    "sysfs",
    "tmpfs",
    "tracefs",
}

VISIBLE_RUN_PREFIXES = ("/run/media", "/run/user")
HIDDEN_PREFIXES = (
    "/proc",
    "/sys",
    "/dev",
    "/snap",
    "/var/lib/snapd",
    "/var/lib/docker",
    "/run/docker",
    "/run/containerd",
    "/var/lib/containers",
)


def _get_value(source: Any, key: str, default: Any = "") -> Any:
    if isinstance(source, dict):
        value = source.get(key, default)
    else:
        value = getattr(source, key, default)
    return default if value is None else value


def load_lsblk_index(timeout: int = 4) -> dict[str, dict[str, Any]]:
    """Load block-device metadata keyed by device path."""
    try:
        result = subprocess.run(
            [
                "lsblk",
                "-J",
                "-b",
                "-o",
                "NAME,KNAME,PATH,PKNAME,LABEL,MODEL,TYPE,RM,RO,TRAN,MOUNTPOINT,FSTYPE,SIZE",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return {}

    if result.returncode != 0 or not result.stdout.strip():
        return {}

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}

    index: dict[str, dict[str, Any]] = {}

    def visit(node: dict[str, Any]) -> None:
        path = node.get("path")
        if path:
            normalized = {
                "path": path,
                "name": node.get("name", ""),
                "kname": node.get("kname", ""),
                "pkname": node.get("pkname", ""),
                "label": node.get("label", ""),
                "model": (node.get("model") or "").strip(),
                "type": node.get("type", ""),
                "rm": bool(int(node.get("rm", 0))),
                "ro": bool(int(node.get("ro", 0))),
                "tran": node.get("tran", ""),
                "mountpoint": node.get("mountpoint", ""),
                "fstype": node.get("fstype", ""),
                "size": int(node.get("size", 0) or 0),
            }
            index[path] = normalized
            if normalized["name"]:
                index[f"/dev/{normalized['name']}"] = normalized
            if normalized["kname"]:
                index[f"/dev/{normalized['kname']}"] = normalized

        for child in node.get("children", []) or []:
            if isinstance(child, dict):
                visit(child)

    for device in payload.get("blockdevices", []) or []:
        if isinstance(device, dict):
            visit(device)

    return index


def _is_network_mount(device: str, fstype: str) -> bool:
    return (
        fstype.lower() in NETWORK_FILESYSTEMS
        or device.startswith("//")
        or device.startswith("\\\\")
        or (":" in device and not device.startswith("/dev/"))
    )


def _hidden_reason(device: str, mountpoint: str, fstype: str) -> str | None:
    lowered_fs = fstype.lower()
    if device.startswith("/dev/loop"):
        return "Loopback package image"
    if lowered_fs == "squashfs" or mountpoint.startswith("/snap"):
        return "Immutable Snap mount"
    if lowered_fs in PSEUDO_FILESYSTEMS:
        return "Pseudo filesystem"
    if mountpoint.startswith(HIDDEN_PREFIXES):
        return "System-managed mount"
    if mountpoint.startswith("/run") and not mountpoint.startswith(VISIBLE_RUN_PREFIXES):
        return "Ephemeral runtime mount"
    return None


def _mount_category(
    device: str,
    mountpoint: str,
    fstype: str,
    block_info: dict[str, Any],
    hidden_reason: str | None,
) -> str:
    if mountpoint in {"/", "/home"}:
        return "primary"
    if mountpoint in {"/boot", "/boot/efi", "/efi"}:
        return "boot"
    if _is_network_mount(device, fstype):
        return "network"
    if hidden_reason:
        return "hidden"
    if block_info.get("rm") or mountpoint.startswith(("/media/", "/run/media/")):
        return "external"
    return "internal"


def _sort_key(entry: dict[str, Any]) -> tuple[Any, ...]:
    category_order = {
        "primary": 0,
        "internal": 1,
        "external": 2,
        "network": 3,
        "boot": 4,
        "hidden": 5,
    }
    mountpoint = entry.get("mountpoint", "")
    if mountpoint == "/":
        mount_priority = 0
    elif mountpoint == "/home":
        mount_priority = 1
    else:
        mount_priority = 2
    return (
        category_order.get(entry.get("category", "hidden"), 9),
        mount_priority,
        0 if entry.get("usageAvailable", False) else 1,
        mountpoint.count("/"),
        entry.get("displayName", ""),
    )


def _display_name(
    device: str,
    mountpoint: str,
    category: str,
    block_info: dict[str, Any],
) -> str:
    label = block_info.get("label") or ""
    model = block_info.get("model") or ""
    if mountpoint == "/":
        return label or "System Volume"
    if mountpoint == "/home":
        return label or "Home Volume"
    if mountpoint == "/boot/efi":
        return "EFI System Partition"
    if mountpoint == "/boot":
        return "Boot Partition"
    if category == "external":
        return label or model or Path(mountpoint).name or Path(device).name or "External Media"
    if category == "network":
        return label or device or "Network Mount"
    return label or model or Path(device).name or mountpoint


def _detail_text(
    fstype: str,
    category: str,
    read_only: bool,
    hidden_reason: str | None,
) -> str:
    parts = [fstype or "unknown filesystem", category]
    if read_only:
        parts.append("read-only")
    if hidden_reason:
        parts.append(hidden_reason)
    return " | ".join(parts)


def build_mount_entry(
    partition: Any,
    usage_lookup: Any,
    block_index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a normalized mount record from a psutil partition entry."""
    device = str(_get_value(partition, "device", ""))
    mountpoint = str(_get_value(partition, "mountpoint", ""))
    fstype = str(_get_value(partition, "fstype", ""))
    opts = str(_get_value(partition, "opts", ""))
    block_info = (block_index or {}).get(device, {})

    hidden_reason = _hidden_reason(device, mountpoint, fstype)
    category = _mount_category(device, mountpoint, fstype, block_info, hidden_reason)
    read_only = "ro" in opts.split(",") or bool(block_info.get("ro"))

    usage_available = True
    usage_error = ""
    total = 0
    used = 0
    free = 0
    percent: float | None = None

    try:
        usage = usage_lookup(mountpoint)
        total = int(getattr(usage, "total", 0) or 0)
        used = int(getattr(usage, "used", 0) or 0)
        free = int(getattr(usage, "free", 0) or 0)
        percent = float(getattr(usage, "percent", 0.0))
    except PermissionError:
        usage_available = False
        usage_error = "Permission denied"
    except OSError as exc:
        usage_available = False
        usage_error = str(exc)

    return {
        "device": device,
        "mountpoint": mountpoint,
        "displayName": _display_name(device, mountpoint, category, block_info),
        "displayMount": mountpoint,
        "label": block_info.get("label", ""),
        "model": block_info.get("model", ""),
        "fstype": fstype,
        "category": category,
        "isHidden": hidden_reason is not None,
        "hiddenReason": hidden_reason or "",
        "isPrimary": mountpoint in {"/", "/home"},
        "isReadOnly": read_only,
        "isRemovable": bool(block_info.get("rm")),
        "transport": block_info.get("tran", ""),
        "usageAvailable": usage_available,
        "usageError": usage_error,
        "total": total,
        "used": used,
        "free": free,
        "percent": percent,
        "detail": _detail_text(fstype, category, read_only, hidden_reason),
    }


def normalize_linux_mounts(
    partitions: list[Any],
    usage_lookup: Any,
    block_index: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalize, de-duplicate, classify, and sort Linux mounts."""
    visible: list[dict[str, Any]] = []
    hidden: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for partition in partitions:
        entry = build_mount_entry(partition, usage_lookup, block_index=block_index)
        key = (entry["device"], entry["mountpoint"])
        if key in seen:
            continue
        seen.add(key)
        if entry["isHidden"]:
            hidden.append(entry)
        else:
            visible.append(entry)

    visible.sort(key=_sort_key)
    hidden.sort(key=_sort_key)
    return visible, hidden
