"""Runtime policy tests for scan backend and sandbox safeguards."""

from app.scanning.integrated_sandbox import IntegratedSandbox
from app.scanning.static_scanner import StaticScanner
from app.scanning.window_capture import is_noise_window_title


def test_sandbox_cpu_cap_default(monkeypatch):
    """Sandbox CPU cap defaults to safe non-zero value."""
    monkeypatch.delenv("SENTINEL_SANDBOX_CPU_CAP_PERCENT", raising=False)
    assert IntegratedSandbox._sandbox_cpu_cap_percent() == 50


def test_windows_sandbox_engine_default(monkeypatch):
    """Windows sandbox engine defaults to VM backend first."""
    monkeypatch.delenv("SENTINEL_SANDBOX_ENGINE", raising=False)
    assert IntegratedSandbox._windows_engine_preference() == "windows_sandbox"


def test_windows_sandbox_engine_alias(monkeypatch):
    """Shorthand backend aliases map to stable internal names."""
    monkeypatch.setenv("SENTINEL_SANDBOX_ENGINE", "wsb")
    assert IntegratedSandbox._windows_engine_preference() == "windows_sandbox"
    monkeypatch.setenv("SENTINEL_SANDBOX_ENGINE", "job")
    assert IntegratedSandbox._windows_engine_preference() == "job_object"


def test_windows_engine_resolution_prefers_wsb_then_fallback():
    """Engine resolution picks VM first and keeps fallback path available."""
    engine, available, reason = IntegratedSandbox._resolve_windows_engine(
        preference="windows_sandbox",
        wsb_available=False,
        job_available=True,
    )
    assert engine == "windows_sandbox"
    assert available is True
    assert "fallback" in reason.lower()


def test_sandbox_cpu_cap_clamped(monkeypatch):
    """Sandbox CPU cap is clamped to valid range."""
    monkeypatch.setenv("SENTINEL_SANDBOX_CPU_CAP_PERCENT", "-20")
    assert IntegratedSandbox._sandbox_cpu_cap_percent() == 0

    monkeypatch.setenv("SENTINEL_SANDBOX_CPU_CAP_PERCENT", "500")
    assert IntegratedSandbox._sandbox_cpu_cap_percent() == 100


def test_inplace_execution_heuristic_for_program_files(tmp_path):
    """Dependency-heavy app folders under Program Files use in-place compatibility mode."""
    app_dir = tmp_path / "Program Files" / "VendorApp"
    app_dir.mkdir(parents=True, exist_ok=True)
    exe_path = app_dir / "vendorapp.exe"
    exe_path.write_bytes(b"MZ")

    for idx in range(6):
        (app_dir / f"sidecar_{idx}.dll").write_text("x", encoding="utf-8")

    assert IntegratedSandbox._should_use_inplace_execution(exe_path) is True


def test_inplace_execution_heuristic_for_game_install_dirs(tmp_path):
    """Known game client install dirs can use in-place compatibility mode."""
    app_dir = tmp_path / "Riot Games" / "Riot Client"
    app_dir.mkdir(parents=True, exist_ok=True)
    exe_path = app_dir / "RiotClientUx.exe"
    exe_path.write_bytes(b"MZ")

    for idx in range(6):
        (app_dir / f"sidecar_{idx}.dll").write_text("x", encoding="utf-8")

    assert IntegratedSandbox._should_use_inplace_execution(exe_path) is True


def test_static_scanner_forced_cpu_backend(monkeypatch):
    """Static scanner honors CPU forcing."""
    monkeypatch.setenv("SENTINEL_SCAN_COMPUTE", "cpu")
    scanner = StaticScanner()
    assert scanner._compute_backend == "cpu"


def test_static_scanner_invalid_backend_env_falls_back(monkeypatch):
    """Invalid compute backend value does not break scanner creation."""
    monkeypatch.setenv("SENTINEL_SCAN_COMPUTE", "not-a-real-backend")
    scanner = StaticScanner()
    assert scanner._compute_backend in {"cpu", "gpu"}


def test_noise_window_title_filtering():
    """Generic shell overlay titles should be filtered from preview fallback."""
    assert is_noise_window_title("Task Switching") is True
    assert is_noise_window_title("Program Manager") is True
    assert is_noise_window_title("   ") is True
    assert is_noise_window_title("Cisco Packet Tracer") is False
