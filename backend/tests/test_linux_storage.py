"""Tests for Linux storage normalization and filtering."""

from __future__ import annotations

from types import SimpleNamespace

from backend.platform.linux.storage import build_mount_entry, normalize_linux_mounts


def _partition(device: str, mountpoint: str, fstype: str, opts: str = "rw") -> SimpleNamespace:
    return SimpleNamespace(device=device, mountpoint=mountpoint, fstype=fstype, opts=opts)


def _usage(total: int, used: int, percent: float) -> SimpleNamespace:
    return SimpleNamespace(total=total, used=used, free=total - used, percent=percent)


def test_normalize_linux_mounts_filters_hidden_mounts_and_sorts_visible():
    partitions = [
        _partition("/dev/nvme0n1p2", "/", "ext4"),
        _partition("/dev/nvme0n1p3", "/home", "ext4"),
        _partition("/dev/sdb1", "/run/media/demo/USB", "ext4"),
        _partition("server:/share", "/mnt/share", "nfs4"),
        _partition("/dev/nvme0n1p1", "/boot/efi", "vfat", "rw"),
        _partition("/dev/loop0", "/snap/core/17200", "squashfs", "ro"),
        _partition("proc", "/proc", "proc", "ro"),
        _partition("overlay", "/var/lib/docker/overlay2/abc", "overlay", "rw"),
        _partition("/dev/nvme0n1p2", "/", "ext4"),  # duplicate entry should collapse
    ]

    usage_map = {
        "/": _usage(1000, 400, 40.0),
        "/home": _usage(2000, 700, 35.0),
        "/run/media/demo/USB": _usage(500, 100, 20.0),
        "/mnt/share": _usage(3000, 1500, 50.0),
        "/boot/efi": _usage(256, 64, 25.0),
        "/snap/core/17200": _usage(128, 128, 100.0),
    }

    def usage_lookup(mountpoint: str):
        if mountpoint not in usage_map:
            raise OSError("usage unavailable")
        return usage_map[mountpoint]

    block_index = {
        "/dev/nvme0n1p2": {"label": "", "model": "Samsung SSD", "rm": False, "ro": False, "tran": "nvme"},
        "/dev/nvme0n1p3": {"label": "home", "model": "Samsung SSD", "rm": False, "ro": False, "tran": "nvme"},
        "/dev/sdb1": {"label": "USB-STICK", "model": "Kingston", "rm": True, "ro": False, "tran": "usb"},
        "/dev/nvme0n1p1": {"label": "", "model": "Samsung SSD", "rm": False, "ro": False, "tran": "nvme"},
    }

    visible, hidden = normalize_linux_mounts(partitions, usage_lookup, block_index)

    assert [entry["mountpoint"] for entry in visible] == ["/", "/home", "/run/media/demo/USB", "/mnt/share", "/boot/efi"]
    assert {entry["mountpoint"] for entry in hidden} == {"/snap/core/17200", "/proc", "/var/lib/docker/overlay2/abc"}
    assert visible[0]["category"] == "primary"
    assert visible[2]["category"] == "external"
    assert visible[3]["category"] == "network"
    assert visible[4]["category"] == "boot"
    assert hidden[0]["isHidden"] is True


def test_build_mount_entry_marks_permission_denied_usage():
    part = _partition("/dev/sdc1", "/media/user/secure", "ext4")

    def denied_usage(_: str):
        raise PermissionError("denied")

    entry = build_mount_entry(part, denied_usage, block_index={"/dev/sdc1": {"rm": True, "ro": False, "tran": "usb"}})

    assert entry["usageAvailable"] is False
    assert entry["usageError"] == "Permission denied"
    assert entry["category"] == "external"
    assert entry["percent"] is None
