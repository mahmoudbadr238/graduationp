import os
import random
import string
from PySide6.QtCore import QObject, Slot, Signal, QThread


class ShredderWorker(QThread):
    progress = Signal(int)
    log = Signal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        if not os.path.exists(self.file_path):
            self.log.emit("Error: File not found.")
            return

        try:
            file_size = os.path.getsize(self.file_path)
            self.progress.emit(10)

            with open(self.file_path, "r+b") as f:
                for i in range(3):
                    f.seek(0)
                    if i < 2:
                        f.write(os.urandom(file_size))
                    else:
                        f.write(b'\x00' * file_size)

                    os.fsync(f.fileno())
                    self.progress.emit(10 + ((i + 1) * 25))

            dir_name = os.path.dirname(self.file_path)
            random_name = ''.join(random.choices(string.ascii_letters + string.digits, k=16)) + ".tmp"
            scrambled_path = os.path.join(dir_name, random_name)

            os.rename(self.file_path, scrambled_path)
            os.remove(scrambled_path)

            self.progress.emit(100)
            self.log.emit("Success: File permanently destroyed.")

        except Exception as e:
            self.log.emit(f"Shredding failed: {str(e)}")


# ---------------------------------------------------------------------------
# Comprehensive file-signature registry keyed by lowercase extension.
# Each value is the magic-number byte prefix used for raw-disk matching.
# ---------------------------------------------------------------------------
MAGIC_SIGNATURES = {
    # Documents
    ".pdf":  b"%PDF",
    ".docx": b"PK\x03\x04",
    ".xlsx": b"PK\x03\x04",
    ".pptx": b"PK\x03\x04",
    ".odt":  b"PK\x03\x04",
    ".ods":  b"PK\x03\x04",
    ".odp":  b"PK\x03\x04",
    ".doc":  b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1",
    ".xls":  b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1",
    ".ppt":  b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1",
    ".rtf":  b"{\\rtf",

    # Images
    ".jpg":  b"\xFF\xD8\xFF",
    ".jpeg": b"\xFF\xD8\xFF",
    ".png":  b"\x89PNG\r\n\x1A\n",
    ".gif":  b"GIF89a",
    ".bmp":  b"BM",
    ".tiff": b"II\x2A\x00",
    ".tif":  b"II\x2A\x00",
    ".webp": b"RIFF",
    ".ico":  b"\x00\x00\x01\x00",
    ".svg":  b"<?xml",

    # Audio
    ".mp3":  b"\xFF\xFB",
    ".wav":  b"RIFF",
    ".flac": b"fLaC",
    ".ogg":  b"OggS",
    ".aac":  b"\xFF\xF1",
    ".wma":  b"\x30\x26\xB2\x75",
    ".m4a":  b"\x00\x00\x00",

    # Video
    ".mp4":  b"\x00\x00\x00",
    ".avi":  b"RIFF",
    ".mkv":  b"\x1A\x45\xDF\xA3",
    ".mov":  b"\x00\x00\x00",
    ".wmv":  b"\x30\x26\xB2\x75",
    ".flv":  b"FLV\x01",
    ".webm": b"\x1A\x45\xDF\xA3",

    # Archives
    ".zip":  b"PK\x03\x04",
    ".rar":  b"Rar!\x1A\x07",
    ".7z":   b"7z\xBC\xAF\x27\x1C",
    ".gz":   b"\x1F\x8B",
    ".tar":  b"ustar",
    ".bz2":  b"BZh",
    ".xz":   b"\xFD7zXZ\x00",
    ".zst":  b"\x28\xB5\x2F\xFD",

    # Executables / Libraries
    ".exe":  b"MZ",
    ".dll":  b"MZ",
    ".elf":  b"\x7FELF",
    ".msi":  b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1",

    # Databases
    ".sqlite": b"SQLite format 3",
    ".db":     b"SQLite format 3",

    # Other
    ".class": b"\xCA\xFE\xBA\xBE",
    ".swf":   b"FWS",
    ".psd":   b"8BPS",
    ".iso":   b"CD001",
}


class CarverWorker(QThread):
    log = Signal(str)

    def __init__(self, extension_input):
        super().__init__()
        self.extension_input = extension_input

    def run(self):
        ext = self.extension_input.strip().lower()
        if not ext.startswith("."):
            ext = "." + ext

        target_sig = MAGIC_SIGNATURES.get(ext)
        if target_sig is None:
            supported = ", ".join(sorted(MAGIC_SIGNATURES.keys()))
            self.log.emit(
                f"[!] Unknown signature for '{ext}'.\n"
                f"    Supported extensions:\n    {supported}"
            )
            return

        self.log.emit(f"[*] Starting system-wide sweep for {ext} files...")
        self.log.emit(f"[*] Magic signature: {target_sig.hex(' ').upper()}")

        drives = [f"{chr(x)}:" for x in range(65, 91) if os.path.exists(f"{chr(x)}:\\")]
        self.log.emit(f"[*] Detected drives: {', '.join(drives)}")

        output_dir = r"C:\Sentinel_Recovery"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        for drive in drives:
            raw_path = f"\\\\.\\{drive}"
            self.log.emit(f"\n[+] Mounting raw physical drive {raw_path}...")

            try:
                with open(raw_path, "rb") as d:
                    chunk_size = 512
                    for sector in range(50000):
                        d.seek(sector * chunk_size)
                        data = d.read(chunk_size)

                        if data and data.startswith(target_sig):
                            clean_ext = ext.lstrip(".")
                            rec_file = os.path.join(
                                output_dir,
                                f"recovered_{drive[0]}_{sector}.{clean_ext}"
                            )
                            with open(rec_file, "wb") as out:
                                out.write(data)
                                out.write(d.read(chunk_size * 10))
                            self.log.emit(
                                f"[!] CARVED: Found match at sector {sector} -> {rec_file}"
                            )

            except PermissionError:
                self.log.emit(
                    f"[CRITICAL] Access Denied on {drive}. "
                    f"Sentinel MUST be run as Administrator!"
                )
            except Exception as e:
                self.log.emit(f"[-] Drive {drive} skipped: {str(e)}")

        self.log.emit("\n[*] System sweep complete.")


class FileFunctionBridge(QObject):
    shredProgressUpdated = Signal(int)
    carverLogUpdated = Signal(str)

    def __init__(self):
        super().__init__()
        self.shred_thread = None
        self.carver_thread = None

    @Slot(str)
    def start_shredding(self, file_path):
        if self.shred_thread and self.shred_thread.isRunning():
            return

        self.shred_thread = ShredderWorker(file_path)
        self.shred_thread.progress.connect(self.shredProgressUpdated.emit)
        self.shred_thread.log.connect(self.carverLogUpdated.emit)
        self.shred_thread.start()

    @Slot(str)
    def start_recovery(self, extension_input):
        if self.carver_thread and self.carver_thread.isRunning():
            self.carverLogUpdated.emit("[-] Sweep already in progress. Please wait.")
            return

        self.carver_thread = CarverWorker(extension_input)
        self.carver_thread.log.connect(self.carverLogUpdated.emit)
        self.carver_thread.start()
