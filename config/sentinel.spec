# -*- mode: python ; coding: utf-8 -*-

"""PyInstaller spec for the Sentinel Windows desktop application."""

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

PROJECT_ROOT = Path(SPECPATH).resolve().parent


def collect_directory_files(source_dir: Path, destination_root: str) -> list[tuple[str, str]]:
    """Recursively collect files while preserving relative layout."""
    datas: list[tuple[str, str]] = []
    if not source_dir.exists():
        return datas

    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue

        relative_parent = path.relative_to(source_dir).parent
        destination = Path(destination_root, relative_parent).as_posix()
        datas.append((str(path), destination))

    return datas


datas = []
datas += collect_directory_files(PROJECT_ROOT / "frontend" / "qml", "frontend/qml")
datas += collect_directory_files(
    PROJECT_ROOT / "backend" / "engines" / "ai" / "knowledge",
    "backend/engines/ai/knowledge",
)
datas += collect_directory_files(
    PROJECT_ROOT / "backend" / "engines" / "sandbox_vmware" / "guest_scripts",
    "backend/engines/sandbox_vmware/guest_scripts",
)
datas += collect_directory_files(
    PROJECT_ROOT / "payload" / "sandbox_agent",
    "payload/sandbox_agent",
)

for file_path, destination in (
    (PROJECT_ROOT / "backend" / "engines" / "ai" / "event_knowledge.json", "backend/engines/ai"),
    (PROJECT_ROOT / "config" / "vmware.json", "config"),
):
    if file_path.exists():
        datas.append((str(file_path), destination))


hiddenimports = sorted(
    set(
        [
            "PySide6.QtCore",
            "PySide6.QtGui",
            "PySide6.QtWidgets",
            "PySide6.QtQml",
            "PySide6.QtQuick",
            "PySide6.QtQuickControls2",
            "psutil",
            "sqlite3",
            "requests",
            "pywintypes",
            "win32api",
            "win32con",
            "win32evtlog",
            "win32evtlogutil",
        ]
        + collect_submodules("backend.engines.ai.providers")
        + collect_submodules("backend.engines.sandbox_vmware")
    )
)


a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "tkinter",
        "PyQt5",
        "PyQt6",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Sentinel",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Sentinel",
)
