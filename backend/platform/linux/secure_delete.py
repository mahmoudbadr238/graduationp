"""
Linux secure file-deletion engine using GNU shred.

Replaces backend/utils/secure_delete.py on Linux.
Uses the native `shred` command for secure overwrite and deletion.
Falls back to Python-based overwrite if shred is unavailable.
"""

from __future__ import annotations

import datetime
import logging
import os
import random
import shutil
import string
import subprocess
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

CHUNK_SIZE = 8 * 1024 * 1024  # 8 MiB per write chunk

# Paths that must never be shredded on Linux.
_BLOCKED_PREFIXES: list[str] = []


def _blocked_prefixes() -> list[str]:
    """Build the blocked-prefix list lazily."""
    if not _BLOCKED_PREFIXES:
        _BLOCKED_PREFIXES.extend([
            "/boot",
            "/usr",
            "/sbin",
            "/lib",
            "/lib64",
            "/etc",
            "/bin",
            "/proc",
            "/sys",
            "/dev",
        ])
    return _BLOCKED_PREFIXES


def validate_target(path: str) -> tuple[bool, str]:
    """Return ``(ok, reason)`` — rejects system-critical targets."""
    p = Path(path)

    if not p.exists():
        return False, f"File not found: {path}"
    if not p.is_file():
        return False, "Target is not a regular file. Only individual files can be shredded."
    if p.stat().st_size == 0:
        return False, "File is empty (0 bytes). Nothing to shred."

    resolved = str(p.resolve()).lower()

    # Block filesystem roots
    if resolved == "/":
        return False, "Cannot shred the root directory."

    for prefix in _blocked_prefixes():
        if resolved.startswith(prefix):
            return False, (
                f"Blocked: target is inside a protected system directory ({prefix})."
            )

    # Block the running application's own directory
    cwd = os.getcwd().lower()
    if resolved.startswith(cwd):
        return False, (
            "Blocked: this file is inside the Sentinel application directory. "
            "The application cannot shred its own files."
        )

    return True, ""


def shred_file(
    path: str,
    passes: int = 1,
    rename: bool = True,
    verify: bool = True,
    log_enabled: bool = True,
    progress_cb=None,
    cancel_event: threading.Event | None = None,
) -> dict:
    """Securely destroy *path* using GNU shred on Linux."""
    started_at = datetime.datetime.now(tz=datetime.timezone.utc)
    log_lines: list[str] = []

    def _log(msg: str) -> None:
        ts = datetime.datetime.now(tz=datetime.timezone.utc).isoformat(timespec="seconds")
        log_lines.append(f"[{ts}] {msg}")
        logger.info(msg)

    def _cancelled() -> bool:
        return cancel_event is not None and cancel_event.is_set()

    def _progress(phase: str, pct: int, pidx: int = 0, total: int = passes) -> None:
        if progress_cb is not None:
            progress_cb(phase, pct, pidx, total)

    result: dict = {
        "ok": False,
        "message": "",
        "started_at": started_at.isoformat(),
        "finished_at": "",
        "duration_s": 0.0,
        "size_bytes": 0,
        "passes": passes,
        "verify_result": None,
        "log_path": "",
    }

    try:
        p = Path(path)
        file_size = p.stat().st_size
        result["size_bytes"] = file_size
        _log(f"Target: {path}  ({file_size:,} bytes)")
        _log(f"Options: passes={passes}, rename={rename}, verify={verify}")

        # ── Rename step ─────────────────────────────────────────────────
        current_path = p
        if rename:
            _progress("rename", 0)
            charset = string.ascii_letters + string.digits
            random_name = "".join(random.choices(charset, k=16))  # noqa: S311
            new_path = p.parent / random_name
            os.rename(p, new_path)
            current_path = new_path
            _log(f"Renamed to: {new_path.name}")
            _progress("rename", 100)

        if _cancelled():
            result["message"] = "Cancelled before overwrite."
            _log(result["message"])
            _finalize(result, started_at, log_lines, log_enabled)
            return result

        # ── Use GNU shred if available ──────────────────────────────────
        shred_bin = shutil.which("shred")
        if shred_bin:
            _log(f"Using GNU shred ({passes} pass(es))")
            _progress("overwrite", 0, 1, passes)

            cmd = ["shred", "-vfzun", str(passes), str(current_path)]
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=300,
                )
                if proc.returncode == 0:
                    _log(f"shred completed successfully ({passes} passes)")
                    _progress("overwrite", 100, passes, passes)
                else:
                    stderr = (proc.stderr or "").strip()
                    raise RuntimeError(f"shred failed (rc={proc.returncode}): {stderr}")
            except subprocess.TimeoutExpired:
                raise RuntimeError("shred command timed out (300s)")

            _progress("delete", 100)
            _log("File securely destroyed via GNU shred.")
        else:
            # ── Python fallback ─────────────────────────────────────────
            _log("GNU shred not found — using Python fallback")
            for pass_idx in range(1, passes + 1):
                if _cancelled():
                    result["message"] = f"Cancelled during pass {pass_idx}/{passes}."
                    _log(result["message"])
                    _finalize(result, started_at, log_lines, log_enabled)
                    return result

                _log(f"Pass {pass_idx}/{passes}: opening for overwrite…")
                _progress("overwrite", 0, pass_idx, passes)

                with open(current_path, "r+b") as fh:
                    written = 0
                    while written < file_size:
                        if _cancelled():
                            result["message"] = f"Cancelled during pass {pass_idx}/{passes}."
                            _log(result["message"])
                            _finalize(result, started_at, log_lines, log_enabled)
                            return result

                        chunk_len = min(CHUNK_SIZE, file_size - written)
                        fh.write(os.urandom(chunk_len))
                        written += chunk_len

                        pct = int(written / file_size * 100)
                        _progress("overwrite", pct, pass_idx, passes)

                    fh.flush()
                    os.fsync(fh.fileno())

                _log(f"Pass {pass_idx}/{passes}: complete.")

            _progress("delete", 0)
            os.remove(current_path)
            _log("File deleted from disk.")
            _progress("delete", 100)

        # ── Verify ──────────────────────────────────────────────────────
        if verify:
            _progress("verify", 0)
            exists = current_path.exists()
            result["verify_result"] = not exists
            if exists:
                result["message"] = "Overwrite succeeded but file still detected on disk."
                _log(f"Verify: FAIL — {current_path} still exists")
            else:
                _log("Verify: PASS — file no longer exists")
            _progress("verify", 100)

        result["ok"] = True
        result["message"] = "File securely destroyed."
        _log(result["message"])

    except PermissionError:
        result["message"] = "Permission denied. Try running with sudo."
        _log(f"ERROR: {result['message']}")
    except Exception as exc:
        result["message"] = str(exc)
        _log(f"ERROR: {exc}")

    _finalize(result, started_at, log_lines, log_enabled)
    return result


def _finalize(
    result: dict,
    started_at: datetime.datetime,
    log_lines: list[str],
    log_enabled: bool,
) -> None:
    finished = datetime.datetime.now(tz=datetime.timezone.utc)
    result["finished_at"] = finished.isoformat()
    result["duration_s"] = round((finished - started_at).total_seconds(), 2)

    if log_enabled and log_lines:
        try:
            config_home = os.environ.get(
                "XDG_CONFIG_HOME",
                str(Path.home() / ".config"),
            )
            ts_dir = started_at.strftime("%Y%m%d_%H%M%S")
            log_dir = Path(config_home) / "Sentinel" / "logs" / "shredder" / ts_dir
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "shredder.log"
            log_path.write_text("\n".join(log_lines), encoding="utf-8")
            result["log_path"] = str(log_path)
        except Exception as exc:
            logger.warning("Could not write shredder log: %s", exc)
