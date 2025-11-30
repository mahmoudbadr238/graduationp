"""Diagnostic utility for Sentinel - smoke test and version checks"""

import logging
import platform
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def collect_diagnostics() -> dict[str, Any]:
    """Collect diagnostic information as a dictionary.

    Returns:
        Dictionary with all diagnostic data (for JSON export or display).
    """
    diagnostics: dict[str, Any] = {}

    # System info
    diagnostics["system"] = {
        "os": platform.system(),
        "os_version": platform.release(),
        "architecture": platform.machine(),
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
    }

    # Admin status
    try:
        from app.infra.privileges import is_admin

        diagnostics["privileges"] = "administrator" if is_admin() else "standard_user"
    except ImportError:
        diagnostics["privileges"] = "unknown"

    # Version info
    try:
        from app.__version__ import APP_FULL_NAME, __version__

        diagnostics["application"] = {
            "name": APP_FULL_NAME,
            "version": __version__,
        }
    except ImportError as e:
        diagnostics["application"] = {"error": str(e)}

    # Dependencies
    deps = {
        "PySide6": {"description": "Qt framework for GUI", "optional": False},
        "psutil": {"description": "System monitoring", "optional": False},
        "pynvml": {"description": "NVIDIA GPU monitoring", "optional": True},
        "pywin32": {"description": "Windows API access", "optional": True},
    }

    diagnostics["dependencies"] = {}
    for module, info in deps.items():
        try:
            mod = __import__(module)
            version = getattr(mod, "__version__", "unknown")
            diagnostics["dependencies"][module] = {
                "version": version,
                "status": "ok",
            }
        except ImportError:
            diagnostics["dependencies"][module] = {
                "status": "not_found",
                "optional": info["optional"],
            }

    # Smoke test: collect metrics
    diagnostics["metrics"] = {}
    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        diagnostics["metrics"]["cpu_percent"] = cpu_percent
        diagnostics["metrics"]["memory_percent"] = mem.percent
        diagnostics["metrics"]["memory_used_gb"] = mem.used // (1024**3)
        diagnostics["metrics"]["memory_total_gb"] = mem.total // (1024**3)
    except (ImportError, OSError, RuntimeError) as e:
        diagnostics["metrics"]["error"] = str(e)

    # GPU test (optional)
    diagnostics["gpu"] = {}
    try:
        import pynvml

        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        diagnostics["gpu"]["count"] = count
        gpus = []
        for i in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            gpus.append({"index": i, "name": name})
        diagnostics["gpu"]["devices"] = gpus
        pynvml.nvmlShutdown()
    except ImportError:
        diagnostics["gpu"]["status"] = "not_available"
    except Exception as e:
        # Catch all pynvml errors (NVMLError_LibraryNotFound, etc.)
        diagnostics["gpu"]["status"] = "not_available"
        diagnostics["gpu"]["error"] = str(e)

    # QML paths
    root = Path(__file__).resolve().parents[2]
    qml_path = root / "qml" / "main.qml"
    diagnostics["paths"] = {
        "qml_entry": str(qml_path),
        "qml_exists": qml_path.exists(),
    }

    # Optional integrations
    try:
        from app.infra.integrations import nmap_available, virustotal_enabled

        diagnostics["integrations"] = {
            "nmap_available": nmap_available(),
            "virustotal_available": virustotal_enabled(),
        }
    except ImportError as e:
        diagnostics["integrations"] = {"error": str(e)}

    return diagnostics



def run_diagnostics() -> int:
    """Run diagnostic smoke test and print system information.

    Returns:
        0 if successful, 1 if any critical errors
    """
    diags = collect_diagnostics()

    print("\n" + "=" * 60)
    print("SENTINEL DIAGNOSTICS")
    print("=" * 60 + "\n")

    # System info
    print("System Information:")
    sys_info = diags.get("system", {})
    print(f"  OS: {sys_info.get('os')} {sys_info.get('os_version')} ({sys_info.get('architecture')})")
    print(f"  Python: {sys_info.get('python_version')}")
    print(f"  Executable: {sys_info.get('python_executable')}")
    priv = diags.get("privileges", "unknown")
    admin_marker = "[OK]" if priv == "administrator" else "[WARNING]"
    print(f"  Privileges: {admin_marker} {priv}")
    print()

    # Application version
    app = diags.get("application", {})
    if "name" in app:
        print(f"Application: {app.get('name')} v{app.get('version')}")
    print()

    # Dependencies
    print("Core Dependencies:")
    deps = diags.get("dependencies", {})
    all_ok = True
    for module, info in deps.items():
        if info.get("status") == "ok":
            version = info.get("version", "unknown")
            print(f"  [OK] {module:15} {version:15}")
        else:
            optional = info.get("optional", False)
            marker = "[WARNING]" if optional else "[ERROR]"
            print(f"  {marker} {module:15} {'NOT FOUND':15}")
            if not optional:
                all_ok = False
    print()

    # Metrics
    print("Smoke Test - Collecting Metrics:")
    metrics = diags.get("metrics", {})
    if "error" not in metrics:
        print(f"  [OK] CPU Usage: {metrics.get('cpu_percent', 0):.1f}%")
        print(
            f"  [OK] Memory: {metrics.get('memory_percent', 0):.1f}% used "
            f"({metrics.get('memory_used_gb', 0)}GB / {metrics.get('memory_total_gb', 0)}GB)"
        )
    else:
        print(f"  [ERROR] Failed to collect metrics: {metrics['error']}")
        all_ok = False

    # GPU
    gpu = diags.get("gpu", {})
    if "count" in gpu:
        print(f"  [OK] NVIDIA GPUs detected: {gpu.get('count')}")
        for dev in gpu.get("devices", []):
            print(f"    - GPU {dev['index']}: {dev['name']}")
    elif "status" in gpu:
        print(f"  [WARNING] {gpu['status']}")
    elif "error" not in gpu:
        print("  [WARNING] GPU detection not available")

    # Paths
    print()
    print("Resource Paths:")
    paths = diags.get("paths", {})
    if paths.get("qml_exists"):
        print(f"  [OK] QML entry: {paths.get('qml_entry')}")
    else:
        print(f"  [ERROR] QML entry not found: {paths.get('qml_entry')}")
        all_ok = False

    # Optional integrations
    print()
    print("Optional Integrations:")
    integrations = diags.get("integrations", {})
    if "error" not in integrations:
        if integrations.get("nmap_available"):
            print("  [OK] Nmap: Available for network scanning")
        else:
            print("  [WARNING] Nmap: Not found (network scanning disabled)")

        if integrations.get("virustotal_available"):
            print("  [OK] VirusTotal: API key configured")
        else:
            print("  [WARNING] VirusTotal: VT_API_KEY not set (file/URL scanning limited)")
    else:
        print(f"  [WARNING] Could not check integrations: {integrations['error']}")

    print()
    if all_ok:
        print("=" * 60)
        print("[OK] DIAGNOSTICS PASSED - Application should run successfully")
        print("=" * 60)
        return 0
    print("=" * 60)
    print("[ERROR] DIAGNOSTICS FAILED - Fix errors above before running")
    print("=" * 60)
    return 1
