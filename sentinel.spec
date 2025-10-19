# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller spec file for Sentinel Desktop Security Suite
Builds a single executable with all dependencies bundled.

Usage:
    pyinstaller sentinel.spec

Output:
    dist/Sentinel.exe (~45-50 MB)
"""

import sys
import os
from pathlib import Path

# Get absolute paths
workspace_dir = Path(SPECPATH)
qml_dir = workspace_dir / 'qml'
app_dir = workspace_dir / 'app'

block_cipher = None

# Collect all QML files and qmldir modules
qml_datas = []
for root, dirs, files in os.walk(qml_dir):
    for file in files:
        # Include .qml, .js files, and qmldir files (no extension check for qmldir)
        if file.endswith(('.qml', '.js')) or file == 'qmldir':
            src = os.path.join(root, file)
            # Destination maintains qml/ directory structure
            dst = os.path.relpath(root, workspace_dir)
            qml_datas.append((src, dst))
            print(f"INFO: Adding QML data: {src} -> {dst}")

# Collect additional data files
datas = qml_datas + [
    ('.env.example', '.'),
    ('requirements.txt', '.'),
    ('README.md', '.'),
    ('LICENSE', '.'),
]

# Hidden imports (modules not detected by PyInstaller)
hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuickControls2',
    'psutil',
    'win32evtlog',
    'win32evtlogutil',
    'win32con',
    'win32api',
    'pywintypes',
    'sqlite3',
    'csv',
    'json',
    'xml.etree.ElementTree',
    'subprocess',
    'pathlib',
    'dotenv',
    'requests',
]

# Analysis: Find all Python files and dependencies
a = Analysis(
    ['main.py'],
    pathex=[str(workspace_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unused modules to reduce size
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'tkinter',
        'PyQt5',
        'PyQt6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# PYZ: Create Python archive
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

# EXE: Create executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # Changed: Don't bundle everything in one file
    name='Sentinel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Compress with UPX (reduces size by ~30%)
    console=True,  # Changed: Enable console for debugging
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Icon (if you have one, otherwise remove this line)
    # icon='sentinel.ico',
)

# COLLECT: Create a directory distribution (REQUIRED for QML files)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Sentinel',
)
