"""Runtime path helpers for dev and PyInstaller builds."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    """Return True when running from a frozen executable."""
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """
    Return the directory that contains the launched application.

    In a frozen build this is the folder next to ``Sentinel.exe`` where sibling
    helper executables live. In development it is the repository root.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return _PROJECT_ROOT


def bundle_root() -> Path:
    """
    Return the directory that contains bundled resources.

    In PyInstaller builds this points at ``sys._MEIPASS`` when available so data
    files can be loaded from the extracted bundle layout.
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", app_root()))
    return _PROJECT_ROOT


def resolve_app_path(*parts: str) -> Path:
    """Resolve a path relative to the application launch directory."""
    return app_root().joinpath(*parts)


def resolve_bundle_path(*parts: str) -> Path:
    """Resolve a path relative to the bundled resource directory."""
    return bundle_root().joinpath(*parts)

