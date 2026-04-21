"""
DRM card enumeration for Linux.

Scans /sys/class/drm/card* and returns real GPU devices, filtering out
display-connector entries (e.g., card0-DP-1, card0-HDMI-A-1).

Vendor IDs:
  AMD:    0x1002
  NVIDIA: 0x10DE
  Intel:  0x8086
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

VENDOR_AMD    = 0x1002
VENDOR_NVIDIA = 0x10DE
VENDOR_INTEL  = 0x8086

_VENDOR_NAMES: dict[int, str] = {
    VENDOR_AMD:    "AMD",
    VENDOR_NVIDIA: "NVIDIA",
    VENDOR_INTEL:  "Intel",
}

# Connector entries have a hyphen after the card number: card0-DP-1, card0-HDMI-A-1, …
_CONNECTOR_RE = re.compile(r"^card\d+-")
_CARD_RE      = re.compile(r"^card\d+$")
_PCI_ADDR_RE  = re.compile(r"^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F]$")

_DRM_DIR = Path("/sys/class/drm")


@dataclass
class DRMCard:
    card_name:    str   # e.g. "card0"
    drm_path:     Path  # /sys/class/drm/card0
    device_path:  Path  # /sys/class/drm/card0/device (or resolved real path)
    pci_address:  str   # e.g. "0000:01:00.0"  — empty string when unknown
    vendor_id:    int   # e.g. 0x1002
    device_id:    int   # e.g. 0x15bf
    vendor_name:  str   # "AMD" | "NVIDIA" | "Intel" | "Unknown"
    driver:       str   # e.g. "amdgpu"
    is_integrated: bool # True when PCI class indicates a display controller (iGPU heuristic)


# ── sysfs helpers ───────────────────────────────────────────────────────────

def _read_hex(path: Path) -> int | None:
    try:
        return int(path.read_text().strip(), 16)
    except (OSError, ValueError):
        return None


def _read_driver(device_path: Path) -> str:
    """Follow the driver symlink and return just the driver name."""
    try:
        return Path(os.readlink(device_path / "driver")).name
    except OSError:
        return "unknown"


def _pci_address(device_path: Path) -> str:
    """
    Resolve the canonical PCI address from the device symlink target.

    /sys/class/drm/card0/device → typically resolves to
    /sys/devices/pci0000:00/0000:00:08.1/0000:01:00.0
    The last path component that matches the PCI address format is returned.
    """
    try:
        resolved = device_path.resolve()
        for part in reversed(resolved.parts):
            if _PCI_ADDR_RE.match(part):
                return part
    except (OSError, AttributeError):
        pass
    return ""


def _is_integrated(device_path: Path) -> bool:
    """
    Heuristic: read the PCI class register to distinguish integrated from discrete.

    PCI class 0x038000 = Display Controller (common for iGPUs / APUs).
    PCI class 0x030000 = VGA compatible controller (most discrete GPUs).
    PCI class 0x030200 = 3D controller (some discrete and some iGPUs).

    Returns True only when the class clearly indicates an integrated display
    controller; defaults to False (treat as discrete) when the class is absent
    or ambiguous.
    """
    class_val = _read_hex(device_path / "class")
    if class_val is None:
        return False
    return (class_val >> 8) == 0x0380


# ── public API ──────────────────────────────────────────────────────────────

def enumerate_drm_cards(drm_dir: Path | None = None) -> list[DRMCard]:
    """
    Return all real GPU DRM card entries found under *drm_dir*.

    Display-connector entries (card0-DP-1, card0-HDMI-A-1, …) are excluded.
    Cards whose vendor ID cannot be read are skipped and logged at DEBUG level.

    The default *drm_dir* is /sys/class/drm; a different directory can be
    supplied for unit tests.
    """
    root = drm_dir or _DRM_DIR
    if not root.exists():
        return []

    try:
        entries = sorted(root.iterdir())
    except OSError as exc:
        logger.debug("Cannot iterate %s: %s", root, exc)
        return []

    cards: list[DRMCard] = []

    for entry in entries:
        name = entry.name

        if _CONNECTOR_RE.match(name):
            continue  # e.g. card0-DP-1 — display connector, not a GPU

        if not _CARD_RE.match(name):
            continue  # unexpected entry — skip

        device_path = entry / "device"
        if not device_path.exists():
            logger.debug("DRM entry %s has no device/ directory, skipping", name)
            continue

        vendor_id = _read_hex(device_path / "vendor")
        if vendor_id is None:
            logger.debug("DRM card %s: vendor ID unreadable, skipping", name)
            continue

        device_id   = _read_hex(device_path / "device") or 0
        vendor_name = _VENDOR_NAMES.get(vendor_id, "Unknown")
        driver      = _read_driver(device_path)
        pci_addr    = _pci_address(device_path)
        integrated  = _is_integrated(device_path)

        cards.append(DRMCard(
            card_name=name,
            drm_path=entry,
            device_path=device_path,
            pci_address=pci_addr,
            vendor_id=vendor_id,
            device_id=device_id,
            vendor_name=vendor_name,
            driver=driver,
            is_integrated=integrated,
        ))

        logger.debug(
            "DRM card found: %s  vendor=%s (0x%04x)  driver=%s  pci=%s  integrated=%s",
            name, vendor_name, vendor_id, driver, pci_addr or "(unknown)", integrated,
        )

    return cards
