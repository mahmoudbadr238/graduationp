#!/bin/bash
# Sentinel - Endpoint Security Suite
# Linux run script

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Sentinel - Endpoint Security Suite v1.0.0${NC}"
echo "================================================"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    echo "Install Python 3.10+ using your package manager:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "  Fedora: sudo dnf install python3 python3-pip"
    echo "  Arch: sudo pacman -S python python-pip"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "Python version: ${GREEN}$PYTHON_VERSION${NC}"

# Check if virtualenv exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv .venv
fi

# Activate virtualenv
echo "Activating virtual environment..."
source .venv/bin/activate

# Install/upgrade dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Check if psutil is installed
if ! python3 -c "import psutil" &> /dev/null; then
    echo -e "${RED}Error: psutil not installed${NC}"
    echo "Installing psutil..."
    pip install psutil
fi

# Check if PySide6 is installed
if ! python3 -c "import PySide6" &> /dev/null; then
    echo -e "${RED}Error: PySide6 not installed${NC}"
    echo "Installing PySide6..."
    pip install PySide6
fi

echo ""
echo -e "${GREEN}Starting Sentinel...${NC}"
echo ""

# Run the application
python3 main.py

# Deactivate virtualenv on exit
deactivate
