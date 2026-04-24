#!/bin/bash
# ══════════════════════════════════════════════════════════════════════
# Sentinel Linux Setup & Run Script
# ══════════════════════════════════════════════════════════════════════
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          Sentinel Security Suite — Linux Setup              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Check Python ─────────────────────────────────────────────
PYTHON=""
for cmd in python3.11 python3.10 python3.12 python3; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[ERROR] Python 3.10+ not found. Install it first:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    echo "  Fedora:        sudo dnf install python3 python3-pip"
    exit 1
fi

PY_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[OK] Found Python $PY_VERSION ($PYTHON)"

# ── Step 2: Install system dependencies ──────────────────────────────
echo ""
echo "── Installing system dependencies ──"
if command -v apt &>/dev/null; then
    echo "[INFO] Detected apt package manager"
    sudo apt update -qq
    sudo apt install -y -qq \
        python3-venv \
        libxcb-xinerama0 \
        libxcb-cursor0 \
        libgl1-mesa-dev \
        libegl1 \
        libxkbcommon0 \
        libdbus-1-3 \
        ufw \
        clamav \
        coreutils \
        2>/dev/null || echo "[WARNING] Some packages may not have installed"
    echo "[OK] System packages installed"
elif command -v dnf &>/dev/null; then
    echo "[INFO] Detected dnf package manager"
    sudo dnf install -y \
        python3-virtualenv \
        mesa-libGL \
        libxkbcommon \
        dbus-libs \
        ufw \
        clamav \
        coreutils \
        2>/dev/null || echo "[WARNING] Some packages may not have installed"
    echo "[OK] System packages installed"
else
    echo "[WARNING] Unknown package manager — install Qt6 dependencies manually"
fi

# ── Step 3: Create virtual environment ───────────────────────────────
echo ""
echo "── Setting up Python virtual environment ──"
if [ ! -d "$VENV_DIR" ]; then
    $PYTHON -m venv "$VENV_DIR"
    echo "[OK] Virtual environment created at $VENV_DIR"
else
    echo "[OK] Virtual environment already exists"
fi

source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip -q

# ── Step 4: Install Python dependencies ──────────────────────────────
echo ""
echo "── Installing Python dependencies ──"
python -m pip install -r "$REPO_ROOT/linux_requirements.txt" -q
echo "[OK] Python packages installed"

# ── Step 5: Run the application ──────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              Starting Sentinel...                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

cd "$REPO_ROOT"
python main.py "$@"