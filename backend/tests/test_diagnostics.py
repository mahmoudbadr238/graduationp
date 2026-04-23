"""Tests for diagnostics feature reporting."""

import builtins
from types import SimpleNamespace

from backend.utils.diagnostics import (
    _build_feature_status,
    _collect_dependency_status,
    _has_degraded_features,
)


def test_windows_event_logs_mark_degraded_when_pywin32_is_missing() -> None:
    features = _build_feature_status(
        "Windows",
        {"pywin32": {"status": "not_found"}, "wmi": {"status": "ok"}},
        groq_configured=False,
    )

    assert features["event_logs"]["status"] == "degraded"
    assert "pywin32" in features["event_logs"]["detail"]


def test_windows_rtp_marks_degraded_when_wmi_is_missing() -> None:
    features = _build_feature_status(
        "Windows",
        {"pywin32": {"status": "ok"}, "wmi": {"status": "not_found"}},
        groq_configured=False,
    )

    assert features["real_time_protection"]["status"] == "degraded"
    assert "wmi" in features["real_time_protection"]["detail"]


def test_cloud_ai_reports_disabled_without_key() -> None:
    features = _build_feature_status(
        "Linux",
        {},
        groq_configured=False,
    )

    assert features["cloud_ai"]["status"] == "disabled"


def test_disabled_features_do_not_count_as_degraded() -> None:
    features = {
        "cloud_ai": {"status": "disabled"},
        "event_logs": {"status": "available"},
    }

    assert _has_degraded_features(features) is False


def test_dependency_status_honors_import_name(monkeypatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: ANN001
        if name == "pythoncom":
            return SimpleNamespace(__version__="test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    status = _collect_dependency_status(
        {
            "pywin32": {
                "optional": True,
                "import_name": "pythoncom",
            }
        }
    )

    assert status["pywin32"]["status"] == "ok"
