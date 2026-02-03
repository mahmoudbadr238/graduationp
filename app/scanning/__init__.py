"""
Sentinel Scanning Module - 100% Offline/Local Security Scanning

This module provides:
- Static file analysis (PE, scripts, YARA)
- Optional ClamAV integration
- Local URL heuristics checking
- Automated sandbox analysis
- Report generation

NO NETWORK DEPENDENCIES - Everything runs locally.

NOTE: All imports are lazy-loaded for faster startup.
"""

# Lazy imports for faster startup
_static_scanner = None
_url_checker = None
_report_writer = None
_yara_engine = None
_clamav_adapter = None
_sandbox_controller = None


def get_static_scanner():
    """Lazy-load StaticScanner."""
    global _static_scanner
    if _static_scanner is None:
        from .static_scanner import StaticScanner
        _static_scanner = StaticScanner
    return _static_scanner


def get_url_checker():
    """Lazy-load URLChecker."""
    global _url_checker
    if _url_checker is None:
        from .url_checker import URLChecker
        _url_checker = URLChecker
    return _url_checker


def get_report_writer():
    """Lazy-load ReportWriter."""
    global _report_writer
    if _report_writer is None:
        from .report_writer import ReportWriter
        _report_writer = ReportWriter
    return _report_writer


def get_yara_engine():
    """Lazy-load YaraEngine."""
    global _yara_engine
    if _yara_engine is None:
        from .yara_engine import YaraEngine
        _yara_engine = YaraEngine
    return _yara_engine


def get_clamav_adapter():
    """Lazy-load ClamAVAdapter."""
    global _clamav_adapter
    if _clamav_adapter is None:
        from .clamav_adapter import ClamAVAdapter
        _clamav_adapter = ClamAVAdapter
    return _clamav_adapter


def get_sandbox_controller():
    """Lazy-load SandboxController."""
    global _sandbox_controller
    if _sandbox_controller is None:
        from .sandbox_controller import SandboxController
        _sandbox_controller = SandboxController
    return _sandbox_controller


# For backwards compatibility, also expose direct imports
# These will trigger immediate loading when accessed
def __getattr__(name):
    """Lazy attribute access for backwards compatibility."""
    if name == "StaticScanner":
        return get_static_scanner()
    elif name == "ScanResult":
        from .static_scanner import ScanResult
        return ScanResult
    elif name == "URLChecker":
        return get_url_checker()
    elif name == "URLCheckResult":
        from .url_checker import URLCheckResult
        return URLCheckResult
    elif name == "ReportWriter":
        return get_report_writer()
    elif name == "YaraEngine":
        return get_yara_engine()
    elif name == "ClamAVAdapter":
        return get_clamav_adapter()
    elif name == "SandboxController":
        return get_sandbox_controller()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "StaticScanner",
    "ScanResult", 
    "URLChecker",
    "URLCheckResult",
    "ReportWriter",
    "YaraEngine",
    "ClamAVAdapter",
    "SandboxController",
    # Lazy getters
    "get_static_scanner",
    "get_url_checker",
    "get_report_writer",
    "get_yara_engine",
    "get_clamav_adapter",
    "get_sandbox_controller",
]
