"""ScanCenter export – write report.json + artifacts.zip to a directory.

Usage
-----
    path = export_report(report, dest_dir="/path/to/export", artifacts=[...])
    # returns {"report_path": ..., "zip_path": ..., "sha256": ...}
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import zipfile
from pathlib import Path
from typing import Any

from .report_schema import V3Report

logger = logging.getLogger(__name__)


def export_report(
    report: V3Report,
    dest_dir: str | Path,
    extra_artifacts: list[str] | None = None,
) -> dict[str, Any]:
    """
    Write *report* as ``report.json`` into *dest_dir* and bundle
    any existing *extra_artifacts* into ``artifacts.zip``.

    Returns
    -------
    {
        "ok": bool,
        "report_path": str,
        "zip_path": str | None,
        "sha256": str,          # sha256 of report.json
        "error": str            # empty on success
    }
    """
    dest = Path(dest_dir)
    result: dict[str, Any] = {
        "ok": False,
        "report_path": "",
        "zip_path": None,
        "sha256": "",
        "error": "",
    }

    try:
        dest.mkdir(parents=True, exist_ok=True)
        report_path = dest / "report.json"

        json_bytes = report.to_json().encode("utf-8")
        report_path.write_bytes(json_bytes)
        result["sha256"] = hashlib.sha256(json_bytes).hexdigest()
        result["report_path"] = str(report_path)

        # Bundle artifacts zip if any candidates exist
        candidates: list[Path] = []
        for p in extra_artifacts or []:
            ap = Path(p)
            if ap.exists() and ap.is_file():
                candidates.append(ap)

        # Also include screenshot if present
        if report.sandbox and report.sandbox.screenshot_path:
            sp = Path(report.sandbox.screenshot_path)
            if sp.exists() and sp not in candidates:
                candidates.append(sp)

        if candidates:
            zip_path = dest / "artifacts.zip"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for ap in candidates:
                    zf.write(ap, ap.name)
            result["zip_path"] = str(zip_path)

        result["ok"] = True
    except Exception as exc:
        result["error"] = str(exc)
        logger.error("export_report failed: %s", exc)

    return result


def default_export_dir(job_id: str) -> Path:
    """Return the canonical per-job export directory (under ~/.sentinel/reports/)."""
    base = Path.home() / ".sentinel" / "reports"
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in job_id)
    return base / safe_id


def load_report_json(path: str | Path) -> V3Report | None:
    """Load a report.json from disk and return a V3Report, or None on error."""
    try:
        text = Path(path).read_text(encoding="utf-8")
        data = json.loads(text)
        return V3Report.from_dict(data)
    except Exception as exc:
        logger.warning("load_report_json failed (%s): %s", path, exc)
        return None
