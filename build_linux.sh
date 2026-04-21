#!/bin/bash
# ══════════════════════════════════════════════════════════════════════
# Build Sentinel as a standalone Linux binary using PyInstaller
# Run this ON the Linux VM after testing from source works
# ══════════════════════════════════════════════════════════════════════
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          Sentinel Linux Build (PyInstaller)                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Activate venv
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
else
    echo "[ERROR] Run run_linux.sh first to set up the environment"
    exit 1
fi

# Install PyInstaller if not present
pip install pyinstaller -q

echo "[INFO] Building Sentinel..."

cd "$SCRIPT_DIR"

pyinstaller \
    --name "Sentinel" \
    --onedir \
    --windowed \
    --noconfirm \
    --clean \
    --add-data "frontend:frontend" \
    --add-data "backend:backend" \
    --hidden-import "backend.platform" \
    --hidden-import "backend.platform.linux" \
    --hidden-import "backend.platform.linux.admin" \
    --hidden-import "backend.platform.linux.security_controller" \
    --hidden-import "backend.platform.linux.security_info" \
    --hidden-import "backend.platform.linux.security_snapshot" \
    --hidden-import "backend.platform.linux.system_snapshot_service" \
    --hidden-import "backend.platform.linux.system_monitor_psutil" \
    --hidden-import "backend.platform.linux.events_linux" \
    --hidden-import "backend.platform.linux.secure_delete" \
    --hidden-import "backend.platform.linux.telemetry_worker" \
    --hidden-import "backend.platform.linux.chatbot_tools" \
    --hidden-import "psutil" \
    --hidden-import "PySide6.QtQuick" \
    --hidden-import "PySide6.QtQml" \
    --collect-all "PySide6" \
    main.py

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Build complete!                                            ║"
echo "║  Output: dist/Sentinel/                                     ║"
echo "║  Run:    ./dist/Sentinel/Sentinel                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
