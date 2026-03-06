"""
Regression tests for app.scanning.report_schema v2.0 helpers.

Covers:
  - validate_report_v2  – structural contract enforcement
  - normalize_report_v2 – default-filling without crashes
  - Round-trip: build_empty_report → validate → passes with zero errors
  - normalize is idempotent (normalizing twice == normalizing once)

All tests are fully offline — no network, no VM, no OS tools required.
"""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path

# ── ensure repo root on sys.path ──────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ── stub optional heavy deps ──────────────────────────────────────────────────
def _stub(name: str) -> None:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


for _m in ("yara", "psutil", "PySide6", "PySide6.QtCore", "groq"):
    _stub(_m)


# ── import under test ─────────────────────────────────────────────────────────
_schema = importlib.import_module("app.scanning.report_schema")
build_empty_report = _schema.build_empty_report
validate_report_v2 = _schema.validate_report_v2
normalize_report_v2 = _schema.normalize_report_v2


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _empty() -> dict:
    """Return a fresh empty report as a plain dict."""
    return dict(build_empty_report())


# ─────────────────────────────────────────────────────────────────────────────
# validate_report_v2
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateReportV2(unittest.TestCase):
    def test_empty_report_is_valid(self) -> None:
        ok, errors = validate_report_v2(_empty())
        self.assertTrue(ok, f"empty report should be valid; errors: {errors}")
        self.assertEqual(errors, [])

    def test_wrong_schema_version(self) -> None:
        r = _empty()
        r["schema_version"] = "1.0"
        ok, errors = validate_report_v2(r)
        self.assertFalse(ok)
        self.assertTrue(any("schema_version" in e for e in errors))

    def test_missing_top_level_key(self) -> None:
        r = _empty()
        del r["iocs"]
        ok, errors = validate_report_v2(r)
        self.assertFalse(ok)
        self.assertTrue(any("iocs" in e for e in errors))

    def test_missing_static_engines(self) -> None:
        r = _empty()
        del r["static"]["engines"]
        ok, errors = validate_report_v2(r)
        self.assertFalse(ok)
        self.assertTrue(any("static.engines" in e for e in errors))

    def test_missing_sandbox_processes_started(self) -> None:
        r = _empty()
        del r["sandbox"]["processes_started"]
        ok, errors = validate_report_v2(r)
        self.assertFalse(ok)
        self.assertTrue(any("sandbox.processes_started" in e for e in errors))

    def test_missing_ioc_urls(self) -> None:
        r = _empty()
        del r["iocs"]["urls"]
        ok, errors = validate_report_v2(r)
        self.assertFalse(ok)
        self.assertTrue(any("iocs.urls" in e for e in errors))

    def test_missing_ioc_file_paths(self) -> None:
        r = _empty()
        del r["iocs"]["file_paths"]
        ok, errors = validate_report_v2(r)
        self.assertFalse(ok)
        self.assertTrue(any("iocs.file_paths" in e for e in errors))

    def test_missing_ioc_registry_keys(self) -> None:
        r = _empty()
        del r["iocs"]["registry_keys"]
        ok, errors = validate_report_v2(r)
        self.assertFalse(ok)
        self.assertTrue(any("iocs.registry_keys" in e for e in errors))

    def test_not_a_dict_returns_false(self) -> None:
        ok, errors = validate_report_v2("not a dict")  # type: ignore[arg-type]
        self.assertFalse(ok)
        self.assertEqual(len(errors), 1)

    def test_multiple_errors_accumulated(self) -> None:
        """Validator must collect ALL errors, not stop at first."""
        r = _empty()
        del r["iocs"]["urls"]
        del r["sandbox"]["highlights"]
        del r["static"]["engines"]
        ok, errors = validate_report_v2(r)
        self.assertFalse(ok)
        self.assertGreaterEqual(len(errors), 3)


# ─────────────────────────────────────────────────────────────────────────────
# normalize_report_v2
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalizeReportV2(unittest.TestCase):
    # Required array keys --------------------------------------------------

    _ARRAY_KEYS = {
        "static": ["engines", "top_strings", "suspicious_imports", "yara_matches"],
        "sandbox": [
            "processes_started",
            "files_created",
            "files_modified",
            "registry_modified",
            "network_attempts",
            "dns_queries",
            "alerts",
            "errors",
            "highlights",
        ],
        "iocs": ["urls", "domains", "ips", "file_paths", "registry_keys", "hashes"],
        "verdict": ["reasons"],
    }

    def test_fills_missing_ioc_arrays(self) -> None:
        """normalize_report_v2 fills every ioc array when they are absent."""
        r: dict = {}  # completely empty dict
        out = normalize_report_v2(r)
        for key in self._ARRAY_KEYS["iocs"]:
            self.assertIn(key, out["iocs"], f"iocs.{key} missing")
            self.assertIsInstance(out["iocs"][key], list, f"iocs.{key} not a list")

    def test_fills_missing_sandbox_arrays(self) -> None:
        r: dict = {}
        out = normalize_report_v2(r)
        for key in self._ARRAY_KEYS["sandbox"]:
            self.assertIn(key, out["sandbox"], f"sandbox.{key} missing")
            self.assertIsInstance(out["sandbox"][key], list)

    def test_fills_missing_static_engines(self) -> None:
        r: dict = {}
        out = normalize_report_v2(r)
        self.assertIsInstance(out["static"]["engines"], list)

    def test_existing_values_are_preserved(self) -> None:
        """normalize must not overwrite values that already exist."""
        r = _empty()
        r["iocs"]["urls"] = ["https://evil.example.com"]
        r["sandbox"]["processes_started"] = [{"pid": 1234, "name": "malware.exe"}]
        out = normalize_report_v2(r)
        self.assertEqual(out["iocs"]["urls"], ["https://evil.example.com"])
        self.assertEqual(
            out["sandbox"]["processes_started"], [{"pid": 1234, "name": "malware.exe"}]
        )

    def test_does_not_mutate_original(self) -> None:
        """normalize_report_v2 must return a deep copy, not modify in place."""
        r: dict = {}
        id(r)
        out = normalize_report_v2(r)
        self.assertIsNot(out, r, "normalize must return a new dict")
        self.assertEqual(r, {}, "original dict must not be mutated")

    def test_non_dict_input_returns_valid_report(self) -> None:
        out = normalize_report_v2(None)  # type: ignore[arg-type]
        ok, errors = validate_report_v2(out)
        self.assertTrue(ok, f"fallback for None should be valid; errors: {errors}")

    def test_idempotent(self) -> None:
        """Normalizing twice must equal normalizing once."""
        r: dict = {"sandbox": {"processes_started": [{"pid": 1}]}}
        once = normalize_report_v2(r)
        twice = normalize_report_v2(once)
        self.assertEqual(once, twice, "normalize_report_v2 must be idempotent")

    def test_normalized_empty_dict_is_valid(self) -> None:
        """A completely empty dict, once normalized, must pass validate."""
        out = normalize_report_v2({})
        ok, errors = validate_report_v2(out)
        self.assertTrue(ok, f"normalized {{}} should pass validate; errors: {errors}")

    def test_schema_version_set_to_2_0(self) -> None:
        out = normalize_report_v2({})
        self.assertEqual(out["schema_version"], "2.0")


# ─────────────────────────────────────────────────────────────────────────────
# Round-trip: build_empty_report → validate
# ─────────────────────────────────────────────────────────────────────────────


class TestRoundTrip(unittest.TestCase):
    def test_fresh_empty_report_validates(self) -> None:
        r = _empty()
        ok, errors = validate_report_v2(r)
        self.assertTrue(
            ok,
            f"build_empty_report() should produce a valid v2 report; errors: {errors}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
