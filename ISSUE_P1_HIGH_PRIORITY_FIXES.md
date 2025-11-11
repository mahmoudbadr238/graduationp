# 🔴 P1 HIGH PRIORITY Issues - Pre-Release Fixes

**Status**: ⚠️ BLOCKING RELEASE  
**Total Issues**: 5  
**Total Effort**: ~75 minutes  
**Deadline**: Before v1.0.0 release

---

## Issue Summary Table

| # | Title | File | Lines | Effort | Risk | Status |
|---|-------|------|-------|--------|------|--------|
| P1-1 | Pip install timeout | `app/utils/gpu_manager.py` | 82-84 | 10 min | High | 🔴 OPEN |
| P1-2 | Path API consistency | `app/application.py` | 72-91 | 20 min | Low | 🔴 OPEN |
| P1-3 | CSV newline handling | `app/ui/backend_bridge.py` | 319+ | 15 min | Low | 🔴 OPEN |
| P1-4 | Admin features gating docs | `SECURITY.md` | - | 20 min | Low | 🔴 OPEN |
| P1-5 | AppImage recipe | `scripts/` | - | 45 min | Medium | 🔴 OPEN |

---

# P1-1: Pip Install Subprocess Timeout

**Component**: GPU Manager  
**File**: `app/utils/gpu_manager.py` (lines 82-84)  
**Issue**: `subprocess.check_call()` has no timeout, can hang indefinitely on network issues  

## Current Code
```python
subprocess.check_call(
    [sys.executable, "-m", "pip", "install", package, "--quiet"]
)
```

## Problem
- If PyPI is unreachable or slow, app freeze
- No user feedback (appears hung)
- Installation could take 10+ minutes on slow connections

## Fix
```python
subprocess.check_call(
    [sys.executable, "-m", "pip", "install", package, "--quiet"],
    timeout=60  # 60 seconds for pip install
)
```

## Testing
```python
def test_gpu_manager_pip_timeout():
    """Verify pip install has timeout"""
    # Mock subprocess to track timeout parameter
    import unittest.mock as mock
    with mock.patch('subprocess.check_call') as mock_call:
        GPUManager.auto_install_package("pynvml")
        # Verify timeout=60 was passed
        args, kwargs = mock_call.call_args
        assert kwargs.get('timeout') == 60
```

---

# P1-2: Path API Consistency

**Component**: Application initialization  
**File**: `app/application.py` (lines 72-91)  
**Issue**: Mixed use of `os.path.dirname/join` and `Path` APIs - inconsistent and cross-platform risky

## Current Code
```python
# ❌ Inconsistent: os.path vs Path
workspace_root = os.path.dirname(sys.executable)
qml_path = os.path.join(workspace_root, "qml")
components_path = os.path.join(qml_path, "components").replace("\\", "/")
```

## Problem
- `os.path.dirname(sys.executable)` on Windows returns `C:\Python313` not app root
- `.replace("\\", "/")` only works on Windows; Unix paths unaffected
- Mixed APIs makes code harder to maintain

## Fix
```python
from pathlib import Path

def _setup_paths(self):
    """Set up QML import paths and working directory."""
    # Get absolute path to workspace root
    if getattr(sys, "frozen", False):
        # PyInstaller bundle
        if hasattr(sys, "_MEIPASS"):
            workspace_root = Path(sys._MEIPASS)
        else:
            workspace_root = Path(sys.executable).parent
    else:
        # Normal Python environment
        workspace_root = Path(__file__).parent.parent

    # Set working directory
    os.chdir(workspace_root)
    print(f"Working directory set to: {workspace_root}")

    # Add QML import paths using Path API
    qml_path = workspace_root / "qml"
    self.engine.addImportPath(str(qml_path))  # Convert to string for Qt

    # Set context properties with cross-platform paths
    components_path = (qml_path / "components").as_posix()
    theme_path = (qml_path / "theme").as_posix()
    self.engine.rootContext().setContextProperty("componentPath", components_path)
    self.engine.rootContext().setContextProperty("themePath", theme_path)

    print(f"QML paths: {self.engine.importPathList()}")
```

## Changes Summary
1. Replace `os.path.dirname/join` with `Path` operators
2. Use `Path.as_posix()` for forward slashes (cross-platform)
3. Use `str(Path)` when passing to Qt APIs
4. Single code path for workspace root detection

## Testing
```python
def test_application_path_setup():
    """Verify paths are set correctly"""
    from app.application import DesktopSecurityApplication
    from pathlib import Path
    
    app = DesktopSecurityApplication()
    
    # Verify working directory
    assert Path.cwd() == Path(__file__).parent.parent.parent
    
    # Verify QML path exists
    qml_path = Path.cwd() / "qml"
    assert qml_path.exists()
```

---

# P1-3: CSV Newline Handling

**Component**: Backend Bridge  
**File**: `app/ui/backend_bridge.py` (CSV export methods)  
**Issue**: No explicit `newline=''` parameter in `open()` - causes extra blank lines on Windows

## Current Code
```python
Path(path).parent.mkdir(parents=True, exist_ok=True)
# Missing: newline='' for CSV
with open(path, 'w', encoding='utf-8') as f:
    writer = csv.writer(f)
    # ... write CSV
```

## Problem
- Windows: `\n` is converted to `\r\n`, CSV writer ALSO adds `\r\n` → `\r\r\n` (extra blank lines)
- CSV RFC 4180 requires Unix newlines internally
- Exported files have unnecessary blank rows between data rows

## Fix
```python
import csv
from pathlib import Path

# Find all CSV export methods and add newline=''
Path(path).parent.mkdir(parents=True, exist_ok=True)
with open(path, 'w', encoding='utf-8', newline='') as f:  # ✅ Add newline=''
    writer = csv.writer(f)
    # ... write CSV
```

## Affected Methods
Search `app/ui/backend_bridge.py` for all `csv.writer` calls:
- `exportScanHistoryCSV()`
- `exportSystemSnapshotCSV()` (if exists)
- Any other CSV export methods

## Testing
```python
import csv
from pathlib import Path
import tempfile

def test_csv_export_no_blank_lines():
    """Verify CSV doesn't have blank rows"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', newline='', delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(['header1', 'header2'])
        writer.writerow(['data1', 'data2'])
        temp_path = f.name
    
    try:
        # Read back and verify no extra newlines
        with open(temp_path, 'r') as f:
            lines = f.readlines()
        
        # Should be exactly 2 lines (header + data), no blanks
        assert len([l for l in lines if l.strip()]) == 2
    finally:
        Path(temp_path).unlink()
```

---

# P1-4: Admin Features Gating Documentation

**Component**: Security Policy  
**File**: `SECURITY.md` (Feature requirements section)  
**Issue**: Ambiguous what features require admin; users confused about degraded mode

## Current Text (lines 38-50)
```markdown
**Why**: These features require elevated access on Windows. Without admin rights, 
security monitoring is degraded but the app still functions.
```

## Problem
- Doesn't list WHICH features degrade
- Doesn't explain WHAT happens without admin
- Users may expect all features to work

## Fix
Add explicit table to SECURITY.md:

```markdown
## Administrator Privileges

Sentinel requests (but does not require) administrator privileges on Windows.

### Features Requiring Admin
The following features require elevated access and are **unavailable without admin**:

| Feature | Why | Fallback |
|---------|-----|----------|
| Windows Defender Status | Requires WMI access | Shows "Unavailable" |
| Windows Firewall Status | Requires netsh/registry access | Shows "Unavailable" |
| BitLocker Encryption Status | Requires manage-bde access | Shows "Unavailable" |
| TPM Status | Requires WMI/registry access | Shows "Unavailable" |
| Secure Boot Status | Requires WMI/registry access | Shows "Unavailable" |
| Event Viewer | Requires Windows Event Log API | Page shows "Admin required" |
| UAC Status | Requires registry access | Shows "Unavailable" |

### Features Working Without Admin
All other features work normally without admin:
- ✅ CPU, Memory, GPU, Disk monitoring
- ✅ Network adapter information
- ✅ Running processes list
- ✅ Network port monitoring
- ✅ System information
- ✅ Application settings and UI

### Running Without Admin
To run without admin privileges:
1. Start the app normally (click on shortcut)
2. When prompted by UAC, click "No" or close the dialog
3. App will display warnings for unavailable features
4. Core monitoring remains fully functional
```

## Changes Summary
1. Add Features Requiring Admin table
2. Add Features Working Without Admin list
3. Add instructions for running without admin
4. Update UI to show clear error messages for unavailable features

## UI Changes Needed
```qml
// qml/components/FeatureUnavailableOverlay.qml - new component
import QtQuick
import "../theme"

Rectangle {
    color: Theme.panel
    border.color: Theme.warning
    
    Text {
        text: "This feature requires Administrator privileges"
        color: Theme.warning
        anchors.centerIn: parent
    }
}
```

---

# P1-5: AppImage Build Recipe

**Component**: Linux Packaging  
**File**: `scripts/build_appimage.sh` (new file)  
**Issue**: Only Windows (PyInstaller) packaging documented; Linux users must build from source

## Current State
- ✅ `sentinel.spec` - PyInstaller for Windows (.exe)
- ❌ No AppImage recipe - for Linux (.AppImage)
- ❌ No build documentation

## Fix: Create AppImage Build Script

Create `scripts/build_appimage.sh`:
```bash
#!/bin/bash
# Build reproducible AppImage for Linux
set -e

VERSION="1.0.0"
ARCH="${1:-x86_64}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🔨 Building Sentinel AppImage v${VERSION} for ${ARCH}"

# Set reproducible build timestamp
export SOURCE_DATE_EPOCH=$(git log -1 --format=%ct 2>/dev/null || date +%s)
export FORCE_SOURCE_DATE=1

# Clean previous builds
rm -rf "${REPO_ROOT}/build/appimage" "${REPO_ROOT}/dist/Sentinel*.AppImage"*

# Create AppDir structure
mkdir -p AppDir/usr/{bin,lib,share}

echo "📦 Installing Python dependencies..."
python3 -m venv AppDir/usr/opt/sentinel-venv
source AppDir/usr/opt/sentinel-venv/bin/activate
pip install -q --upgrade pip
pip install -q -r "${REPO_ROOT}/requirements.txt"

echo "📋 Copying application files..."
# Copy app source
cp -r "${REPO_ROOT}/app" AppDir/usr/opt/sentinel/
cp -r "${REPO_ROOT}/qml" AppDir/usr/opt/sentinel/
cp "${REPO_ROOT}/main.py" AppDir/usr/opt/sentinel/
cp "${REPO_ROOT}/README.md" AppDir/usr/opt/sentinel/
cp "${REPO_ROOT}/LICENSE" AppDir/usr/opt/sentinel/

echo "🔗 Creating AppImage wrapper script..."
cat > AppDir/usr/bin/sentinel <<'EOF'
#!/bin/bash
APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PYTHONPATH="${APPDIR}/usr/opt/sentinel:${PYTHONPATH}"
exec "${APPDIR}/usr/opt/sentinel-venv/bin/python3" \
    "${APPDIR}/usr/opt/sentinel/main.py" "$@"
EOF
chmod +x AppDir/usr/bin/sentinel

echo "🎨 Creating desktop entry..."
mkdir -p AppDir/usr/share/applications
cat > AppDir/usr/share/applications/sentinel.desktop <<EOF
[Desktop Entry]
Type=Application
Name=Sentinel
Comment=Endpoint Security Suite
Exec=sentinel
Icon=sentinel
Categories=System;Security;Utility;
Terminal=false
EOF

echo "🚀 Building AppImage..."
# Download linuxdeploy if not present
if [ ! -f "linuxdeploy-${ARCH}.AppImage" ]; then
    wget -q "https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-${ARCH}.AppImage"
    chmod +x "linuxdeploy-${ARCH}.AppImage"
fi

# Build AppImage
./linuxdeploy-${ARCH}.AppImage --appdir=AppDir --output=appimage

echo "✅ AppImage built: Sentinel-${VERSION}-${ARCH}.AppImage"
ls -lh Sentinel-*.AppImage
```

Also create `scripts/build_appimage_docker.sh` for reproducible builds:
```bash
#!/bin/bash
# Docker-based reproducible AppImage build

docker run --rm \
    -v "$(pwd):/workspace" \
    -e SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) \
    ubuntu:22.04 \
    bash -c "
        apt-get update && apt-get install -y python3 python3-pip git
        cd /workspace
        bash scripts/build_appimage.sh x86_64
    "
```

## Documentation
Add to `CONTRIBUTING.md`:

```markdown
## Building for Linux

### Prerequisites
- linuxdeploy
- Python 3.10+
- Git

### Building AppImage
```bash
bash scripts/build_appimage.sh x86_64
# Output: dist/Sentinel-1.0.0-x86_64.AppImage
```

### Reproducible Builds
Use Docker for byte-identical builds:
```bash
bash scripts/build_appimage_docker.sh
```

### Testing AppImage
```bash
chmod +x Sentinel-*.AppImage
./Sentinel-*.AppImage --diagnose
```

### Installing
```bash
sudo install -D Sentinel-*.AppImage /usr/local/bin/sentinel
sentinel  # Run from anywhere
```
```

---

## Implementation Order

1. **P1-1 (10 min)**: Add timeout to pip install - QUICK WIN
2. **P1-4 (20 min)**: Update SECURITY.md - Documentation
3. **P1-3 (15 min)**: Fix CSV newlines - Search & replace
4. **P1-2 (20 min)**: Refactor path API - Code review required
5. **P1-5 (45 min)**: Create AppImage recipe - Most complex

**Total Time**: ~110 minutes if done sequentially  
**Parallel**: P1-1, P1-3, P1-4 can be done simultaneously = ~60 min total

---

## Pre-Release Checklist

### P1-1: Pip Timeout
- [ ] Add `timeout=60` to subprocess.check_call()
- [ ] Add unit test for timeout handling
- [ ] Test pip install succeeds with timeout
- [ ] Test timeout exception caught properly

### P1-2: Path API
- [ ] Refactor application.py to use Path() only
- [ ] Test on Windows (Python dev environment)
- [ ] Test on Linux (WSL or VM)
- [ ] Verify QML assets still load
- [ ] Check PyInstaller build still works

### P1-3: CSV Newlines
- [ ] Find all csv.writer() calls
- [ ] Add `newline=''` parameter
- [ ] Test CSV export on Windows
- [ ] Test CSV export on Linux
- [ ] Verify no blank lines in output

### P1-4: Admin Docs
- [ ] Add Features Requiring Admin table to SECURITY.md
- [ ] Add Features Working Without Admin list
- [ ] Update UI error messages for unavailable features
- [ ] Test running without admin
- [ ] Verify error messages display

### P1-5: AppImage
- [ ] Create scripts/build_appimage.sh
- [ ] Test build on Ubuntu 22.04
- [ ] Verify AppImage runs
- [ ] Test --diagnose flag works
- [ ] Document in CONTRIBUTING.md
- [ ] Create GitHub Actions workflow

---

## Release Blockers Summary

| Issue | Blocks Release | Must Fix | Can Defer |
|-------|---|---|---|
| P1-1 Pip Timeout | NO | ✅ | ❌ |
| P1-2 Path API | NO | ✅ | ❌ |
| P1-3 CSV Newlines | NO | ✅ | ❌ |
| P1-4 Admin Docs | NO | ✅ | ❌ |
| P1-5 AppImage | YES | ⚠️ | Windows only OK for v1.0 |

**Recommendation**: Fix P1-1 through P1-4 before v1.0.0. P1-5 (AppImage) can be v1.0.1 for Linux users.

---

**Priority**: 🔴 HIGH  
**Total Effort**: 110 min (sequential) / 60 min (parallel)  
**Release Impact**: BLOCKING  
**Required**: YES before v1.0.0  

**By**: Principal Engineer  
**Date**: November 11, 2025
