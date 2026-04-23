"""Diagnostic utility for Sentinel - smoke test and version checks."""

import logging
import os
import platform
import shutil
import sys
from typing import Any

from backend.runtime import resolve_bundle_path

logger = logging.getLogger(__name__)


def _collect_privileges(os_name: str) -> str:
    """Return the current privilege level using the correct platform helper."""
    try:
        if os_name == "Windows":
            from backend.infra.privileges import is_admin as _is_admin

            return "administrator" if _is_admin() else "standard_user"
        if os_name == "Linux":
            from backend.platform.linux.admin import check_admin as _is_admin

            return "root" if _is_admin() else "standard_user"
    except ImportError:
        return "unknown"
    return "unknown"


def _dependency_specs(os_name: str) -> dict[str, dict[str, Any]]:
    """Return dependency checks relevant to the current platform."""
    deps = {
        "PySide6": {"description": "Qt framework for GUI", "optional": False},
        "psutil": {"description": "System monitoring", "optional": False},
        "pynvml": {"description": "NVIDIA GPU monitoring", "optional": True},
    }
    if os_name == "Windows":
        deps["pywin32"] = {
            "description": "Windows Event Log integration",
            "optional": True,
            "import_name": "pythoncom",
        }
        deps["wmi"] = {
            "description": "WMI bindings for Windows RTP",
            "optional": True,
        }
    return deps


def _collect_dependency_status(
    dependency_specs: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Import each dependency and return normalized status information."""
    dependency_status: dict[str, dict[str, Any]] = {}
    for module, info in dependency_specs.items():
        try:
            import_name = info.get("import_name", module)
            mod = __import__(import_name)
            version = getattr(mod, "__version__", "unknown")
            dependency_status[module] = {
                "version": version,
                "status": "ok",
            }
        except ImportError:
            dependency_status[module] = {
                "status": "not_found",
                "optional": info["optional"],
            }
    return dependency_status


def _build_feature_status(
    os_name: str,
    dependencies: dict[str, dict[str, Any]],
    *,
    groq_configured: bool,
) -> dict[str, dict[str, str]]:
    """Describe feature availability without pretending optional paths are healthy."""
    features: dict[str, dict[str, str]] = {}

    if os_name == "Windows":
        pywin32_ready = dependencies.get("pywin32", {}).get("status") == "ok"
        wmi_ready = dependencies.get("wmi", {}).get("status") == "ok"
        features["event_logs"] = {
            "label": "Windows Event Log",
            "status": "available" if pywin32_ready else "degraded",
            "detail": (
                "Event Viewer can read Windows Event Log"
                if pywin32_ready
                else "pywin32 is missing; Windows Event Log support is limited"
            ),
        }
        features["real_time_protection"] = {
            "label": "Real-Time Protection",
            "status": "available" if pywin32_ready and wmi_ready else "degraded",
            "detail": (
                "Windows RTP can monitor new process launches"
                if pywin32_ready and wmi_ready
                else "Windows RTP is limited until pywin32 and wmi are installed"
            ),
        }
    elif os_name == "Linux":
        journalctl_ready = shutil.which("journalctl") is not None
        features["event_logs"] = {
            "label": "systemd journal",
            "status": "available" if journalctl_ready else "degraded",
            "detail": (
                "Event Viewer can read systemd journal entries"
                if journalctl_ready
                else "journalctl is unavailable; Linux event log support is limited"
            ),
        }
        features["real_time_protection"] = {
            "label": "Real-Time Protection",
            "status": "available",
            "detail": "Linux RTP can monitor new process launches via process polling",
        }

    features["cloud_ai"] = {
        "label": "Groq AI",
        "status": "available" if groq_configured else "disabled",
        "detail": (
            "Groq-backed AI features are enabled"
            if groq_configured
            else "Set GROQ_API_KEY to enable cloud AI features"
        ),
    }
    return features


def _has_degraded_features(features: dict[str, dict[str, str]]) -> bool:
    """Return True when a feature is degraded, not merely disabled by config."""
    return any(feature.get("status") == "degraded" for feature in features.values())


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
    os_name = diagnostics["system"]["os"]

    # Admin status
    diagnostics["privileges"] = _collect_privileges(os_name)

    # Version info
    try:
        from backend.__version__ import APP_FULL_NAME, __version__

        diagnostics["application"] = {
            "name": APP_FULL_NAME,
            "version": __version__,
        }
    except ImportError as e:
        diagnostics["application"] = {"error": str(e)}

    # Dependencies
    deps = _dependency_specs(os_name)
    diagnostics["dependencies"] = _collect_dependency_status(deps)
    diagnostics["features"] = _build_feature_status(
        os_name,
        diagnostics["dependencies"],
        groq_configured=bool(os.environ.get("GROQ_API_KEY", "").strip()),
    )

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
    qml_path = resolve_bundle_path("frontend", "qml", "main.qml")
    diagnostics["paths"] = {
        "qml_entry": str(qml_path),
        "qml_exists": qml_path.exists(),
    }

    # Optional integrations
    try:
        from backend.infra.integrations import get_clamav_status, nmap_available

        diagnostics["integrations"] = {
            "nmap_available": nmap_available(),
            "clamav_status": get_clamav_status(),
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
    print(
        f"  OS: {sys_info.get('os')} {sys_info.get('os_version')} ({sys_info.get('architecture')})"
    )
    print(f"  Python: {sys_info.get('python_version')}")
    print(f"  Executable: {sys_info.get('python_executable')}")
    priv = diags.get("privileges", "unknown")
    admin_marker = "[OK]" if priv in {"administrator", "root"} else "[WARNING]"
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

    print("Feature Availability:")
    features = diags.get("features", {})
    for feature in features.values():
        status = feature.get("status", "unknown")
        if status == "available":
            marker = "[OK]"
        elif status == "disabled":
            marker = "[INFO]"
        else:
            marker = "[WARNING]"
        print(f"  {marker} {feature.get('label')}: {feature.get('detail')}")
    if not features:
        print("  [INFO] No feature-specific checks available")
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
    else:
        print(f"  [WARNING] Could not check integrations: {integrations['error']}")

    degraded_features = _has_degraded_features(features)
    if all_ok and not degraded_features:
        print("=" * 60)
        print("[OK] DIAGNOSTICS PASSED - Application should run successfully")
        print("=" * 60)
        return 0
    if all_ok:
        print("=" * 60)
        print("[WARNING] DIAGNOSTICS PASSED WITH DEGRADED FEATURES")
        print("=" * 60)
        return 0
    print("=" * 60)
    print("[ERROR] DIAGNOSTICS FAILED - Fix errors above before running")
    print("=" * 60)
    return 1
