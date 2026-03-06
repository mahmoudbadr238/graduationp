"""
Unit tests for the VirusTotal-style sandbox reporting pipeline.

Covers:
  - app.sandbox.report_schema  (score_to_risk, build_empty_report)
  - app.sandbox.engines        (EngineResult structure)
  - app.sandbox.report_builder (_compute_verdict helper)
  - app.sandbox.report_explainer (_offline_fallback)

All tests are fully offline — no network, no VM, no OS tools required.
"""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path

# ── ensure repo root is on sys.path ───────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# Helper: stub out heavy optional dependencies so imports never fail
# ─────────────────────────────────────────────────────────────────────────────
def _stub(name: str) -> None:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


for _m in ("yara", "psutil", "PySide6", "PySide6.QtCore", "groq"):
    _stub(_m)


# ─────────────────────────────────────────────────────────────────────────────
# Tests: report_schema
# ─────────────────────────────────────────────────────────────────────────────
class TestScoreToRisk(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = importlib.import_module("app.sandbox.report_schema")

    def test_high_risk(self) -> None:
        self.assertEqual(self.mod.score_to_risk(60), "High")
        self.assertEqual(self.mod.score_to_risk(100), "High")

    def test_medium_risk(self) -> None:
        self.assertEqual(self.mod.score_to_risk(25), "Medium")
        self.assertEqual(self.mod.score_to_risk(59), "Medium")

    def test_low_risk(self) -> None:
        self.assertEqual(self.mod.score_to_risk(0), "Low")
        self.assertEqual(self.mod.score_to_risk(24), "Low")


class TestBuildEmptyReport(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = importlib.import_module("app.sandbox.report_schema")

    def test_required_top_level_keys(self) -> None:
        report = self.mod.build_empty_report()
        for key in (
            "schemaVersion",
            "job",
            "file",
            "static",
            "sandbox",
            "iocs",
            "verdict",
            "recommendations",
        ):
            self.assertIn(key, report, f"Missing top-level key: {key!r}")

    def test_schema_version(self) -> None:
        report = self.mod.build_empty_report()
        self.assertEqual(report["schemaVersion"], "1.0")

    def test_verdict_fields(self) -> None:
        report = self.mod.build_empty_report()
        verdict = report["verdict"]
        for field in ("risk", "confidence", "reasons"):
            self.assertIn(field, verdict)

    def test_iocs_lists(self) -> None:
        report = self.mod.build_empty_report()
        iocs = report["iocs"]
        for field in ("ips", "domains", "paths", "registry"):
            self.assertIsInstance(iocs[field], list)


# ─────────────────────────────────────────────────────────────────────────────
# Tests: engines — EngineResult structure
# ─────────────────────────────────────────────────────────────────────────────
class TestEngineResultStructure(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = importlib.import_module("app.sandbox.engines")

    def _make_fake_engine_result(self, status: str) -> dict:
        return {"name": "TestEngine", "status": status, "details": "test detail"}

    def test_valid_statuses(self) -> None:
        valid = {"clean", "suspicious", "malicious", "error", "not_installed"}
        for s in valid:
            er = self._make_fake_engine_result(s)
            self.assertIn(er["status"], valid)

    def test_clamav_not_installed_graceful(self) -> None:
        """clamscan is not on PATH in CI — result must be 'not_installed', not an exception."""
        import shutil

        if shutil.which("clamscan") is None:
            result = self.mod.run_clamav(Path(__file__))
            self.assertEqual(result["status"], "not_installed")
        else:
            self.skipTest("clamscan is installed on this machine")

    def test_yara_not_installed_graceful(self) -> None:
        """If yara-python is absent the engine returns not_installed rather than crashing."""
        import importlib as _il

        try:
            _il.import_module("yara")
            has_yara = True
        except ImportError:
            has_yara = False

        if not has_yara:
            result = self.mod.run_yara(Path(__file__))
            self.assertEqual(result["status"], "not_installed")
        else:
            self.skipTest("yara-python is installed on this machine")


# ─────────────────────────────────────────────────────────────────────────────
# Tests: report_builder — _compute_verdict
# ─────────────────────────────────────────────────────────────────────────────
class TestComputeVerdict(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = importlib.import_module("app.sandbox.report_builder")

    def _cv(self, engine_results, guest_summary=None, iocs=None):
        empty_iocs = {"ips": [], "domains": [], "paths": [], "registry": []}
        if iocs:
            empty_iocs.update(iocs)
        verdict, recs = self.mod._compute_verdict(
            engine_results, guest_summary or {}, empty_iocs
        )
        return {
            "risk": verdict["risk"],
            "score": verdict["confidence"],
            "recommendations": recs,
        }

    def test_clean_verdict(self) -> None:
        engines = [
            {"name": "Defender", "status": "clean", "details": ""},
            {"name": "YARA", "status": "clean", "details": ""},
            {"name": "ClamAV", "status": "not_installed", "details": ""},
        ]
        v = self._cv(engines)
        self.assertEqual(v["risk"], "Low")

    def test_malicious_verdict(self) -> None:
        # Two malicious detections = 80pts → High
        engines = [
            {"name": "Defender", "status": "malicious", "details": "Trojan:Win32/Foo"},
            {"name": "YARA", "status": "malicious", "details": "yara-sig-001"},
            {"name": "ClamAV", "status": "not_installed", "details": ""},
        ]
        v = self._cv(engines)
        self.assertEqual(v["risk"], "High")
        self.assertGreaterEqual(v["score"], 60)

    def test_suspicious_verdict(self) -> None:
        engines = [
            {"name": "Defender", "status": "clean", "details": ""},
            {"name": "YARA", "status": "suspicious", "details": "generic"},
            {"name": "ClamAV", "status": "not_installed", "details": ""},
        ]
        v = self._cv(engines)
        # 15 pts from YARA → Low/Medium boundary
        self.assertIn(v["risk"], ("Low", "Medium"))

    def test_score_capped_at_100(self) -> None:
        engines = [{"name": "Defender", "status": "malicious", "details": "virus"}] * 5
        v = self._cv(engines)
        self.assertLessEqual(v["score"], 100)

    def test_recommendations_non_empty(self) -> None:
        engines = [{"name": "Defender", "status": "malicious", "details": "virus"}]
        v = self._cv(engines)
        self.assertIsInstance(v["recommendations"], list)
        self.assertGreater(len(v["recommendations"]), 0)


# ─────────────────────────────────────────────────────────────────────────────
# Tests: report_explainer — _offline_fallback
# ─────────────────────────────────────────────────────────────────────────────
class TestOfflineFallback(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = importlib.import_module("app.sandbox.report_explainer")

    def _make_report(self, risk: str, score: int) -> dict:
        from app.sandbox.report_schema import build_empty_report

        r = build_empty_report()
        r["verdict"]["risk"] = risk
        r["verdict"]["score"] = score
        return r

    def test_returns_required_keys(self) -> None:
        r = self._make_report("Low", 5)
        result = self.mod._offline_fallback(r)
        for key in ("summary", "risk", "risk_reasons", "user_actions"):
            self.assertIn(key, result)

    def test_high_risk_has_actions(self) -> None:
        r = self._make_report("High", 75)
        result = self.mod._offline_fallback(r)
        self.assertEqual(result["risk"], "High")
        self.assertGreater(len(result["user_actions"]), 0)

    def test_low_risk_summary_mentions_safe(self) -> None:
        r = self._make_report("Low", 5)
        result = self.mod._offline_fallback(r)
        # Low-risk summary should mention something reassuring (no threat / low)
        summary_lower = result["summary"].lower()
        self.assertTrue(
            any(
                word in summary_lower
                for word in ("low", "no significant", "safe", "clean")
            ),
            f"Expected reassuring language in summary: {result['summary']!r}",
        )


if __name__ == "__main__":
    unittest.main()
