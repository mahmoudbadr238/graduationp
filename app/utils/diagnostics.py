"""Diagnostic utility for Sentinel - smoke test and version checks"""

import logging
import platform
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def run_diagnostics() -> int:
    """Run diagnostic smoke test and print system information.

    Returns:
        0 if successful, 1 if any critical errors
    """
    print("\n" + "=" * 60)
    print("SENTINEL DIAGNOSTICS")
    print("=" * 60 + "\n")

    # System info
    print("System Information:")
    print(f"  OS: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  Executable: {sys.executable}")

    # Admin status
    try:
        from app.infra.privileges import is_admin

        admin_status = "✓ Administrator" if is_admin() else "⚠ Standard user"
        print(f"  Privileges: {admin_status}")
    except ImportError:
        print("  Privileges: ⚠ Could not determine")

    print()

    # Version info
    try:
        from app.__version__ import APP_FULL_NAME, __version__

        print(f"Application: {APP_FULL_NAME} v{__version__}")
    except ImportError as e:
        print(f"❌ Failed to import version: {e}")
        return 1

    print()

    # Dependencies
    print("Core Dependencies:")
    deps = {
        "PySide6": "Qt framework for GUI",
        "psutil": "System monitoring",
        "pynvml": "NVIDIA GPU monitoring (optional)",
        "pywin32": "Windows API access (optional)",
    }

    all_ok = True
    for module, desc in deps.items():
        try:
            mod = __import__(module)
            version = getattr(mod, "__version__", "unknown")
            print(f"  ✓ {module:15} {version:15} - {desc}")
        except ImportError:
            optional = "(optional)" in desc
            marker = "⚠" if optional else "❌"
            print(f"  {marker} {module:15} {'NOT FOUND':15} - {desc}")
            if not optional:
                all_ok = False

    print()

    # Smoke test: collect basic metrics
    print("Smoke Test - Collecting Metrics:")
    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        print(f"  ✓ CPU Usage: {cpu_percent:.1f}%")
        print(
            f"  ✓ Memory: {mem.percent:.1f}% used ({mem.used // (1024**3)}GB / {mem.total // (1024**3)}GB)"
        )
    except (ImportError, OSError, RuntimeError) as e:  # Specific psutil errors
        print(f"  ❌ psutil failed: {e}")
        all_ok = False

    # GPU test (optional)
    try:
        import pynvml

        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        print(f"  ✓ NVIDIA GPUs detected: {count}")
        for i in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            print(f"    - GPU {i}: {name}")
        pynvml.nvmlShutdown()
    except ImportError:
        print("  ⚠ pynvml not available (NVIDIA GPU monitoring disabled)")
    except (OSError, RuntimeError) as e:  # Specific NVML errors
        print(f"  ⚠ GPU detection failed: {e}")

    # QML paths
    print()
    print("Resource Paths:")
    # Root is the workspace root (one level up from app/)
    root = Path(__file__).resolve().parents[2]
    qml_path = root / "qml" / "main.qml"
    if qml_path.exists():
        print(f"  ✓ QML entry: {qml_path}")
    else:
        print(f"  ❌ QML entry not found: {qml_path}")
        all_ok = False

    # Database path
    db_path = Path.home() / ".sentinel"
    print(f"  ✓ Database dir: {db_path}")

    # Optional integrations
    print()
    print("Optional Integrations:")
    try:
        from app.infra.integrations import nmap_available, virustotal_enabled

        if nmap_available():
            print("  ✓ Nmap: Available for network scanning")
        else:
            print("  ⚠ Nmap: Not found (network scanning disabled)")

        if virustotal_enabled():
            print("  ✓ VirusTotal: API key configured")
        else:
            print("  ⚠ VirusTotal: VT_API_KEY not set (file/URL scanning limited)")
    except ImportError as e:
        print(f"  ⚠ Could not check integrations: {e}")

    print()
    if all_ok:
        print("=" * 60)
        print("✓ DIAGNOSTICS PASSED - Application should run successfully")
        print("=" * 60)
        return 0
    print("=" * 60)
    print("❌ DIAGNOSTICS FAILED - Fix errors above before running")
    print("=" * 60)
    return 1
