# -*- mode: python ; coding: utf-8 -*-

"""PyInstaller spec for the GPU telemetry helper executable."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(PROJECT_ROOT / "backend" / "engines" / "gpu" / "telemetry_worker.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="sentinel_gpu_worker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
