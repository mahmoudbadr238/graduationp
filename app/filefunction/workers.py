"""
Background workers for file shredding and forensic file carving.

Both classes are QRunnable subclasses designed to run on QThreadPool so
the GUI thread is never blocked.
"""

from __future__ import annotations

import logging
import os
import random
import string
from pathlib import Path

import psutil
from PySide6.QtCore import QMutex, QMutexLocker, QObject, QRunnable, Signal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Magic-number registry  (header, footer | None)
# ---------------------------------------------------------------------------
SIGNATURES: dict[str, tuple[bytes, bytes | None]] = {
    "JPEG": (b"\xff\xd8\xff", b"\xff\xd9"),
    "PNG":  (b"\x89PNG\r\n\x1a\n", b"IEND\xaeB\x60\x82"),
    "PDF":  (b"%PDF", b"%%EOF"),
}

SECTOR_SIZE = 512             # standard disk sector
MAX_CARVED_SIZE = 20_971_520  # 20 MiB safety cap per carved file
RECOVERY_DIR = Path(r"C:\Sentinel_Recovery")


# ═══════════════════════════════════════════════════════════════════════════
#  ShredderWorker — 3-pass overwrite → rename → delete
# ═══════════════════════════════════════════════════════════════════════════


class ShredderWorker(QRunnable):
    """Securely destroy a single file with a 3-pass overwrite scheme.

    Pass 1 & 2: ``os.urandom`` covering the entire file size.
    Pass 3:     Zeroes (``b'\\x00'``) covering the entire file size.
    Then the file is renamed to a random 16-character string (to destroy
    the original MFT record) and deleted.
    """

    class Signals(QObject):
        progress = Signal(int)    # 0-100
        status = Signal(str)      # human-readable phase label
        finished = Signal(str)    # success message
        error = Signal(str)       # error message

    def __init__(self, file_path: str) -> None:
        super().__init__()
        self.file_path = file_path
        self.signals = self.Signals()
        self._cancelled = False
        self._mutex = QMutex()
        self.setAutoDelete(True)

    # -- cancellation -------------------------------------------------------
    def cancel(self) -> None:
        with QMutexLocker(self._mutex):
            self._cancelled = True

    def _is_cancelled(self) -> bool:
        with QMutexLocker(self._mutex):
            return self._cancelled

    # -- main logic ---------------------------------------------------------
    def run(self) -> None:  # noqa: C901
        try:
            path = Path(self.file_path)
            if not path.is_file():
                self.signals.error.emit(f"File not found: {self.file_path}")
                return

            file_size = path.stat().st_size
            if file_size == 0:
                path.unlink()
                self.signals.progress.emit(100)
                self.signals.finished.emit("Empty file deleted.")
                return

            total_steps = 5  # 3 passes + rename + delete
            step = 0

            # --- Pass 1: random bytes ----------------------------------------
            if self._is_cancelled():
                return
            self.signals.status.emit("Pass 1/3: Random overwrite…")
            self._overwrite_pass(path, file_size, mode="random")
            step += 1
            self.signals.progress.emit(int(step / total_steps * 100))

            # --- Pass 2: random bytes ----------------------------------------
            if self._is_cancelled():
                return
            self.signals.status.emit("Pass 2/3: Random overwrite…")
            self._overwrite_pass(path, file_size, mode="random")
            step += 1
            self.signals.progress.emit(int(step / total_steps * 100))

            # --- Pass 3: zero bytes ------------------------------------------
            if self._is_cancelled():
                return
            self.signals.status.emit("Pass 3/3: Zero overwrite…")
            self._overwrite_pass(path, file_size, mode="zero")
            step += 1
            self.signals.progress.emit(int(step / total_steps * 100))

            # --- Rename to random 16-char string (destroys MFT name) ---------
            if self._is_cancelled():
                return
            self.signals.status.emit("Renaming file…")
            charset = string.ascii_letters + string.digits
            random_name = "".join(random.choices(charset, k=16))  # noqa: S311
            new_path = path.parent / random_name
            os.rename(path, new_path)
            step += 1
            self.signals.progress.emit(int(step / total_steps * 100))

            # --- Delete ------------------------------------------------------
            self.signals.status.emit("Deleting file…")
            new_path.unlink()
            step += 1
            self.signals.progress.emit(100)

            self.signals.finished.emit(
                f"File securely destroyed: {path.name}"
            )
            logger.info("Shredder completed for %s", self.file_path)

        except PermissionError:
            self.signals.error.emit(
                "Permission denied. Close any programs using this file and try again."
            )
        except Exception as exc:
            logger.exception("ShredderWorker error")
            self.signals.error.emit(str(exc))

    # -- overwrite helper ---------------------------------------------------
    @staticmethod
    def _overwrite_pass(path: Path, file_size: int, *, mode: str) -> None:
        """Overwrite *path* entirely, then ``flush`` + ``fsync`` to disk."""
        with open(path, "r+b") as fh:
            fh.seek(0)
            if mode == "random":
                fh.write(os.urandom(file_size))
            else:
                fh.write(b"\x00" * file_size)
            fh.flush()
            os.fsync(fh.fileno())


# ═══════════════════════════════════════════════════════════════════════════
#  CarverWorker — sweep all mounted drives for deleted file signatures
# ═══════════════════════════════════════════════════════════════════════════


class CarverWorker(QRunnable):
    """Scan raw disk sectors across every mounted drive for file signatures.

    Emits real-time log strings so the QML terminal can display progress.
    Carved files are written to ``C:\\Sentinel_Recovery``.
    """

    class Signals(QObject):
        found = Signal(str)      # one log-line per carved file
        status = Signal(str)     # current drive / offset
        finished = Signal(str)   # completion summary
        error = Signal(str)      # error message

    def __init__(self, file_type: str) -> None:
        super().__init__()
        self.file_type = file_type.upper()
        self.signals = self.Signals()
        self._cancelled = False
        self._mutex = QMutex()
        self.setAutoDelete(True)

    # -- cancellation -------------------------------------------------------
    def cancel(self) -> None:
        with QMutexLocker(self._mutex):
            self._cancelled = True

    def _is_cancelled(self) -> bool:
        with QMutexLocker(self._mutex):
            return self._cancelled

    # -- main logic ---------------------------------------------------------
    def run(self) -> None:
        try:
            sig = SIGNATURES.get(self.file_type)
            if sig is None:
                self.signals.error.emit(
                    f"Unsupported file type: {self.file_type}"
                )
                return

            header, footer = sig

            # Prepare output directory
            RECOVERY_DIR.mkdir(parents=True, exist_ok=True)

            # Enumerate fixed drives
            drives = self._get_fixed_drives()
            if not drives:
                self.signals.error.emit("No fixed drives detected.")
                return

            self.signals.status.emit(
                f"Detected drives: {', '.join(d + ':' for d in drives)}"
            )
            self.signals.found.emit(
                f"[*] Starting {self.file_type} recovery across "
                f"{len(drives)} drive(s)…"
            )

            total_found = 0

            for drive_letter in drives:
                if self._is_cancelled():
                    break

                count = self._scan_drive(
                    drive_letter, header, footer, total_found
                )
                total_found += count

            if self._is_cancelled():
                self.signals.finished.emit(
                    f"Cancelled. {total_found} file(s) recovered before stop."
                )
            else:
                self.signals.finished.emit(
                    f"Recovery complete. {total_found} {self.file_type} file(s) "
                    f"saved to {RECOVERY_DIR}"
                )

        except Exception as exc:
            logger.exception("CarverWorker error")
            self.signals.error.emit(str(exc))

    # -- per-drive scan -----------------------------------------------------
    def _scan_drive(
        self,
        drive_letter: str,
        header: bytes,
        footer: bytes | None,
        found_offset: int,
    ) -> int:
        """Open *drive_letter* as a raw volume and scan sector-by-sector.

        Returns the number of files carved from this drive.
        """
        raw_path = f"\\\\.\\{drive_letter}:"
        self.signals.found.emit(f"[{drive_letter}:] Opening raw handle {raw_path}")

        try:
            fh = open(raw_path, "rb")  # noqa: SIM115 – raw disk handle
        except PermissionError:
            self.signals.found.emit(
                f"[{drive_letter}:] PermissionError — run Sentinel as Administrator "
                f"to scan this drive."
            )
            return 0
        except OSError as exc:
            self.signals.found.emit(f"[{drive_letter}:] Cannot open drive: {exc}")
            return 0

        count = 0
        sector_index = 0
        UPDATE_EVERY = 2048  # emit status every ~1 MiB of raw read

        try:
            while True:
                if self._is_cancelled():
                    break

                sector = fh.read(SECTOR_SIZE)
                if not sector:
                    break  # end of disk

                # Fast check: does this sector contain the header?
                pos = sector.find(header)
                if pos != -1:
                    abs_offset = sector_index * SECTOR_SIZE + pos
                    fh.seek(abs_offset)

                    carved = self._carve_file(fh, header, footer)
                    if carved:
                        idx = found_offset + count + 1
                        ext = self.file_type.lower()
                        out_name = f"{self.file_type}_{idx}.{ext}"
                        out_path = RECOVERY_DIR / out_name
                        out_path.write_bytes(carved)
                        count += 1
                        self.signals.found.emit(
                            f"[{drive_letter}:] Carved {out_name} from "
                            f"sector {sector_index} (offset 0x{abs_offset:X})"
                        )

                    # Resume from the next sector
                    next_sector = sector_index + 1
                    fh.seek(next_sector * SECTOR_SIZE)
                    sector_index = next_sector
                    continue

                sector_index += 1

                if sector_index % UPDATE_EVERY == 0:
                    self.signals.status.emit(
                        f"Scanning Drive {drive_letter}: "
                        f"Sector {sector_index}…"
                    )
        finally:
            fh.close()

        self.signals.found.emit(
            f"[{drive_letter}:] Drive scan complete — {count} file(s) recovered."
        )
        return count

    # -- carve a single file from current position --------------------------
    @staticmethod
    def _carve_file(
        fh,
        header: bytes,
        footer: bytes | None,
    ) -> bytes | None:
        """Read from *fh* (positioned at *header*) until *footer* or size cap."""
        data = fh.read(MAX_CARVED_SIZE)
        if not data or not data.startswith(header):
            return None

        if footer:
            end = data.find(footer)
            if end != -1:
                return data[: end + len(footer)]
            # Footer not found within cap — likely truncated / corrupt
            return None

        # No footer defined — return entire chunk (capped)
        return data

    # -- drive enumeration --------------------------------------------------
    @staticmethod
    def _get_fixed_drives() -> list[str]:
        """Return a sorted list of drive letters for fixed/local partitions."""
        letters: list[str] = []
        for part in psutil.disk_partitions(all=False):
            # On Windows, mountpoint is like 'C:\\'; opts contains 'fixed'
            mp = part.mountpoint
            if len(mp) >= 2 and mp[1] == ":":
                letter = mp[0].upper()
                if letter not in letters:
                    letters.append(letter)
        letters.sort()
        return letters
