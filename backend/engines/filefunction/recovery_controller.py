"""Market-ready file recovery controller using Win32 CreateFile + sector-aligned reads."""

import ctypes
import ctypes.wintypes
import hashlib
import json
import os
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

# ── Win32 constants ──────────────────────────────────────────────────────
GENERIC_READ          = 0x80000000
FILE_SHARE_READ       = 0x00000001
FILE_SHARE_WRITE      = 0x00000002
FILE_SHARE_DELETE     = 0x00000004
OPEN_EXISTING         = 3
FILE_FLAG_NO_BUFFERING = 0x20000000
INVALID_HANDLE_VALUE  = ctypes.wintypes.HANDLE(-1).value & 0xFFFFFFFFFFFFFFFF

IOCTL_DISK_GET_DRIVE_GEOMETRY = 0x00070000

kernel32 = ctypes.windll.kernel32

# ── Signature definitions ────────────────────────────────────────────────
SIGNATURES = {
    "pdf":  (b"%PDF-",              b"%%EOF",                  50 * 1024 * 1024, ".pdf"),
    "jpg":  (b"\xFF\xD8\xFF",      b"\xFF\xD9",              25 * 1024 * 1024, ".jpg"),
    "png":  (b"\x89PNG\r\n\x1A\n", b"IEND\xAE\x42\x60\x82", 25 * 1024 * 1024, ".png"),
    "mp4":  (b"ftyp",                 None,                     200 * 1024 * 1024, ".mp4"),
    "zip":  (b"PK\x03\x04",        None,                     100 * 1024 * 1024, ".zip"),
    "docx": (b"PK\x03\x04",        None,                      50 * 1024 * 1024, ".docx"),
    "any":  None,
}
ALL_SIGS = {k: v for k, v in SIGNATURES.items() if v is not None}

DEMO_BLOB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "test_recovery_blob.bin"


def _is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


# ── Win32 disk helpers ───────────────────────────────────────────────────

def _open_raw_device(device_path: str):
    """Open a raw disk/volume using Win32 CreateFileW. Returns handle or raises."""
    handle = kernel32.CreateFileW(
        device_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_NO_BUFFERING,
        None,
    )
    # Compare as unsigned
    if (handle & 0xFFFFFFFFFFFFFFFF) == INVALID_HANDLE_VALUE:
        err = ctypes.get_last_error() or kernel32.GetLastError()
        if err == 5:
            raise PermissionError(f"Access denied on {device_path}. Run as Administrator.")
        raise OSError(f"CreateFileW failed on {device_path} (error {err})")
    return handle


def _get_sector_size(handle) -> int:
    """Query bytes-per-sector via IOCTL_DISK_GET_DRIVE_GEOMETRY."""
    # DISK_GEOMETRY: Cylinders(LARGE_INTEGER), MediaType(DWORD),
    # TracksPerCylinder(DWORD), SectorsPerTrack(DWORD), BytesPerSector(DWORD)
    buf = ctypes.create_string_buffer(256)
    returned = ctypes.wintypes.DWORD(0)
    ok = kernel32.DeviceIoControl(
        handle, IOCTL_DISK_GET_DRIVE_GEOMETRY,
        None, 0,
        buf, ctypes.sizeof(buf),
        ctypes.byref(returned),
        None,
    )
    if ok and returned.value >= 24:
        # BytesPerSector is at offset 20 (after 8+4+4+4 bytes)
        bps = int.from_bytes(buf[20:24], byteorder="little")
        if bps in (512, 1024, 2048, 4096):
            return bps
    return 512  # safe default


def _get_disk_size(handle) -> int:
    """Get disk/volume size by seeking to end with SetFilePointerEx."""
    high = ctypes.wintypes.LARGE_INTEGER(0)
    result = ctypes.wintypes.LARGE_INTEGER(0)
    ok = kernel32.SetFilePointerEx(handle, high, ctypes.byref(result), 2)  # FILE_END=2
    if ok:
        size = result.value
        # Seek back to start
        kernel32.SetFilePointerEx(handle, ctypes.wintypes.LARGE_INTEGER(0), None, 0)
        return size
    # Seek back to start anyway
    kernel32.SetFilePointerEx(handle, ctypes.wintypes.LARGE_INTEGER(0), None, 0)
    return 0


def _read_aligned(handle, offset: int, length: int, sector_size: int) -> bytes:
    """Read `length` bytes from `offset`, aligned to sector boundaries."""
    aligned_start = (offset // sector_size) * sector_size
    padding = offset - aligned_start
    aligned_length = ((padding + length + sector_size - 1) // sector_size) * sector_size

    # Seek to aligned position
    pos = ctypes.wintypes.LARGE_INTEGER(aligned_start)
    if not kernel32.SetFilePointerEx(handle, pos, None, 0):  # FILE_BEGIN=0
        return b""

    buf = ctypes.create_string_buffer(aligned_length)
    bytes_read = ctypes.wintypes.DWORD(0)
    ok = kernel32.ReadFile(handle, buf, aligned_length, ctypes.byref(bytes_read), None)
    if not ok or bytes_read.value == 0:
        return b""

    raw = buf.raw[:bytes_read.value]
    return raw[padding:padding + length]


def _read_chunk(handle, offset: int, chunk_size: int, sector_size: int) -> bytes:
    """Read a sector-aligned chunk at the given offset."""
    aligned_offset = (offset // sector_size) * sector_size
    aligned_size = ((chunk_size + sector_size - 1) // sector_size) * sector_size

    pos = ctypes.wintypes.LARGE_INTEGER(aligned_offset)
    if not kernel32.SetFilePointerEx(handle, pos, None, 0):
        return b""

    buf = ctypes.create_string_buffer(aligned_size)
    bytes_read = ctypes.wintypes.DWORD(0)
    ok = kernel32.ReadFile(handle, buf, aligned_size, ctypes.byref(bytes_read), None)
    if not ok or bytes_read.value == 0:
        return b""

    return buf.raw[:bytes_read.value]


def _close_handle(handle):
    try:
        kernel32.CloseHandle(handle)
    except Exception:
        pass


# ── Scan worker ──────────────────────────────────────────────────────────

SCAN_CHUNK = 8 * 1024 * 1024  # 8 MiB scan chunks
OVERLAP_SIZE = 1024            # overlap bytes between chunks for cross-boundary headers


class _ScanWorker(QThread):
    progressChanged = Signal(str)
    candidateFound = Signal(str)   # single candidate JSON
    candidateBatch = Signal(str)   # JSON array of candidates (throttled)
    finished = Signal(str)
    error = Signal(str)

    BATCH_INTERVAL = 0.4  # seconds between batch emissions

    def __init__(self, target_type: str, demo: bool = False):
        super().__init__()
        self.target_type = target_type.lower().strip().lstrip(".")
        self.demo = demo
        self._cancel = threading.Event()
        self._pending_batch: list = []
        self._last_batch_time: float = 0.0

    def cancel(self):
        self._cancel.set()

    def run(self):
        try:
            candidates = []
            cid = 0

            if self.demo:
                candidates, cid = self._scan_demo_blob(candidates, cid)
            else:
                if not _is_admin():
                    self.error.emit("Administrator privileges required for raw disk access.")
                    return
                candidates, cid = self._scan_volumes(candidates, cid)

            # Flush any remaining candidates
            self._flush_batch()

            output_dir = str(Path(os.environ.get("SENTINEL_RECOVERY_DIR",
                                                  r"C:\Sentinel_Recovery")))
            stats = {
                "total_candidates": len(candidates),
                "drives_scanned": len(set(c["drive"] for c in candidates)) if candidates else 0,
            }
            self.finished.emit(json.dumps({
                "candidates": candidates,
                "output_dir": output_dir,
                "stats": stats,
            }))
        except Exception as exc:
            self.error.emit(str(exc))

    # ── Demo blob scan ───────────────────────────────────────────────
    def _scan_demo_blob(self, candidates, cid):
        if not DEMO_BLOB_PATH.exists():
            self.error.emit(f"Demo blob not found: {DEMO_BLOB_PATH}")
            return candidates, cid

        data = DEMO_BLOB_PATH.read_bytes()
        total = len(data)
        sigs = self._get_target_sigs()

        self.progressChanged.emit(json.dumps({
            "percent": 0, "stage": "Scanning demo blob",
            "drive": "demo", "found_count": 0, "speed_mbps": 0,
        }))

        for sig_name, (header, footer, max_size, ext) in sigs.items():
            pos = 0
            while pos < total:
                if self._cancel.is_set():
                    return candidates, cid
                idx = data.find(header, pos)
                if idx == -1:
                    break
                end_offset = self._find_end(data, idx, header, footer, max_size)
                size_guess = end_offset - idx
                confidence = 85 if footer and data[idx:end_offset].endswith(footer) else 45
                preview = self._extract_preview(data[idx:idx + 256], sig_name)
                sha = hashlib.sha256(data[idx:idx + min(4096, size_guess)]).hexdigest()[:16]
                cand_obj = {
                    "id": cid, "drive": "demo_blob",
                    "offset_start": idx, "offset_end_guess": end_offset,
                    "offset_hex": f"0x{idx:X}",
                    "type": sig_name, "size_guess": size_guess,
                    "confidence": confidence, "preview_text": preview,
                    "sha256_guess": sha,
                }
                candidates.append(cand_obj)
                self._emit_candidate(cand_obj)
                cid += 1
                pos = end_offset
                self.progressChanged.emit(json.dumps({
                    "percent": int(pos * 100 / total),
                    "stage": f"Found {sig_name.upper()} @ offset {idx}",
                    "drive": "demo", "found_count": len(candidates), "speed_mbps": 0,
                }))

        self.progressChanged.emit(json.dumps({
            "percent": 100, "stage": "Demo scan complete",
            "drive": "demo", "found_count": len(candidates), "speed_mbps": 0,
        }))
        return candidates, cid

    # ── Real volume scan using Win32 CreateFile ──────────────────────
    def _scan_volumes(self, candidates, cid):
        import psutil
        volumes = []
        for part in psutil.disk_partitions(all=False):
            letter = part.device.rstrip("\\").rstrip(":")
            if len(letter) == 1:
                volumes.append(letter)
        if not volumes:
            volumes = [chr(x) for x in range(67, 91) if os.path.exists(f"{chr(x)}:\\")]
            if os.path.exists("C:\\"):
                volumes.insert(0, "C")
            volumes = list(dict.fromkeys(volumes))

        sigs = self._get_target_sigs()
        total_volumes = len(volumes)

        for vi, letter in enumerate(volumes):
            if self._cancel.is_set():
                break

            device_path = f"\\\\.\\{letter}:"
            self.progressChanged.emit(json.dumps({
                "percent": int(vi * 100 / max(total_volumes, 1)),
                "stage": f"Opening {device_path}",
                "drive": f"{letter}:", "found_count": len(candidates), "speed_mbps": 0,
            }))

            try:
                handle = _open_raw_device(device_path)
            except (PermissionError, OSError) as e:
                self.progressChanged.emit(json.dumps({
                    "percent": int(vi * 100 / max(total_volumes, 1)),
                    "stage": f"Skipped {device_path}: {e}",
                    "drive": f"{letter}:", "found_count": len(candidates), "speed_mbps": 0,
                }))
                continue

            try:
                sector_size = _get_sector_size(handle)
                # Ensure chunk is sector-aligned
                chunk_size = ((SCAN_CHUNK + sector_size - 1) // sector_size) * sector_size

                drive_size = _get_disk_size(handle)
                if drive_size <= 0:
                    # Fallback: try reading until EOF
                    drive_size = 500 * 1024 * 1024 * 1024

                # Immediate initial progress so the UI shows activity
                self.progressChanged.emit(json.dumps({
                    "percent": int(vi * 100 / max(total_volumes, 1)),
                    "stage": f"Scanning {device_path} — 0 MiB of {drive_size // (1024*1024)} MiB",
                    "drive": f"{letter}:", "found_count": len(candidates), "speed_mbps": 0,
                }))

                read_pos = 0
                leftover = b""
                t0 = time.monotonic()
                bytes_since_report = 0

                while read_pos < drive_size:
                    if self._cancel.is_set():
                        break

                    try:
                        chunk = _read_chunk(handle, read_pos, chunk_size, sector_size)
                    except Exception:
                        # Unreadable sector region — skip forward
                        read_pos += chunk_size
                        bytes_since_report += chunk_size
                        continue

                    if not chunk:
                        break

                    # Save the leftover length BEFORE building buf so offset
                    # calculation is correct, then clear leftover.
                    leftover_len = len(leftover)
                    buf = leftover + chunk
                    leftover = b""

                    try:
                        for sig_name, (header, footer, max_size, ext) in sigs.items():
                            search_pos = 0
                            while search_pos < len(buf):
                                idx = buf.find(header, search_pos)
                                if idx == -1:
                                    break
                                # Absolute disk offset: read_pos is where `chunk` started;
                                # leftover_len bytes from the prior chunk precede it in buf.
                                abs_offset = max(0, read_pos + idx - leftover_len)

                                end_off = self._find_end(buf, idx, header, footer, min(max_size, len(buf) - idx))
                                size_guess = end_off - idx
                                has_footer = footer and buf[idx:end_off].endswith(footer)
                                confidence = 80 if has_footer else 40

                                # For mp4, the actual file starts 4 bytes before `ftyp`
                                if sig_name == "mp4" and abs_offset >= 4:
                                    abs_offset -= 4
                                    size_guess += 4

                                preview = self._extract_preview(buf[idx:idx + 256], sig_name)
                                sha = hashlib.sha256(buf[idx:idx + min(4096, size_guess)]).hexdigest()[:16]

                                cand_obj = {
                                    "id": cid, "drive": f"{letter}:",
                                    "offset_start": abs_offset,
                                    "offset_end_guess": abs_offset + size_guess,
                                    "offset_hex": f"0x{abs_offset:X}",
                                    "type": sig_name, "size_guess": size_guess,
                                    "confidence": confidence, "preview_text": preview,
                                    "sha256_guess": sha,
                                }
                                candidates.append(cand_obj)
                                self._emit_candidate(cand_obj)
                                cid += 1
                                search_pos = end_off
                    except Exception:
                        pass  # Skip malformed chunk without aborting

                    # Overlap for cross-chunk header detection
                    if len(buf) > OVERLAP_SIZE:
                        leftover = buf[-OVERLAP_SIZE:]

                    read_pos += len(chunk)
                    bytes_since_report += len(chunk)

                    # Report every 4 MiB for responsive UI
                    if bytes_since_report >= 4 * 1024 * 1024:
                        elapsed = time.monotonic() - t0
                        speed = (read_pos / (1024 * 1024)) / max(elapsed, 0.001)
                        pct_drive = int(read_pos * 100 / drive_size) if drive_size else 0
                        pct_total = int((vi * 100 + pct_drive) / total_volumes)
                        self.progressChanged.emit(json.dumps({
                            "percent": min(pct_total, 99),
                            "stage": f"Scanning {device_path} — {read_pos // (1024*1024)} MiB",
                            "drive": f"{letter}:",
                            "found_count": len(candidates),
                            "speed_mbps": round(speed, 1),
                        }))
                        bytes_since_report = 0
            except Exception as exc:
                # Per-volume failure — report and continue to next volume
                self.progressChanged.emit(json.dumps({
                    "percent": int(vi * 100 / max(total_volumes, 1)),
                    "stage": f"Error on {device_path}: {exc}",
                    "drive": f"{letter}:", "found_count": len(candidates), "speed_mbps": 0,
                }))
            finally:
                _close_handle(handle)

        self.progressChanged.emit(json.dumps({
            "percent": 100, "stage": "Scan complete",
            "drive": "", "found_count": len(candidates), "speed_mbps": 0,
        }))
        return candidates, cid

    # ── Helpers ──────────────────────────────────────────────────────
    def _get_target_sigs(self):
        if self.target_type == "any":
            return ALL_SIGS
        if self.target_type in SIGNATURES and SIGNATURES[self.target_type] is not None:
            return {self.target_type: SIGNATURES[self.target_type]}
        return ALL_SIGS

    @staticmethod
    def _find_end(data, start, header, footer, max_window):
        end_limit = min(start + max_window, len(data))
        if footer:
            search_from = start + len(header)
            idx = data.find(footer, search_from, end_limit)
            if idx != -1:
                return idx + len(footer)
        return min(start + max_window, len(data))

    @staticmethod
    def _extract_preview(head_bytes, sig_type):
        if sig_type == "pdf":
            try:
                text = head_bytes.decode("latin-1", errors="replace")
                lines = text.split("\n")
                preview = " ".join(l.strip() for l in lines[:3] if l.strip())
                return preview[:80]
            except Exception:
                return ""
        return head_bytes[:16].hex(" ").upper()

    def _emit_candidate(self, cand_obj):
        """Add candidate to pending batch; flush if interval elapsed."""
        self._pending_batch.append(cand_obj)
        now = time.monotonic()
        if now - self._last_batch_time >= self.BATCH_INTERVAL:
            self._flush_batch()

    def _flush_batch(self):
        """Emit all pending candidates as a single batch signal."""
        if self._pending_batch:
            self.candidateBatch.emit(json.dumps(self._pending_batch))
            self._pending_batch = []
            self._last_batch_time = time.monotonic()


# ── Recover worker ───────────────────────────────────────────────────────

class _RecoverWorker(QThread):
    progressChanged = Signal(str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, candidates: list, output_dir: str, demo: bool = False):
        super().__init__()
        self.candidates = candidates
        self.output_dir = output_dir
        self.demo = demo
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def run(self):
        try:
            recovered = []
            total = len(self.candidates)
            out_base = Path(self.output_dir) / "Recovered"
            out_base.mkdir(parents=True, exist_ok=True)

            for i, cand in enumerate(self.candidates):
                if self._cancel.is_set():
                    break

                ctype = cand["type"]
                ext = SIGNATURES.get(ctype, (None, None, None, f".{ctype}"))[3] if ctype in SIGNATURES else f".{ctype}"
                type_dir = out_base / ctype
                type_dir.mkdir(exist_ok=True)
                out_path = type_dir / f"candidate_{cand['id']}{ext}"

                try:
                    data = self._read_candidate(cand)
                    if data:
                        out_path.write_bytes(data)
                        recovered.append(str(out_path))
                except Exception as exc:
                    self.error.emit(f"Failed to recover candidate {cand['id']}: {exc}")

                self.progressChanged.emit(json.dumps({
                    "percent": int((i + 1) * 100 / total),
                    "done": i + 1,
                    "total": total,
                }))

            stats = {
                "total_recovered": len(recovered),
                "total_attempted": total,
                "output_dir": str(out_base),
            }
            self.finished.emit(json.dumps({
                "recovered_paths": recovered,
                "output_dir": str(out_base),
                "stats": stats,
            }))
        except Exception as exc:
            self.error.emit(str(exc))

    def _read_candidate(self, cand):
        start = cand["offset_start"]
        end = cand["offset_end_guess"]
        length = end - start
        drive = cand["drive"]

        if drive == "demo_blob" or self.demo:
            if DEMO_BLOB_PATH.exists():
                all_data = DEMO_BLOB_PATH.read_bytes()
                return all_data[start:end]
            return None

        # Use Win32 CreateFile for real disk access
        device_path = f"\\\\.\\{drive}"
        handle = _open_raw_device(device_path)
        try:
            sector_size = _get_sector_size(handle)
            return _read_aligned(handle, start, length, sector_size)
        finally:
            _close_handle(handle)


# ── Controller exposed to QML ────────────────────────────────────────────

class RecoveryController(QObject):
    recoveryScanProgressChanged = Signal(str)
    recoveryScanCandidateFound = Signal(str)
    recoveryScanCandidateBatch = Signal(str)  # JSON array of candidates
    recoveryScanFinished = Signal(str)
    recoveryScanError = Signal(str)

    recoveryRecoverProgressChanged = Signal(str)
    recoveryRecoverFinished = Signal(str)
    recoveryRecoverError = Signal(str)

    recoveryAdminStatus = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scan_worker = None
        self._recover_worker = None
        self._candidates = []

    @Slot(result=bool)
    def checkAdmin(self):
        is_admin = _is_admin()
        self.recoveryAdminStatus.emit(is_admin)
        return is_admin

    @Slot(str)
    def startRecoveryScan(self, target_type: str):
        if self._scan_worker and self._scan_worker.isRunning():
            self.recoveryScanError.emit("Scan already running.")
            return

        demo = not _is_admin()
        if demo and not DEMO_BLOB_PATH.exists():
            self.recoveryScanError.emit(
                "Administrator privileges required for raw disk access. "
                "No demo data available."
            )
            return

        self._candidates = []
        self._scan_worker = _ScanWorker(target_type, demo=demo)
        self._scan_worker.progressChanged.connect(self.recoveryScanProgressChanged.emit)
        self._scan_worker.candidateFound.connect(self._on_candidate_found)
        self._scan_worker.candidateBatch.connect(self._on_candidate_batch)
        self._scan_worker.finished.connect(self._on_scan_done)
        self._scan_worker.error.connect(self.recoveryScanError.emit)
        self._scan_worker.start()

    def _on_candidate_found(self, json_str):
        """Individual candidate — only used if no batching."""
        pass  # Batching handles accumulation

    def _on_candidate_batch(self, json_str):
        batch = json.loads(json_str)
        self._candidates.extend(batch)
        self.recoveryScanCandidateBatch.emit(json_str)

    def _on_scan_done(self, json_str):
        data = json.loads(json_str)
        # Replace with final authoritative list
        self._candidates = data.get("candidates", [])
        self.recoveryScanFinished.emit(json_str)

    @Slot()
    def cancelRecoveryScan(self):
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.cancel()

    @Slot(str)
    def recoverSelected(self, candidate_ids_json: str):
        if self._recover_worker and self._recover_worker.isRunning():
            self.recoveryRecoverError.emit("Recovery already running.")
            return

        ids = json.loads(candidate_ids_json)
        selected = [c for c in self._candidates if c["id"] in ids]
        if not selected:
            self.recoveryRecoverError.emit("No candidates selected.")
            return

        output_dir = os.environ.get("SENTINEL_RECOVERY_DIR", r"C:\Sentinel_Recovery")
        demo = any(c["drive"] == "demo_blob" for c in selected)

        self._recover_worker = _RecoverWorker(selected, output_dir, demo=demo)
        self._recover_worker.progressChanged.connect(self.recoveryRecoverProgressChanged.emit)
        self._recover_worker.finished.connect(self.recoveryRecoverFinished.emit)
        self._recover_worker.error.connect(self.recoveryRecoverError.emit)
        self._recover_worker.start()

    @Slot()
    def cancelRecover(self):
        if self._recover_worker and self._recover_worker.isRunning():
            self._recover_worker.cancel()

    @Slot(str)
    def openRecoveryFolder(self, path: str):
        folder = Path(path)
        if folder.is_file():
            folder = folder.parent
        if folder.exists():
            os.startfile(str(folder))  # noqa: S606 — Windows only
