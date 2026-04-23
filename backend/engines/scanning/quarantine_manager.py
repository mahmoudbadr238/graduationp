"""
Quarantine Vault — Secure File Quarantine for Sentinel.

Provides an XOR-encrypted vault where suspicious / malicious files are
neutralised, logged, and stored until the analyst decides to delete
or restore them.

Vault Layout
~~~~~~~~~~~~
::

    C:\\ProgramData\\Sentinel\\Quarantine\\
    ├── vault_ledger.json          ← master ledger (all entries)
    ├── <uuid>.quarantine          ← XOR-encrypted file payloads
    └── ...

Security Notes
~~~~~~~~~~~~~~
* Files are XOR-obfuscated with a 256-byte random key per file so they
  cannot accidentally execute if opened or double-clicked. This is
  **not** cryptographic encryption — it prevents accidental execution,
  not a determined adversary with filesystem access.
* The original file is **deleted** after quarantine.
* The ledger records the original path, timestamp, SHA-256, and file
  size so an analyst can audit and restore if needed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import shutil
import stat
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.platform.paths import get_app_paths

logger = logging.getLogger(__name__)

# Default vault directory
DEFAULT_VAULT_DIR = get_app_paths().quarantine_dir

# XOR key length (bytes)
XOR_KEY_LENGTH = 256

# Ledger filename
LEDGER_FILENAME = "vault_ledger.json"

# Metadata schema version for modern quarantine entries.
QUARANTINE_METADATA_VERSION = 2


# ===========================================================================
# XOR Helpers
# ===========================================================================


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    """XOR *data* with a repeating *key*."""
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


def _as_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_optional_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def _canonical_path(path: str | Path) -> str:
    try:
        return str(Path(path).resolve(strict=False)).lower()
    except OSError:
        return os.path.abspath(str(path)).lower()


def _system_root() -> str:
    return _canonical_path(os.environ.get("SystemRoot") or r"C:\Windows")


def _is_windows_system_path(path: str | Path) -> bool:
    normalized = _canonical_path(path)
    root = _system_root()
    if not normalized or not root:
        return False
    return normalized == root or normalized.startswith(root + os.sep)


def _is_trusted_windows_install_path(path: str | Path) -> bool:
    normalized = _canonical_path(path)
    if not normalized:
        return False

    trusted_roots: list[str] = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        value = os.environ.get(env_name, "").strip()
        if value:
            trusted_roots.append(_canonical_path(value))

    local_programs = os.path.join(
        os.environ.get("LocalAppData", "").strip(),
        "Programs",
    ).strip("\\/")
    if local_programs:
        trusted_roots.append(_canonical_path(local_programs))

    return any(
        normalized == root or normalized.startswith(root + os.sep)
        for root in trusted_roots
        if root
    )


def _path_trust_class(path: str | Path) -> str:
    normalized = _canonical_path(path)
    if not normalized:
        return "unknown"
    if _is_windows_system_path(normalized):
        return "windows_system"
    if _is_trusted_windows_install_path(normalized):
        return "program_files"
    return "user_space"


def _probe_windows_signature(path: str | Path) -> tuple[bool | None, str]:
    """Best-effort Authenticode probe for quarantine safety and metadata."""
    if sys.platform != "win32":
        return None, ""

    literal_path = str(path).replace("'", "''")
    command = (
        "$s = Get-AuthenticodeSignature -LiteralPath '"
        + literal_path
        + "'; "
        "$subject = ''; "
        "if ($s.SignerCertificate) { $subject = $s.SignerCertificate.Subject }; "
        "Write-Output ($s.Status.ToString() + '|' + $subject)"
    )

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None, ""

    output = (result.stdout or "").strip()
    if "|" not in output:
        return None, ""

    status, subject = output.split("|", 1)
    status_text = status.strip().lower()
    publisher = subject.strip()

    if status_text == "valid":
        return True, publisher
    if status_text in {"notsigned", "unknownerror", "notsupportedfileformat"}:
        return None, publisher
    return False, publisher


def _normalize_source_key(metadata: dict[str, Any]) -> str:
    raw_source = str(metadata.get("enforcement_source") or "").strip().lower()
    source_detail = str(metadata.get("source_detail") or "").strip().lower()
    reason_text = str(metadata.get("action_reason") or "").strip().lower()

    if raw_source in {"rtp", "real_time_protection"}:
        return "rtp"
    if raw_source in {"scan_center", "scancenter"}:
        return "scan_center"
    if raw_source in {"manual", "security_assistant", "ai_assistant"}:
        return "manual"
    if raw_source in {"legacy", "imported"}:
        return "legacy"
    if source_detail in {"security_assistant", "manual"}:
        return "manual"
    if "rtp" in reason_text or "real-time protection" in reason_text:
        return "rtp"
    if "manual" in reason_text or "security assistant" in reason_text:
        return "manual"
    if not metadata:
        return "manual"
    return "unknown"


def _has_decision_metadata(metadata: dict[str, Any]) -> bool:
    return any(
        metadata.get(key) not in (None, "")
        for key in ("decision_score", "decision_verdict", "decision_action")
    )


def _metadata_quality(source_key: str, metadata: dict[str, Any]) -> str:
    if source_key == "legacy":
        return "legacy_incomplete"
    if source_key == "manual" and not _has_decision_metadata(metadata):
        return "manual_record"
    if (
        _has_decision_metadata(metadata)
        and metadata.get("file_action")
        and metadata.get("action_reason")
        and metadata.get("enforcement_source")
    ):
        return "complete"
    if not _has_decision_metadata(metadata) and not metadata.get("action_reason"):
        return "legacy_incomplete"
    return "partial"


def _default_action_reason(source_key: str) -> str:
    if source_key == "rtp":
        return "Real-time protection quarantined the file after enforcement."
    if source_key == "scan_center":
        return "Scan Center quarantine requested after analyst review."
    if source_key == "manual":
        return "Manual quarantine requested by the analyst."
    if source_key == "legacy":
        return "This legacy quarantine entry predates complete incident metadata."
    return "No enforcement reason was recorded for this quarantine entry."


def _default_metadata_note(source_key: str, quality: str) -> str:
    if quality == "legacy_incomplete":
        return (
            "This quarantine record predates complete incident metadata. "
            "Score, verdict, and source details were not recorded at quarantine time."
        )
    if source_key == "manual":
        return (
            "Manual quarantine entry. A file action was recorded, but no scan score or verdict "
            "was captured for this action."
        )
    if quality == "partial":
        return "This quarantine record has partial incident metadata."
    return ""


def _should_block_manual_system_quarantine(
    file_path: Path,
    *,
    source_key: str,
    strong_evidence: bool,
    allow_system_quarantine: bool,
    signature_valid: bool | None,
) -> bool:
    if sys.platform != "win32":
        return False
    if allow_system_quarantine or strong_evidence:
        return False
    if source_key not in {"manual", "scan_center", "unknown"}:
        return False
    if not _is_windows_system_path(file_path):
        return False
    return signature_valid is not False


def _is_protected_trusted_windows_binary(
    file_path: Path,
    *,
    signature_valid: bool | None,
) -> bool:
    if sys.platform != "win32":
        return False
    if _is_windows_system_path(file_path):
        return signature_valid is not False
    if _is_trusted_windows_install_path(file_path):
        return signature_valid is True
    return False


def _automatic_quarantine_requires_complete_decision(
    *,
    source_key: str,
    decision_action: str,
    decision_score: int | None,
    decision_verdict: str,
    file_action: str,
    explicit_override: bool,
) -> tuple[bool, str]:
    if source_key not in {"rtp", "scan_center", "unknown"}:
        return True, ""
    if explicit_override:
        return True, ""
    if decision_action != "block":
        return False, "Blocked: automatic quarantine requires a final block decision."
    if decision_score is None or decision_score <= 0:
        return False, "Blocked: automatic quarantine requires a positive final threat score."
    if decision_verdict.strip().lower() in {"", "unknown", "safe", "suspicious"}:
        return (
            False,
            "Blocked: automatic quarantine requires a high-confidence final verdict.",
        )
    if file_action != "quarantine_file":
        return (
            False,
            "Blocked: automatic quarantine requires the normalized file action 'quarantine_file'.",
        )
    return True, ""


# ===========================================================================
# Quarantine Vault
# ===========================================================================


class QuarantineVault:
    """Manages a secure quarantine directory for neutralised malware.

    Parameters
    ----------
    vault_dir
        Absolute path to the quarantine directory.
        Created automatically if it doesn't exist.
    """

    def __init__(self, vault_dir: Path | str | None = None) -> None:
        self._vault_dir = Path(vault_dir) if vault_dir else DEFAULT_VAULT_DIR
        self._ledger_path = self._vault_dir / LEDGER_FILENAME
        self._ensure_vault_dir()

    # ------------------------------------------------------------------
    # Vault initialisation
    # ------------------------------------------------------------------

    def _ensure_vault_dir(self) -> None:
        """Create the vault directory if it doesn't exist."""
        try:
            self._vault_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Quarantine vault ready: %s", self._vault_dir)
        except PermissionError:
            logger.error(
                "Cannot create quarantine vault at %s — "
                "run as Administrator or change SENTINEL_QUARANTINE_DIR",
                self._vault_dir,
            )
        except Exception as exc:
            logger.error("Failed to create vault directory: %s", exc)

    # ------------------------------------------------------------------
    # Ledger management
    # ------------------------------------------------------------------

    def _load_ledger(self) -> list[dict[str, Any]]:
        """Load the vault ledger from disk."""
        if not self._ledger_path.exists():
            return []
        try:
            return json.loads(self._ledger_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read ledger: %s", exc)
            return []

    def _save_ledger(self, entries: list[dict[str, Any]]) -> None:
        """Persist the ledger to disk."""
        try:
            self._ledger_path.write_text(
                json.dumps(entries, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("Failed to write ledger: %s", exc)

    def _append_entry(self, entry: dict[str, Any]) -> None:
        """Append a single entry to the ledger."""
        ledger = self._load_ledger()
        ledger.append(entry)
        self._save_ledger(ledger)

    def _update_entry(self, entry_id: str, updates: dict[str, Any]) -> None:
        """Update an existing ledger entry by UUID."""
        ledger = self._load_ledger()
        for entry in ledger:
            if entry.get("id") == entry_id:
                entry.update(updates)
                break
        self._save_ledger(ledger)

    # ------------------------------------------------------------------
    # Public API — Quarantine
    # ------------------------------------------------------------------

    def quarantine_file(
        self,
        file_path: str | Path,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Neutralise and vault a file.

        Steps
        -----
        1. Read the original file bytes.
        2. Generate a random XOR key and encrypt the payload.
        3. Write the encrypted payload + key to the vault as
           ``<UUID>.quarantine``.
        4. Delete the original file.
        5. Record the operation in ``vault_ledger.json``.

        Parameters
        ----------
        file_path
            Path to the file to quarantine.

        Returns
        -------
        dict
            ``success``       — bool
            ``quarantine_id`` — str (UUID)
            ``message``       — str (human-readable status)
            ``entry``         — dict (ledger entry) or None on failure
        """
        file_path = Path(file_path)
        raw_metadata = dict(metadata or {})
        result: dict[str, Any] = {
            "success": False,
            "quarantine_id": "",
            "message": "",
            "entry": None,
        }

        # ---- Validate source ----
        if not file_path.exists():
            result["message"] = f"File not found: {file_path}"
            logger.warning(result["message"])
            return result

        if not file_path.is_file():
            result["message"] = f"Not a regular file: {file_path}"
            logger.warning(result["message"])
            return result

        # ---- Read original ----
        try:
            original_bytes = file_path.read_bytes()
        except PermissionError:
            # Try to force-unlock read-only flag and retry
            try:
                file_path.chmod(stat.S_IWRITE | stat.S_IREAD)
                original_bytes = file_path.read_bytes()
            except Exception as inner_exc:
                result["message"] = (
                    f"Permission denied: cannot read '{file_path}'. "
                    f"The file may be locked by a running process. ({inner_exc})"
                )
                logger.error(result["message"])
                return result
        except Exception as exc:
            result["message"] = f"Error reading file: {exc}"
            logger.error(result["message"])
            return result

        # ---- Compute metadata ----
        file_hash = hashlib.sha256(original_bytes).hexdigest()
        file_size = len(original_bytes)

        source_key = _normalize_source_key(raw_metadata)
        decision_score = _as_optional_int(raw_metadata.get("decision_score"))
        decision_verdict = str(raw_metadata.get("decision_verdict") or "").strip()
        decision_action = str(raw_metadata.get("decision_action") or "").strip().lower()
        file_action = str(raw_metadata.get("file_action") or "quarantine_file").strip().lower()
        if not file_action:
            file_action = "quarantine_file"
        source_detail = str(raw_metadata.get("source_detail") or "").strip()
        publisher = str(raw_metadata.get("publisher") or "").strip()
        signature_valid = _as_optional_bool(raw_metadata.get("signature_valid"))
        strong_evidence = bool(raw_metadata.get("strong_evidence"))
        allow_protected_quarantine = bool(
            raw_metadata.get("allow_protected_quarantine")
            or raw_metadata.get("allow_system_quarantine")
        )
        decision_enforcement_source = str(
            raw_metadata.get("decision_enforcement_source") or ""
        ).strip().lower()
        override_type = str(raw_metadata.get("override_type") or "").strip().lower()
        explicit_override = bool(
            decision_enforcement_source == "explicit_override" or override_type
        )
        path_class = _path_trust_class(file_path)
        path_note = (
            "Protected Windows system path. Quarantine requires corroborated evidence."
            if path_class == "windows_system"
            else ""
        )

        if sys.platform == "win32" and (signature_valid is None or not publisher):
            probed_valid, probed_publisher = _probe_windows_signature(file_path)
            if signature_valid is None and probed_valid is not None:
                signature_valid = probed_valid
            if not publisher and probed_publisher:
                publisher = probed_publisher

        decision_is_complete, decision_block_reason = (
            _automatic_quarantine_requires_complete_decision(
                source_key=source_key,
                decision_action=decision_action,
                decision_score=decision_score,
                decision_verdict=decision_verdict,
                file_action=file_action,
                explicit_override=explicit_override,
            )
        )
        if not decision_is_complete:
            result["message"] = decision_block_reason
            logger.warning(
                "Refused automatic quarantine for %s due to incomplete decision metadata "
                "(source=%s action=%s score=%s verdict=%s file_action=%s)",
                file_path,
                source_key,
                decision_action or "missing",
                decision_score,
                decision_verdict or "missing",
                file_action or "missing",
            )
            return result

        if _should_block_manual_system_quarantine(
            file_path,
            source_key=source_key,
            strong_evidence=strong_evidence,
            allow_system_quarantine=allow_protected_quarantine,
            signature_valid=signature_valid,
        ):
            result["message"] = (
                "Blocked: protected Windows system binaries cannot be quarantined from weak or "
                "manual evidence alone. Review the file through a full scan or provide explicit "
                "corroborated evidence before quarantining it."
            )
            logger.warning(
                "Refused quarantine for protected system file %s (source=%s, publisher=%s, signature=%s)",
                file_path,
                source_key,
                publisher or "unknown",
                signature_valid,
            )
            return result

        if (
            _is_protected_trusted_windows_binary(
                file_path,
                signature_valid=signature_valid,
            )
            and not allow_protected_quarantine
            and not explicit_override
        ):
            result["message"] = (
                "Blocked: trusted signed Windows applications require an explicit override "
                "before quarantine. Sentinel will not quarantine protected installed software "
                "from weak, incomplete, or single-source evidence."
            )
            logger.warning(
                "Refused quarantine for protected signed binary %s (source=%s, publisher=%s, signature=%s)",
                file_path,
                source_key,
                publisher or "unknown",
                signature_valid,
            )
            return result

        normalized_metadata = {
            "metadata_version": QUARANTINE_METADATA_VERSION,
            "enforcement_source": source_key,
            "source_detail": source_detail,
            "decision_score": decision_score,
            "decision_verdict": decision_verdict,
            "decision_action": decision_action,
            "file_action": file_action,
            "file_action_taken": "quarantined",
            "action_reason": str(raw_metadata.get("action_reason") or "").strip() or _default_action_reason(source_key),
            "publisher": publisher,
            "signature_valid": signature_valid,
            "strong_evidence": strong_evidence,
            "decision_enforcement_source": decision_enforcement_source,
            "override_type": override_type,
            "path_class": path_class,
            "path_trust_note": path_note,
            "system_protected": path_class == "windows_system",
            "process_action": str(raw_metadata.get("process_action") or "").strip().lower(),
            "process_name": str(raw_metadata.get("process_name") or "").strip(),
            "pid": _as_optional_int(raw_metadata.get("pid")),
            "metadata_quality": "",
            "metadata_note": "",
        }
        if "requested_by" in raw_metadata:
            normalized_metadata["requested_by"] = str(raw_metadata.get("requested_by") or "").strip()
        quality = _metadata_quality(source_key, normalized_metadata)
        normalized_metadata["metadata_quality"] = quality
        normalized_metadata["metadata_note"] = (
            str(raw_metadata.get("metadata_note") or "").strip()
            or _default_metadata_note(source_key, quality)
        )
        for key, value in raw_metadata.items():
            if key not in normalized_metadata:
                normalized_metadata[key] = value

        # ---- Encrypt (XOR) ----
        qid = str(uuid.uuid4())
        xor_key = secrets.token_bytes(XOR_KEY_LENGTH)
        encrypted = _xor_bytes(original_bytes, xor_key)

        # ---- Write to vault ----
        vault_file = self._vault_dir / f"{qid}.quarantine"
        key_file = self._vault_dir / f"{qid}.key"

        try:
            vault_file.write_bytes(encrypted)
            key_file.write_bytes(xor_key)
        except Exception as exc:
            result["message"] = f"Failed to write vault payload: {exc}"
            logger.error(result["message"])
            return result

        # ---- Delete original ----
        try:
            file_path.chmod(stat.S_IWRITE | stat.S_IREAD)
            file_path.unlink()
        except PermissionError:
            # Couldn't delete — try shutil as last resort
            try:
                shutil.move(str(file_path), str(vault_file) + ".bak")
            except Exception:
                logger.warning(
                    "Could not delete original '%s' — the quarantine "
                    "payload is still safely vaulted.",
                    file_path,
                )
        except Exception as exc:
            logger.warning("Could not delete original '%s': %s", file_path, exc)

        # ---- Ledger entry ----
        entry = {
            "id": qid,
            "original_path": str(file_path.resolve()),
            "original_name": file_path.name,
            "sha256": file_hash,
            "size_bytes": file_size,
            "quarantined_at": datetime.now(timezone.utc).isoformat(),
            "vault_file": str(vault_file),
            "status": "quarantined",
        }
        entry.update(normalized_metadata)
        self._append_entry(entry)

        result.update({
            "success": True,
            "quarantine_id": qid,
            "message": (
                f"File '{file_path.name}' quarantined successfully.\n"
                f"  ID:     {qid}\n"
                f"  SHA256: {file_hash}\n"
                f"  Size:   {file_size:,} bytes\n"
                f"  Vault:  {vault_file}"
            ),
            "entry": entry,
        })

        logger.info(
            "QUARANTINED: %s → %s (sha256=%s)",
            file_path.name, qid, file_hash[:16],
        )
        return result

    # ------------------------------------------------------------------
    # Public API — Restore
    # ------------------------------------------------------------------

    def restore_file(self, quarantine_id: str) -> dict[str, Any]:
        """Restore a quarantined file to its original location.

        Parameters
        ----------
        quarantine_id
            The UUID assigned during quarantine.

        Returns
        -------
        dict
            ``success`` — bool
            ``message`` — str
        """
        result: dict[str, Any] = {"success": False, "message": ""}

        # ---- Find ledger entry ----
        ledger = self._load_ledger()
        entry = next((e for e in ledger if e.get("id") == quarantine_id), None)

        if entry is None:
            result["message"] = f"No quarantine entry found for ID: {quarantine_id}"
            logger.warning(result["message"])
            return result

        if entry.get("status") == "restored":
            result["message"] = f"Entry {quarantine_id} was already restored."
            return result
        if entry.get("status") == "deleted":
            result["message"] = (
                f"Entry {quarantine_id} was permanently deleted and cannot be restored."
            )
            return result
        if entry.get("status") != "quarantined":
            result["message"] = (
                f"Entry {quarantine_id} is not in an active quarantined state."
            )
            return result

        # ---- Read encrypted payload ----
        vault_file = self._vault_dir / f"{quarantine_id}.quarantine"
        key_file = self._vault_dir / f"{quarantine_id}.key"

        if not vault_file.exists():
            result["message"] = f"Vault payload not found: {vault_file}"
            logger.error(result["message"])
            return result

        if not key_file.exists():
            result["message"] = f"Encryption key not found: {key_file}"
            logger.error(result["message"])
            return result

        try:
            encrypted = vault_file.read_bytes()
            xor_key = key_file.read_bytes()
        except Exception as exc:
            result["message"] = f"Error reading vault data: {exc}"
            logger.error(result["message"])
            return result

        # ---- Decrypt ----
        original_bytes = _xor_bytes(encrypted, xor_key)

        # ---- Write back to original location ----
        original_path = Path(entry["original_path"])
        try:
            original_path.parent.mkdir(parents=True, exist_ok=True)
            original_path.write_bytes(original_bytes)
        except Exception as exc:
            result["message"] = (
                f"Failed to restore file to '{original_path}': {exc}"
            )
            logger.error(result["message"])
            return result

        # ---- Verify integrity ----
        restored_hash = hashlib.sha256(original_bytes).hexdigest()
        if restored_hash != entry.get("sha256", ""):
            logger.warning(
                "Integrity mismatch: expected %s, got %s",
                entry.get("sha256"), restored_hash,
            )

        # ---- Clean up vault ----
        try:
            vault_file.unlink(missing_ok=True)
            key_file.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Could not delete vault files: %s", exc)

        # ---- Update ledger ----
        self._update_entry(quarantine_id, {
            "status": "restored",
            "restored_at": datetime.now(timezone.utc).isoformat(),
        })

        result.update({
            "success": True,
            "message": "File restored successfully.",
            "original_name": str(entry.get("original_name") or original_path.name),
            "original_path": str(original_path),
            "restored_sha256": restored_hash,
            "integrity_verified": restored_hash == entry.get("sha256"),
            "status": "restored",
        })

        logger.info("RESTORED: %s -> %s", quarantine_id, original_path)
        return result

    # ------------------------------------------------------------------
    # Public API — List / Delete
    # ------------------------------------------------------------------

    def list_quarantined(self) -> list[dict[str, Any]]:
        """Return all active quarantine entries."""
        return [
            e for e in self._load_ledger()
            if e.get("status") == "quarantined"
        ]

    def list_entries(self) -> list[dict[str, Any]]:
        """Return the full quarantine ledger newest-first for audit/history views."""
        entries = [dict(entry) for entry in self._load_ledger()]
        entries.sort(
            key=lambda entry: (
                entry.get("deleted_at")
                or entry.get("restored_at")
                or entry.get("quarantined_at")
                or ""
            ),
            reverse=True,
        )
        return entries

    def delete_permanently(self, quarantine_id: str) -> dict[str, Any]:
        """Permanently delete a quarantined file (no recovery)."""
        result: dict[str, Any] = {"success": False, "message": ""}

        ledger = self._load_ledger()
        entry = next((e for e in ledger if e.get("id") == quarantine_id), None)
        if entry is None:
            result["message"] = f"No quarantine entry found for ID: {quarantine_id}"
            return result
        if entry.get("status") == "deleted":
            result["message"] = f"Entry {quarantine_id} was already permanently deleted."
            return result
        if entry.get("status") == "restored":
            result["message"] = (
                f"Entry {quarantine_id} was already restored; there is no vaulted payload left to delete."
            )
            return result
        if entry.get("status") != "quarantined":
            result["message"] = (
                f"Entry {quarantine_id} is not in an active quarantined state."
            )
            return result

        vault_file = self._vault_dir / f"{quarantine_id}.quarantine"
        key_file = self._vault_dir / f"{quarantine_id}.key"

        try:
            vault_file.unlink(missing_ok=True)
            key_file.unlink(missing_ok=True)
        except Exception as exc:
            result["message"] = f"Error deleting vault files: {exc}"
            return result

        self._update_entry(quarantine_id, {
            "status": "deleted",
            "deleted_at": datetime.now(timezone.utc).isoformat(),
        })

        result.update({
            "success": True,
            "message": "Vault payload permanently deleted.",
            "status": "deleted",
            "audit_retained": True,
            "original_name": str(entry.get("original_name") or ""),
            "original_path": str(entry.get("original_path") or ""),
        })
        logger.info("DELETED: %s permanently removed", quarantine_id)
        return result

    @property
    def vault_path(self) -> Path:
        """Return the vault directory path."""
        return self._vault_dir


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_vault: QuarantineVault | None = None


def get_quarantine_vault() -> QuarantineVault:
    """Return the singleton ``QuarantineVault`` instance."""
    global _vault
    if _vault is None:
        _vault = QuarantineVault()
    return _vault
