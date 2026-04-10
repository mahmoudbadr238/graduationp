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
* Files are XOR-encrypted with a 256-byte random key so they cannot
  accidentally execute if opened.
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
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default vault directory
DEFAULT_VAULT_DIR = Path(os.environ.get(
    "SENTINEL_QUARANTINE_DIR",
    r"C:\ProgramData\Sentinel\Quarantine",
))

# XOR key length (bytes)
XOR_KEY_LENGTH = 256

# Ledger filename
LEDGER_FILENAME = "vault_ledger.json"


# ===========================================================================
# XOR Helpers
# ===========================================================================


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    """XOR *data* with a repeating *key*."""
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


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

    def quarantine_file(self, file_path: str | Path) -> dict[str, Any]:
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
            "message": (
                f"File restored successfully.\n"
                f"  Original: {original_path}\n"
                f"  SHA256:   {restored_hash}\n"
                f"  Integrity: {'VERIFIED ✓' if restored_hash == entry.get('sha256') else 'MISMATCH ⚠'}"
            ),
        })

        logger.info("RESTORED: %s → %s", quarantine_id, original_path)
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

    def delete_permanently(self, quarantine_id: str) -> dict[str, Any]:
        """Permanently delete a quarantined file (no recovery)."""
        result: dict[str, Any] = {"success": False, "message": ""}

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
            "message": f"Quarantine entry {quarantine_id} permanently deleted.",
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
