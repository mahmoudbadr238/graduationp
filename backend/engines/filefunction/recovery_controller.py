"""File recovery controller using Win32 CreateFile + sector-aligned reads (Windows)
and direct raw block device access (Linux, requires root)."""

import ctypes
import ctypes.wintypes
import hashlib
import json
import os
import re
import subprocess
import sys
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

if sys.platform == "win32":
    kernel32 = ctypes.windll.kernel32
else:
    kernel32 = None  # Linux — Win32 APIs unavailable

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


def _is_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _is_root() -> bool:
    """Root on Linux, Administrator on Windows."""
    if sys.platform == "win32":
        return _is_admin()
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def _detect_linux_root_device() -> str:
    """
    Parse `lsblk` to find the block device that hosts /.
    Falls back to the first detected disk if the mount-point walk fails.
    """
    try:
        result = subprocess.run(
            ["lsblk", "-o", "NAME,TYPE,MOUNTPOINT", "--noheadings", "--raw"],
            capture_output=True, text=True, timeout=5,
        )
        parent_disk = ""
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            name, dev_type = parts[0], parts[1]
            mount = parts[2] if len(parts) > 2 else ""
            if dev_type == "part" and mount == "/":
                # Strip trailing partition suffix: sda1→sda, nvme0n1p1→nvme0n1
                parent_disk = re.sub(r"p?\d+$", "", name)
                break
            if dev_type == "disk" and not parent_disk:
                parent_disk = name  # running fallback
        if parent_disk:
            return f"/dev/{parent_disk}"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    # Hard fallback: first present common device
    for candidate in ("/dev/sda", "/dev/vda", "/dev/nvme0n1", "/dev/hda"):
        if os.path.exists(candidate):
            return candidate
    return ""


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

    def __init__(self, target_type: str, target_drive: str = ""):
        super().__init__()
        self.target_type = target_type.lower().strip().lstrip(".")
        self.target_drive = target_drive.strip().rstrip(":").rstrip("\\") if target_drive else ""
        self._cancel = threading.Event()
        self._pending_batch: list = []
        self._last_batch_time: float = 0.0

    def cancel(self):
        self._cancel.set()

    def run(self):
        try:
            candidates = []
            cid = 0

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

    # ── Volume scan using Win32 CreateFile ──────────────────────────
    def _scan_volumes(self, candidates, cid):
        import psutil
        if self.target_drive:
            volumes = [self.target_drive]
        else:
            volumes = []
            for part in psutil.disk_partitions(all=False):
                letter = part.device.rstrip("\\").rstrip(":")
                if len(letter) == 1:
                    volumes.append(letter)
            if not volumes:
                volumes = [chr(x) for x in range(67, 91) if os.path.exists(f"{chr(x)}:\\")]
                if sys.platform == "win32" and os.path.exists("C:\\"):
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


# ── Linux raw block scanner ─────────────────────────────────────────────

_LINUX_SIGNATURES = {
    "jpg":  (b"\xFF\xD8\xFF",          b"\xFF\xD9",               25 * 1024 * 1024, ".jpg"),
    "pdf":  (b"%PDF-",                 b"%%EOF",                  50 * 1024 * 1024, ".pdf"),
    "png":  (b"\x89PNG\r\n\x1a\n",    b"IEND\xaeB`\x82",         25 * 1024 * 1024, ".png"),
    "mp4":  (b"ftyp",                  None,                     200 * 1024 * 1024, ".mp4"),
    "zip":  (b"PK\x03\x04",           None,                     100 * 1024 * 1024, ".zip"),
    "docx": (b"PK\x03\x04",           None,                      50 * 1024 * 1024, ".docx"),
}

_LINUX_CHUNK_SIZE  = 1 * 1024 * 1024   # 1 MiB per read
_LINUX_OVERLAP     = 1024              # cross-boundary guard bytes
_LINUX_MAX_CHUNKS  = 500               # 500 MB default scan depth (configurable via SENTINEL_RECOVERY_MAX_MB)


class _LinuxScanWorker(QThread):
    """Raw block scanner for Linux.  Uses direct open('/dev/sdX','rb')."""

    progressChanged = Signal(str)
    candidateFound  = Signal(str)
    candidateBatch  = Signal(str)
    finished        = Signal(str)
    error           = Signal(str)

    BATCH_INTERVAL = 0.4

    def __init__(self, target_type: str, device: str = ""):
        super().__init__()
        self.target_type = target_type.lower().strip().lstrip(".")
        self.device      = device
        self._cancel     = threading.Event()
        self._pending_batch: list  = []
        self._last_batch_time: float = 0.0

    def cancel(self):
        self._cancel.set()

    def run(self):
        try:
            if not _is_root():
                self.error.emit(
                    "Root privileges required for raw disk access. "
                    "Re-run Sentinel with: sudo python main.py"
                )
                return

            device = self.device or _detect_linux_root_device()
            if not device:
                self.error.emit(
                    "Could not detect a block device. "
                    "Pass a device explicitly (e.g. /dev/sda)."
                )
                return

            sigs = self._get_sigs()
            candidates: list[dict] = []
            cid = 0

            self.progressChanged.emit(json.dumps({
                "percent": 0, "stage": f"Opening {device}",
                "drive": device, "found_count": 0, "speed_mbps": 0,
            }))

            try:
                fh = open(device, "rb")  # noqa: SIM115 — intentional raw open
            except PermissionError:
                self.error.emit(
                    f"Permission denied: {device}. "
                    "Sentinel must run as root for raw disk access."
                )
                return
            except OSError as exc:
                self.error.emit(f"Cannot open {device}: {exc}")
                return

            with fh:
                t0        = time.monotonic()
                read_pos  = 0
                leftover  = b""

                for chunk_idx in range(_LINUX_MAX_CHUNKS):
                    if self._cancel.is_set():
                        break

                    try:
                        chunk = fh.read(_LINUX_CHUNK_SIZE)
                    except OSError:
                        # Unreadable sector — skip one chunk forward
                        try:
                            fh.seek(_LINUX_CHUNK_SIZE, 1)
                        except OSError:
                            break
                        read_pos += _LINUX_CHUNK_SIZE
                        continue

                    if not chunk:
                        break  # EOF

                    leftover_len = len(leftover)
                    buf      = leftover + chunk
                    leftover = buf[-_LINUX_OVERLAP:] if len(buf) > _LINUX_OVERLAP else buf

                    try:
                        for sig_name, (header, footer, max_sz, _ext) in sigs.items():
                            search = 0
                            while search < len(buf):
                                idx = buf.find(header, search)
                                if idx == -1:
                                    break
                                abs_off  = max(0, read_pos + idx - leftover_len)
                                end_off  = self._find_end(buf, idx, header, footer,
                                                          min(max_sz, len(buf) - idx))
                                size_guess = end_off - idx
                                has_footer = bool(footer and buf[idx:end_off].endswith(footer))
                                confidence = 80 if has_footer else 42
                                sha = hashlib.sha256(
                                    buf[idx: idx + min(4096, size_guess)]
                                ).hexdigest()[:16]
                                cand_obj = {
                                    "id":               cid,
                                    "drive":            device,
                                    "offset_start":     abs_off,
                                    "offset_end_guess": abs_off + size_guess,
                                    "offset_hex":       f"0x{abs_off:X}",
                                    "type":             sig_name,
                                    "size_guess":       size_guess,
                                    "confidence":       confidence,
                                    "preview_text":     buf[idx: idx + 16].hex(" ").upper(),
                                    "sha256_guess":     sha,
                                }
                                candidates.append(cand_obj)
                                self._emit_candidate(cand_obj)
                                cid    += 1
                                search  = end_off
                    except Exception:
                        pass  # malformed region — keep scanning

                    read_pos += len(chunk)

                    if chunk_idx % 4 == 0:
                        elapsed = time.monotonic() - t0
                        speed   = (read_pos / (1024 * 1024)) / max(elapsed, 0.001)
                        self.progressChanged.emit(json.dumps({
                            "percent":     min(int(chunk_idx * 100 / _LINUX_MAX_CHUNKS), 99),
                            "stage":       f"Scanning {device} — {read_pos // (1024 * 1024)} MiB",
                            "drive":       device,
                            "found_count": len(candidates),
                            "speed_mbps":  round(speed, 1),
                        }))

            self._flush_batch()
            self.progressChanged.emit(json.dumps({
                "percent": 100, "stage": "Scan complete",
                "drive": device, "found_count": len(candidates), "speed_mbps": 0,
            }))
            default_dir = os.environ.get("SENTINEL_RECOVERY_DIR", "/tmp/Sentinel_Recovery")
            self.finished.emit(json.dumps({
                "candidates": candidates,
                "output_dir": default_dir,
                "stats": {
                    "total_candidates": len(candidates),
                    "drives_scanned":   1,
                },
            }))

        except Exception as exc:
            self.error.emit(str(exc))

    # ── helpers ──────────────────────────────────────────────────────────

    def _get_sigs(self) -> dict:
        if self.target_type == "any" or self.target_type not in _LINUX_SIGNATURES:
            return _LINUX_SIGNATURES
        return {self.target_type: _LINUX_SIGNATURES[self.target_type]}

    @staticmethod
    def _find_end(data: bytes, start: int, header: bytes,
                  footer: bytes | None, max_window: int) -> int:
        end_limit = min(start + max_window, len(data))
        if footer:
            idx = data.find(footer, start + len(header), end_limit)
            if idx != -1:
                return idx + len(footer)
        return end_limit

    def _emit_candidate(self, cand_obj: dict):
        self._pending_batch.append(cand_obj)
        if time.monotonic() - self._last_batch_time >= self.BATCH_INTERVAL:
            self._flush_batch()

    def _flush_batch(self):
        if self._pending_batch:
            self.candidateBatch.emit(json.dumps(self._pending_batch))
            self._pending_batch      = []
            self._last_batch_time    = time.monotonic()


# ── Recover worker ───────────────────────────────────────────────────────

class _RecoverWorker(QThread):
    progressChanged = Signal(str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, candidates: list, output_dir: str):
        super().__init__()
        self.candidates = candidates
        self.output_dir = output_dir
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
        start  = cand["offset_start"]
        end    = cand["offset_end_guess"]
        length = end - start
        drive  = cand["drive"]

        # Linux raw device (path starts with /dev/)
        if sys.platform != "win32":
            try:
                with open(drive, "rb") as fh:
                    fh.seek(start)
                    return fh.read(length)
            except (PermissionError, OSError):
                return None

        # Windows — Win32 CreateFile sector-aligned read
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
        is_admin = _is_root()
        self.recoveryAdminStatus.emit(is_admin)
        return is_admin

    @Slot(result=str)
    def getAvailableDrives(self):
        """Return JSON array of available drives (letters on Windows, /dev/sdX on Linux)."""
        if sys.platform != "win32":
            try:
                result = subprocess.run(
                    ["lsblk", "-o", "NAME,TYPE", "--noheadings", "--raw"],
                    capture_output=True, text=True, timeout=5,
                )
                drives = [
                    f"/dev/{parts[0]}"
                    for line in result.stdout.splitlines()
                    if len((parts := line.split())) >= 2 and parts[1] == "disk"
                ]
                return json.dumps(drives if drives else [])
            except Exception:
                return json.dumps([])
        try:
            import psutil
            drives = []
            for part in psutil.disk_partitions(all=False):
                letter = part.device.rstrip("\\").rstrip(":")
                if len(letter) == 1:
                    drives.append(letter + ":")
            if not drives:
                drives = [chr(x) + ":" for x in range(67, 91) if os.path.exists(f"{chr(x)}:\\")]
            return json.dumps(drives)
        except Exception:
            return json.dumps([])

    @Slot(str, str)
    def startRecoveryScan(self, target_type: str, drive: str = ""):
        if self._scan_worker and self._scan_worker.isRunning():
            self.recoveryScanError.emit("Scan already running.")
            return

        self._candidates = []

        if sys.platform != "win32":
            # Linux path — raw open() via _LinuxScanWorker (requires root)
            device = drive if drive.startswith("/dev/") else ""
            self._scan_worker = _LinuxScanWorker(target_type, device=device)
        else:
            # Windows path — Win32 CreateFile via _ScanWorker (requires Administrator)
            if not _is_admin():
                self.recoveryScanError.emit(
                    "Administrator privileges required for raw disk access. "
                    "Restart Sentinel as Administrator to use File Recovery."
                )
                return
            self._scan_worker = _ScanWorker(target_type, target_drive=drive)

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

        _default = "/tmp/Sentinel_Recovery" if sys.platform != "win32" else r"C:\Sentinel_Recovery"
        output_dir = os.environ.get("SENTINEL_RECOVERY_DIR", _default)

        self._recover_worker = _RecoverWorker(selected, output_dir)
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
        if not folder.exists():
            return
        if sys.platform == "win32":
            os.startfile(str(folder))  # noqa: S606
        else:
            try:
                subprocess.Popen(["xdg-open", str(folder)])
            except (FileNotFoundError, OSError):
                pass
