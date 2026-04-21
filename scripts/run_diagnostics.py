#!/usr/bin/env python
"""
Sentinel Pre-Flight Diagnostic Suite
=====================================
Validates the ENTIRE Sentinel architecture before launch:
  1. System & Privilege Hooks  (Admin, pip packages)
  2. Backend Service Integration  (WMI, Defender CLI, Firewall)
  3. API & AI Automation  (.env keys, Groq reachability, agent payload)
  4. UI / QML Compilation  (headless QQmlEngine validation)

Run:
    python run_diagnostics.py          # normal
    python run_diagnostics.py -v       # verbose (show PASS detail)

Requires: colorama  (pip install colorama)
"""

from __future__ import annotations

import argparse
import importlib
import io
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

_IS_WINDOWS = sys.platform == "win32"
_IS_LINUX = sys.platform.startswith("linux")

if _IS_WINDOWS:
    import ctypes

# Force UTF-8 stdout/stderr so any stray Unicode doesn't crash on cp1252
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True,
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True,
    )

# -- colorama bootstrap ------------------------------------------------------
try:
    from colorama import Fore, Style, init as colorama_init

    colorama_init(autoreset=True)
except ImportError:
    print("[FATAL] colorama is not installed.  Run:  pip install colorama")
    sys.exit(1)


# -- Globals -----------------------------------------------------------------
WORKSPACE = Path(__file__).resolve().parent
RESULTS: List[Tuple[str, bool, str, str]] = []  # (name, passed, detail, action)
VERBOSE = False


# -- Utility -----------------------------------------------------------------
def _pass(name: str, detail: str = "") -> None:
    RESULTS.append((name, True, detail, ""))
    if VERBOSE:
        print(f"  {Fore.GREEN}[PASS]{Style.RESET_ALL}  {name}" + (f"  -- {detail}" if detail else ""))


def _fail(name: str, detail: str, action: str) -> None:
    RESULTS.append((name, False, detail, action))
    print(f"  {Fore.RED}[FAIL]{Style.RESET_ALL}  {name}  -- {detail}")


def _warn(name: str, detail: str, action: str = "") -> None:
    RESULTS.append((name, True, detail, action))  # warnings count as pass
    print(f"  {Fore.YELLOW}[WARN]{Style.RESET_ALL}  {name}  -- {detail}")


def _header(title: str) -> None:
    width = 64
    print()
    print(f"{Fore.CYAN}{'-' * width}")
    print(f"  {title}")
    print(f"{'-' * width}{Style.RESET_ALL}")


# ===========================================================================
# 1. SYSTEM & PRIVILEGE HOOK TESTS
# ===========================================================================
def test_admin_privileges() -> None:
    """Check if the process is running with elevated privileges."""
    if _IS_WINDOWS:
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            is_admin = False

        if is_admin:
            _pass("Administrator privileges", "Running elevated")
        else:
            _fail(
                "Administrator privileges",
                "NOT running as Administrator",
                "ACTION: Right-click terminal -> 'Run as administrator', or use scripts/run_as_admin.bat",
            )
    else:
        # Linux / macOS
        is_root = os.geteuid() == 0
        if is_root:
            _pass("Root privileges", "Running as root")
        else:
            _warn(
                "Root privileges",
                "NOT running as root — some diagnostics may be limited",
                "ACTION: Re-run with 'sudo python run_diagnostics.py'",
            )


# Packages grouped by purpose so the report is useful
_COMMON_PACKAGES = {
    # pip-name  ->  import-name
    "PySide6": "PySide6",
    "psutil": "psutil",
    "requests": "requests",
    "colorama": "colorama",
    "python-dotenv": "dotenv",
    "pefile": "pefile",
    "groq": "groq",
    "aiohttp": "aiohttp",
    "GPUtil": "GPUtil",
    "nvidia-ml-py": "pynvml",
}

_WINDOWS_ONLY_PACKAGES = {
    "wmi": "wmi",
    "pywin32": "win32api",
}

REQUIRED_PACKAGES = {**_COMMON_PACKAGES}
if _IS_WINDOWS:
    REQUIRED_PACKAGES.update(_WINDOWS_ONLY_PACKAGES)


def test_pip_packages() -> None:
    """Verify every critical pip dependency can be imported."""
    for pip_name, import_name in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(import_name)
            _pass(f"Package: {pip_name}")
        except ImportError:
            _fail(
                f"Package: {pip_name}",
                f"Cannot import '{import_name}'",
                f"ACTION: pip install {pip_name}",
            )


# ===========================================================================
# 2. BACKEND SERVICE INTEGRATION TESTS
# ===========================================================================
def test_wmi_security_center() -> None:
    """Connect to ROOT\\SecurityCenter2 and query AntiVirusProduct (Windows only)."""
    if not _IS_WINDOWS:
        _warn("WMI SecurityCenter2", "Skipped — Windows-only test",
              "Linux uses ClamAV / custom AV integration instead")
        return

    try:
        import wmi as wmi_mod

        conn = wmi_mod.WMI(namespace=r"root\SecurityCenter2")
        products = conn.AntiVirusProduct()
        names = [p.displayName for p in products] if products else []
        if names:
            _pass("WMI SecurityCenter2", f"AV products: {', '.join(names)}")
        else:
            _warn(
                "WMI SecurityCenter2",
                "Connected, but no AntiVirusProduct entries found",
                "ACTION: Ensure an antivirus is registered with Windows Security Center",
            )
    except ImportError:
        _fail(
            "WMI SecurityCenter2",
            "wmi package not installed",
            "ACTION: pip install wmi pywin32",
        )
    except Exception as exc:
        _fail(
            "WMI SecurityCenter2",
            f"Connection failed: {exc}",
            "ACTION: Run as Administrator; verify WMI service is running (services.msc -> 'Windows Management Instrumentation')",
        )


def test_defender_cli() -> None:
    """Run MpCmdRun.exe -h and verify returncode 0 (Windows only)."""
    if not _IS_WINDOWS:
        _warn("Defender CLI (MpCmdRun)", "Skipped — Windows-only test",
              "Linux uses ClamAV (clamscan / freshclam) instead")
        return

    mpcmd = os.path.join(
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        "Windows Defender",
        "MpCmdRun.exe",
    )
    if not os.path.isfile(mpcmd):
        _fail(
            "Defender CLI (MpCmdRun)",
            f"Executable not found at: {mpcmd}",
            "ACTION: Install / enable Windows Defender, or verify ProgramFiles path",
        )
        return

    try:
        result = subprocess.run(
            [mpcmd, "-h"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0:
            _pass("Defender CLI (MpCmdRun)", f"Help text OK ({len(result.stdout)} bytes)")
        else:
            _fail(
                "Defender CLI (MpCmdRun)",
                f"Returned exit code {result.returncode}",
                "ACTION: Ensure Windows Defender is enabled and MpCmdRun is accessible",
            )
    except subprocess.TimeoutExpired:
        _fail(
            "Defender CLI (MpCmdRun)",
            "Command timed out after 15s",
            "ACTION: Check if Defender service is hung; restart 'WinDefend' service",
        )
    except Exception as exc:
        _fail(
            "Defender CLI (MpCmdRun)",
            f"Execution error: {exc}",
            "ACTION: Run as Administrator; ensure Defender has not been uninstalled by Group Policy",
        )


def test_firewall_service() -> None:
    """Check the firewall service for the current platform."""
    if _IS_WINDOWS:
        _test_firewall_windows()
    elif _IS_LINUX:
        _test_firewall_linux()
    else:
        _warn("Firewall service", "Unknown platform — skipped")


def _test_firewall_windows() -> None:
    """Check the Windows Firewall service (mpssvc) via psutil."""
    try:
        import psutil

        service_names = {s.name().lower() for s in psutil.win_service_iter()}
        if "mpssvc" in service_names:
            svc = psutil.win_service_get("mpssvc")
            info = svc.as_dict()
            status = info.get("status", "unknown")
            if status == "running":
                _pass("Firewall service (mpssvc)", "Running")
            else:
                _warn(
                    "Firewall service (mpssvc)",
                    f"Service exists but status is '{status}'",
                    "ACTION: Run 'net start mpssvc' as Administrator",
                )
        else:
            _fail(
                "Firewall service (mpssvc)",
                "Service not found in psutil service list",
                "ACTION: Windows Firewall service may have been removed or renamed",
            )
    except ImportError:
        _fail(
            "Firewall service (mpssvc)",
            "psutil not installed",
            "ACTION: pip install psutil",
        )
    except Exception as exc:
        _fail(
            "Firewall service (mpssvc)",
            f"psutil error: {exc}",
            "ACTION: Run as Administrator to access service information",
        )


def _test_firewall_linux() -> None:
    """Check if UFW or firewalld is active on Linux."""
    # Try UFW first
    try:
        result = subprocess.run(
            ["ufw", "status"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and "active" in result.stdout.lower():
            _pass("Firewall service (UFW)", "UFW is active")
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try firewalld
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "firewalld"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            _pass("Firewall service (firewalld)", "firewalld is active")
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try iptables
    try:
        result = subprocess.run(
            ["iptables", "-L", "-n"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            _pass("Firewall service (iptables)", "iptables rules present")
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    _warn(
        "Firewall service",
        "No active firewall detected (UFW, firewalld, or iptables)",
        "ACTION: Install and enable a firewall — e.g. 'sudo apt install ufw && sudo ufw enable'",
    )


# ===========================================================================
# 3. API & AI AUTOMATION TESTS
# ===========================================================================
def test_env_file() -> Tuple[dict, bool]:
    """Read .env and verify critical API keys are present and non-empty.

    Returns (env_dict, groq_key_present) for downstream tests.
    """
    env_path = WORKSPACE / ".env"
    env_vars: dict = {}
    groq_ok = False

    if not env_path.exists():
        _fail(
            ".env file exists",
            f"Not found at {env_path}",
            "ACTION: Copy .env.example to .env and fill in your API keys",
        )
        return env_vars, groq_ok

    _pass(".env file exists")

    # Parse key=value lines (simple; honours quotes & comments)
    with open(env_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            env_vars[key] = value

    # --- Check GROQ_API_KEY ---
    groq_key = env_vars.get("GROQ_API_KEY", "")
    if groq_key:
        _pass("GROQ_API_KEY", f"Present ({len(groq_key)} chars)")
        groq_ok = True
    else:
        _fail(
            "GROQ_API_KEY",
            "Key is empty or missing in .env",
            "ACTION: Edit .env -> set GROQ_API_KEY=gsk_... (get one at https://console.groq.com/)",
        )

    return env_vars, groq_ok


def test_groq_reachability(api_key: str) -> None:
    """Send a minimal models-list request to Groq to verify connectivity."""
    try:
        import requests
    except ImportError:
        _fail("Groq API reachability", "requests not installed", "ACTION: pip install requests")
        return

    url = "https://api.groq.com/openai/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Sentinel-Enterprise-Agent/1.0",
        "Accept": "application/json",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            _pass("Groq API reachability", f"HTTP 200 -- {len(resp.json().get('data', []))} models listed")
        elif resp.status_code == 401:
            _fail(
                "Groq API reachability",
                "HTTP 401 -- Invalid API key",
                "ACTION: Edit .env -> replace GROQ_API_KEY with a valid key from https://console.groq.com/",
            )
        elif resp.status_code == 403:
            _fail(
                "Groq API reachability",
                "HTTP 403 -- Cloudflare / endpoint blocked",
                "ACTION: Check network/proxy settings; the Groq API may be geo-blocked or firewalled",
            )
        else:
            _fail(
                "Groq API reachability",
                f"HTTP {resp.status_code} -- {resp.text[:120]}",
                "ACTION: Investigate Groq API status at https://status.groq.com/",
            )
    except requests.exceptions.Timeout:
        _fail(
            "Groq API reachability",
            "Timed out after 5s",
            "ACTION: Check internet connectivity and DNS resolution for api.groq.com",
        )
    except requests.exceptions.ConnectionError as exc:
        _fail(
            "Groq API reachability",
            f"Connection error: {exc}",
            "ACTION: Check internet connectivity; ensure api.groq.com is not blocked by firewall/proxy",
        )
    except Exception as exc:
        _fail(
            "Groq API reachability",
            f"Unexpected error: {exc}",
            "ACTION: Review network configuration",
        )


def test_agent_payload() -> None:
    """Verify the sentinel_agent.exe payload exists in the expected location."""
    # Check the source script (always needed for builds)
    source = WORKSPACE / "payload" / "sandbox_agent" / "agent_payload.py"
    if source.exists():
        _pass("Agent source (agent_payload.py)", f"{source.stat().st_size} bytes")
    else:
        _fail(
            "Agent source (agent_payload.py)",
            f"Not found at {source}",
            "ACTION: Restore payload/sandbox_agent/agent_payload.py from version control",
        )

    # Check the compiled exe in common output locations
    exe_candidates = [
        WORKSPACE / "dist" / "sentinel_agent.exe",
        WORKSPACE / "build" / "sentinel_agent" / "sentinel_agent.exe",
        WORKSPACE / "payload" / "sandbox_agent" / "dist" / "sentinel_agent.exe",
    ]
    found = None
    for p in exe_candidates:
        if p.exists():
            found = p
            break

    if found:
        size_mb = found.stat().st_size / (1024 * 1024)
        _pass("Agent payload (sentinel_agent.exe)", f"Found at {found} ({size_mb:.1f} MB)")
    else:
        searched = ", ".join(str(p.parent) for p in exe_candidates)
        _warn(
            "Agent payload (sentinel_agent.exe)",
            f"Compiled exe not found (searched: {searched})",
            "ACTION: Run 'python scripts/build_agent.py' to compile the agent payload",
        )


# ===========================================================================
# 4. UI / QML COMPILATION TEST
# ===========================================================================

QML_ROOT = WORKSPACE / "frontend" / "qml"


def _iter_qml_targets() -> list[str]:
    """Compile the current app shell and all page entrypoints under frontend/qml."""
    targets = ["frontend/qml/main.qml"]
    pages_dir = QML_ROOT / "pages"
    if pages_dir.is_dir():
        targets.extend(
            str(path.relative_to(WORKSPACE)).replace("\\", "/")
            for path in sorted(pages_dir.rglob("*.qml"))
        )
    return targets


def test_qml_compilation() -> None:
    """Instantiate a headless QGuiApplication + QQmlEngine and attempt to
    compile every target QML file.  Reports exact syntax errors with line
    numbers when component.isError() is True."""
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlComponent, QQmlEngine
    except ImportError:
        _fail(
            "QML Engine bootstrap",
            "PySide6 is not installed",
            "ACTION: pip install PySide6",
        )
        return

    # Create headless Qt application (only if one doesn't already exist)
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])

    engine = QQmlEngine()

    # Register the same import paths the real application uses
    qml_root = QML_ROOT
    engine.addImportPath(str(qml_root))
    for subdir in ("components", "pages", "theme", "ui", "ux"):
        p = qml_root / subdir
        if p.is_dir():
            engine.addImportPath(str(p))

    # Also add the frontend/ parent so "import '../components'" works
    engine.addImportPath(str(WORKSPACE / "frontend"))

    qml_pass = 0
    qml_fail = 0

    for rel in _iter_qml_targets():
        qml_path = WORKSPACE / rel
        test_name = f"QML: {rel}"

        if not qml_path.exists():
            _fail(test_name, "File not found", f"ACTION: Restore {rel} from version control")
            qml_fail += 1
            continue

        url = QUrl.fromLocalFile(str(qml_path))
        component = QQmlComponent(engine, url)

        if component.isReady():
            _pass(test_name, "Compiled OK")
            qml_pass += 1
        elif component.isError():
            errors = component.errors()
            error_lines = []
            for err in errors:
                line = err.line()
                col = err.column()
                desc = err.description()
                error_lines.append(f"  Line {line}:{col} -- {desc}")
            detail = "\n".join(error_lines)
            # Extract the first error's line for the action hint
            first_line = errors[0].line() if errors else "?"
            first_desc = errors[0].description() if errors else "unknown"
            _fail(
                test_name,
                f"{len(errors)} error(s):\n{detail}",
                f"ACTION: Fix QML syntax on line {first_line} of {rel} -- {first_desc}",
            )
            qml_fail += 1
        else:
            # Component is loading or has a non-error issue
            _warn(test_name, "Component status is not Ready and not Error (possible async load)")
            qml_pass += 1  # don't count as failure

    if qml_fail == 0:
        print(f"\n  {Fore.GREEN}All {qml_pass} QML files compiled successfully.{Style.RESET_ALL}")
    else:
        print(f"\n  {Fore.RED}{qml_fail} QML file(s) had compilation errors.{Style.RESET_ALL}")

    # Cleanup engine before app teardown
    engine.clearComponentCache()
    del engine


# ===========================================================================
# 5. REPORT GENERATION
# ===========================================================================
def print_report() -> None:
    total = len(RESULTS)
    passed = sum(1 for _, ok, _, _ in RESULTS if ok)
    failed = total - passed
    failures = [(n, d, a) for n, ok, d, a in RESULTS if not ok]

    width = 64
    print()
    print(f"{Fore.CYAN}{'=' * width}")
    print(f"  SENTINEL PRE-FLIGHT DIAGNOSTIC REPORT")
    print(f"{'=' * width}{Style.RESET_ALL}")
    print()

    if failed == 0:
        print(f"  {Fore.GREEN}[OK] ALL TESTS PASSED  [{passed}/{total}]{Style.RESET_ALL}")
        print(f"  {Fore.GREEN}The application is ready to launch.{Style.RESET_ALL}")
    else:
        print(f"  {Fore.RED}[!!] {failed} TEST(S) FAILED  [{passed}/{total} Passed]{Style.RESET_ALL}")
        print()
        print(f"  {Fore.YELLOW}{'-' * width}")
        print(f"  ACTIONS REQUIRED:")
        print(f"  {'-' * width}{Style.RESET_ALL}")
        for i, (name, detail, action) in enumerate(failures, 1):
            print(f"\n  {Fore.RED}{i}. {name}{Style.RESET_ALL}")
            print(f"     Detail : {detail}")
            if action:
                print(f"     {Fore.YELLOW}{action}{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}{'=' * width}{Style.RESET_ALL}\n")


# ===========================================================================
# MAIN
# ===========================================================================
def main() -> None:
    global VERBOSE

    parser = argparse.ArgumentParser(description="Sentinel Pre-Flight Diagnostic Suite")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show PASS detail in output")
    args = parser.parse_args()
    VERBOSE = args.verbose

    print()
    print(f"{Fore.CYAN}{'=' * 64}")
    print(f"  SENTINEL PRE-FLIGHT DIAGNOSTIC SUITE")
    print(f"  Scanning architecture health...")
    print(f"{'=' * 64}{Style.RESET_ALL}")

    start = time.monotonic()

    # -- 1. System & Privilege -----------------------------------------------
    _header("1. System & Privilege Hook Tests")
    test_admin_privileges()
    test_pip_packages()

    # -- 2. Backend Services -------------------------------------------------
    _header("2. Backend Service Integration Tests")
    test_wmi_security_center()
    test_defender_cli()
    test_firewall_service()

    # -- 3. API & AI Automation ----------------------------------------------
    _header("3. API & AI Automation Tests")
    env_vars, groq_ok = test_env_file()

    if groq_ok:
        test_groq_reachability(env_vars["GROQ_API_KEY"])
    else:
        _fail(
            "Groq API reachability",
            "Skipped -- no valid GROQ_API_KEY",
            "ACTION: Fix .env first, then re-run diagnostics",
        )

    test_agent_payload()

    # -- 4. QML Compilation --------------------------------------------------
    _header("4. UI (QML) Compilation Tests")
    test_qml_compilation()

    elapsed = time.monotonic() - start

    # -- 5. Final Report -----------------------------------------------------
    print_report()
    print(f"  Completed in {elapsed:.2f}s\n")


if __name__ == "__main__":
    main()
