"""
Window Capture Service - Captures frames from sandboxed process windows.

Provides live video-like preview of sandbox execution:
- Finds window by PID (including child processes)
- Captures frames at configurable FPS
- Stores frames for session recording
- Thread-safe frame delivery to UI

Windows-only implementation using Win32 API.
"""

import ctypes
import logging
import os
import threading
import time
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

NOISE_WINDOW_TITLE_TOKENS = (
    "task switching",
    "task view",
    "program manager",
    "start",
    "search",
    "action center",
    "notification center",
    "widgets",
)
NOISE_WINDOW_PROCESS_NAMES = {
    "explorer.exe",
    "dwm.exe",
    "shellexperiencehost.exe",
    "startmenuexperiencehost.exe",
    "searchhost.exe",
    "searchapp.exe",
    "taskmgr.exe",
    "ctfmon.exe",
    "applicationframehost.exe",
}

# Windows API constants
IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    kernel32 = ctypes.windll.kernel32

    # Window constants
    GWL_STYLE = -16
    WS_VISIBLE = 0x10000000
    WS_MINIMIZE = 0x20000000

    # BitBlt constants
    SRCCOPY = 0x00CC0020
    CAPTUREBLT = 0x40000000

    # PrintWindow flag
    PW_RENDERFULLCONTENT = 0x00000002

    # Process enumeration constants
    TH32CS_SNAPPROCESS = 0x00000002

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_char * 260),
        ]


def get_child_pids(parent_pid: int, max_depth: int = 10) -> set[int]:
    """
    Get all child process PIDs for a given parent PID.
    
    Uses Windows Toolhelp32 API to enumerate process tree.
    Returns set of all descendant PIDs including the parent.
    """
    if not IS_WINDOWS:
        return {parent_pid}

    result = {parent_pid}

    try:
        # Create snapshot of all processes
        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == -1:
            return result

        try:
            pe32 = PROCESSENTRY32()
            pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)

            # Build parent->children map
            children_map: dict[int, list[int]] = {}

            if kernel32.Process32First(snapshot, ctypes.byref(pe32)):
                while True:
                    pid = pe32.th32ProcessID
                    ppid = pe32.th32ParentProcessID

                    if ppid not in children_map:
                        children_map[ppid] = []
                    children_map[ppid].append(pid)

                    if not kernel32.Process32Next(snapshot, ctypes.byref(pe32)):
                        break

            # BFS to find all descendants
            queue = [parent_pid]
            depth = 0
            while queue and depth < max_depth:
                next_queue = []
                for pid in queue:
                    if pid in children_map:
                        for child_pid in children_map[pid]:
                            if child_pid not in result:
                                result.add(child_pid)
                                next_queue.append(child_pid)
                queue = next_queue
                depth += 1

        finally:
            kernel32.CloseHandle(snapshot)

    except Exception as e:
        logger.debug(f"Error enumerating child processes: {e}")

    return result


def get_pids_by_exe_name(exe_name: str) -> set[int]:
    """
    Get all PIDs for processes with the given executable name.
    
    Args:
        exe_name: Executable name (e.g., "game.exe") - case insensitive
        
    Returns:
        Set of PIDs matching the executable name
    """
    if not IS_WINDOWS:
        return set()

    result = set()
    exe_name_lower = exe_name.lower()
    exe_stem = Path(exe_name_lower).stem

    try:
        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == -1:
            return result

        try:
            pe32 = PROCESSENTRY32()
            pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)

            if kernel32.Process32First(snapshot, ctypes.byref(pe32)):
                while True:
                    try:
                        proc_exe = pe32.szExeFile.decode("utf-8", errors="ignore").lower()
                        proc_stem = Path(proc_exe).stem
                        if (
                            proc_exe == exe_name_lower
                            or proc_exe.endswith(exe_name_lower)
                            or proc_stem == exe_stem
                        ):
                            result.add(pe32.th32ProcessID)
                    except Exception:
                        pass

                    if not kernel32.Process32Next(snapshot, ctypes.byref(pe32)):
                        break
        finally:
            kernel32.CloseHandle(snapshot)

    except Exception as e:
        logger.debug(f"Error finding processes by exe name: {e}")

    return result


def get_pid_to_exe_map() -> dict[int, str]:
    """Return map of PID -> executable name (lowercase)."""
    if not IS_WINDOWS:
        return {}

    result: dict[int, str] = {}
    try:
        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == -1:
            return result

        try:
            pe32 = PROCESSENTRY32()
            pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)

            if kernel32.Process32First(snapshot, ctypes.byref(pe32)):
                while True:
                    try:
                        proc_exe = pe32.szExeFile.decode("utf-8", errors="ignore").lower()
                        result[int(pe32.th32ProcessID)] = proc_exe
                    except Exception:
                        pass

                    if not kernel32.Process32Next(snapshot, ctypes.byref(pe32)):
                        break
        finally:
            kernel32.CloseHandle(snapshot)
    except Exception as e:
        logger.debug(f"Error building PID->EXE map: {e}")

    return result


def is_noise_window_title(title: str) -> bool:
    """Heuristic to ignore generic system overlay windows."""
    normalized = (title or "").strip().lower()
    if not normalized:
        return True
    return any(token in normalized for token in NOISE_WINDOW_TITLE_TOKENS)


def get_all_visible_windows() -> dict[int, tuple[int, str]]:
    """
    Get all currently visible windows.
    
    Returns:
        Dict mapping hwnd -> (pid, title)
    """
    if not IS_WINDOWS:
        return {}

    windows = {}

    def enum_callback(hwnd, lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True

            # Get window size
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            width = rect.right - rect.left
            height = rect.bottom - rect.top

            # Skip tiny windows
            if width * height < 10000:
                return True

            # Get PID
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            # Get title
            length = user32.GetWindowTextLengthW(hwnd)
            title = ""
            if length:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                title = buffer.value

            windows[hwnd] = (pid.value, title)

        except Exception:
            pass

        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

    return windows


@dataclass
class CapturedFrame:
    """A single captured frame from the sandbox window."""
    timestamp: str
    frame_number: int
    width: int
    height: int
    data: bytes  # Raw BGRA pixel data
    window_title: str = ""


class WindowCaptureService:
    """
    Captures frames from a sandboxed process window.
    
    Features:
    - Finds main window by PID with retry logic
    - Captures at configurable FPS (5-10 recommended)
    - Stores frames to disk for session recording
    - Thread-safe frame delivery via callback
    - Friendly messages for console-only processes
    
    Usage:
        capture = WindowCaptureService(
            target_pid=1234,
            fps=8,
            session_folder=Path("./sandbox_session"),
            frame_callback=lambda data, w, h: provider.update_frame(data, w, h),
            window_found_callback=lambda found, title: print(f"Window: {title}"),
        )
        capture.start()
        # ... sandbox runs ...
        stats = capture.stop()
    """

    # Class constants for retry behavior
    WINDOW_SEARCH_TIMEOUT = 30.0  # Max seconds to search for a window
    WINDOW_RETRY_INTERVAL = 0.5   # Seconds between window searches
    CONSOLE_WAIT_TIME = 10.0      # After this time, assume console-only (increased for slow apps)

    def __init__(
        self,
        target_pid: int,
        fps: int = 8,
        session_folder: Path | None = None,
        frame_callback: Callable[[bytes, int, int], None] | None = None,
        window_found_callback: Callable[[bool, str], None] | None = None,
        status_callback: Callable[[str], None] | None = None,
        save_frames: bool = True,
        max_frames: int = 500,
        exe_name: str | None = None,  # Executable name to search for windows
        # Legacy parameter aliases for backward compatibility
        output_dir: Path | None = None,
    ):
        """
        Initialize the capture service.
        
        Args:
            target_pid: PID of the sandboxed process
            fps: Frames per second to capture (default 8)
            session_folder: Where to save frames (optional)
            frame_callback: Called with (frame_data, width, height) for each frame
            window_found_callback: Called with (found: bool, title: str) when window state changes
            status_callback: Called with status message strings
            save_frames: Whether to save frames to disk
            max_frames: Maximum frames to store (to limit disk usage)
            exe_name: Executable name (e.g., "game.exe") for fallback window search
            output_dir: Alias for session_folder (backward compatibility)
        """
        self.target_pid = target_pid
        self.pid = target_pid  # Alias for compatibility
        self.fps = min(max(fps, 1), 15)  # Clamp to 1-15 FPS
        self.session_folder = session_folder or output_dir
        self.frame_callback = frame_callback
        self.window_found_callback = window_found_callback
        self.status_callback = status_callback
        self.save_frames = save_frames
        self.max_frames = max_frames
        self.exe_name = exe_name.lower() if exe_name else None  # Store lowercase for comparison

        # State
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._hwnd: int | None = None
        self._window_title: str = ""
        self._frame_count = 0
        self._last_frame: CapturedFrame | None = None
        self._frames_folder: Path | None = None
        self._window_search_start: float | None = None
        self._console_mode_reported = False
        self._baseline_windows: set[int] = set()  # Windows that existed before sandbox started

        # Callbacks (can also be set as attributes after construction)
        self.on_frame: Callable[[int, bytes, int, int], None] | None = None  # Legacy callback format
        self.on_window_found: Callable[[bool], None] | None = None  # Legacy callback format

        # Stats
        self.capture_stats = {
            "frames_captured": 0,
            "frames_saved": 0,
            "last_capture_time": None,
            "window_found": False,
            "window_title": "",
            "window_size": (0, 0),
            "is_console_only": False,
        }

        # Take snapshot of existing windows (baseline)
        self._baseline_windows = set(get_all_visible_windows().keys())
        logger.debug(f"Baseline windows: {len(self._baseline_windows)} windows exist before sandbox")

        # Create frames folder if saving
        if self.save_frames and self.session_folder:
            self._frames_folder = self.session_folder / "frames"
            self._frames_folder.mkdir(parents=True, exist_ok=True)

    def start(self) -> bool:
        """
        Start capturing frames in background thread.
        
        Returns:
            bool: True if started successfully
        """
        if self._running:
            return True

        self._running = True
        self._stop_event.clear()
        self._window_search_start = time.time()
        self._console_mode_reported = False

        # Emit initial status
        self._emit_status("Launching sandbox...")

        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info(f"Window capture started for PID {self.target_pid}")
        return True

    def stop(self) -> dict[str, Any]:
        """Stop capturing and return stats."""
        self._running = False
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        logger.info(f"Window capture stopped. Captured {self._frame_count} frames.")
        return self.capture_stats.copy()

    def get_last_frame(self) -> CapturedFrame | None:
        """Get the most recently captured frame."""
        return self._last_frame

    def _emit_status(self, status: str) -> None:
        """Emit status message via callback."""
        if self.status_callback:
            try:
                self.status_callback(status)
            except Exception as e:
                logger.warning(f"Status callback error: {e}")

    def _emit_window_found(self, found: bool, title: str = "") -> None:
        """Emit window found status via callbacks."""
        # New-style callback
        if self.window_found_callback:
            try:
                self.window_found_callback(found, title)
            except Exception as e:
                logger.warning(f"Window found callback error: {e}")

        # Legacy callback (bool only)
        if self.on_window_found:
            try:
                self.on_window_found(found)
            except Exception as e:
                logger.warning(f"Legacy window callback error: {e}")

    def _emit_frame(self, frame: "CapturedFrame") -> None:
        """Emit frame via callbacks."""
        # New-style callback
        if self.frame_callback:
            try:
                self.frame_callback(frame.data, frame.width, frame.height)
            except Exception as e:
                logger.warning(f"Frame callback error: {e}")

        # Legacy callback (includes frame number)
        if self.on_frame:
            try:
                self.on_frame(frame.frame_number, frame.data, frame.width, frame.height)
            except Exception as e:
                logger.warning(f"Legacy frame callback error: {e}")

    def _capture_loop(self) -> None:
        """
        Main capture loop running in background thread.
        
        - Retries finding window for up to WINDOW_SEARCH_TIMEOUT seconds
        - Reports console-only mode after CONSOLE_WAIT_TIME seconds
        - Captures frames at configured FPS
        """
        frame_interval = 1.0 / self.fps
        last_window_check = 0.0
        window_was_found = False

        self._emit_status("Searching for sandbox window...")

        while self._running and not self._stop_event.is_set():
            try:
                now = time.time()
                search_elapsed = now - (self._window_search_start or now)

                # Try to find window if we don't have one
                if not self._hwnd or not self._is_window_valid(self._hwnd):
                    if self._hwnd:
                        # Window was lost
                        self._hwnd = None
                        self._emit_status("Window closed, searching...")
                        self._emit_window_found(False, "")

                    if now - last_window_check >= self.WINDOW_RETRY_INTERVAL:
                        self._hwnd = self._find_window_for_pid(self.target_pid)
                        last_window_check = now

                        if self._hwnd:
                            self._window_title = self._get_window_title(self._hwnd)
                            self.capture_stats["window_found"] = True
                            self.capture_stats["window_title"] = self._window_title
                            window_was_found = True
                            self._console_mode_reported = False

                            logger.info(f"Found window for PID {self.target_pid}: {self._window_title}")
                            self._emit_status(f"Capturing: {self._window_title[:35]}..." if len(self._window_title) > 35 else f"Capturing: {self._window_title}")
                            self._emit_window_found(True, self._window_title)

                        elif (
                            not self._console_mode_reported
                            and not window_was_found
                            and search_elapsed > self.CONSOLE_WAIT_TIME
                        ):
                            # No window found after waiting - likely console-only process
                            self._console_mode_reported = True
                            self.capture_stats["is_console_only"] = True
                            logger.info(f"No visible window for PID {self.target_pid} after {search_elapsed:.1f}s - console/background process")
                            self._emit_status("No visible app window (console/background process)")
                            self._emit_window_found(False, "")

                # Capture frame if we have a valid window
                if self._hwnd and self._is_window_valid(self._hwnd):
                    frame = self._capture_frame(self._hwnd)
                    if frame:
                        self._frame_count += 1
                        self._last_frame = frame
                        self.capture_stats["frames_captured"] = self._frame_count
                        self.capture_stats["last_capture_time"] = frame.timestamp
                        self.capture_stats["window_size"] = (frame.width, frame.height)

                        # Deliver frame via callbacks
                        self._emit_frame(frame)

                        # Save to disk
                        if self.save_frames and self._frames_folder and self._frame_count <= self.max_frames:
                            self._save_frame(frame)

                # Wait for next frame
                elapsed = time.time() - now
                sleep_time = max(0, frame_interval - elapsed)
                if sleep_time > 0:
                    self._stop_event.wait(sleep_time)

            except Exception as e:
                logger.warning(f"Capture loop error: {e}")
                time.sleep(0.1)

    def _find_window_for_pid(self, pid: int) -> int | None:
        """
        Find the main visible window for a process or any of its child processes.
        
        This handles apps that spawn child processes to create their main window
        (common with launchers, games, installers, etc.)
        """
        if not IS_WINDOWS:
            return None

        # Get all PIDs in the process tree
        all_pids = get_child_pids(pid)
        logger.debug(f"Searching for window in process tree: {all_pids}")

        found_hwnd = None
        found_area = 0
        found_pid = None

        def enum_callback(hwnd, lparam):
            nonlocal found_hwnd, found_area, found_pid

            try:
                # Check if window belongs to any process in our tree
                window_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))

                if window_pid.value not in all_pids:
                    return True

                # Check if visible
                if not user32.IsWindowVisible(hwnd):
                    return True

                # Get window rect
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))

                width = rect.right - rect.left
                height = rect.bottom - rect.top
                area = width * height

                # Skip tiny windows
                if area < 10000:  # Less than ~100x100
                    return True

                # Prefer larger windows
                if area > found_area:
                    found_hwnd = hwnd
                    found_area = area
                    found_pid = window_pid.value

            except Exception:
                pass

            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

        if found_hwnd and found_pid != pid:
            logger.info(f"Found window in child process PID {found_pid} (parent: {pid})")

        # If no window found and we have an exe_name, search by exe name as fallback
        if not found_hwnd and self.exe_name:
            exe_pids = get_pids_by_exe_name(self.exe_name)
            if exe_pids:
                logger.debug(f"Fallback: searching for windows by exe name '{self.exe_name}': {exe_pids}")

                # Reset search state
                found_hwnd = None
                found_area = 0
                found_pid = None

                def enum_callback_exe(hwnd, lparam):
                    nonlocal found_hwnd, found_area, found_pid

                    try:
                        window_pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))

                        if window_pid.value not in exe_pids:
                            return True

                        if not user32.IsWindowVisible(hwnd):
                            return True

                        rect = wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))

                        width = rect.right - rect.left
                        height = rect.bottom - rect.top
                        area = width * height

                        if area < 10000:
                            return True

                        if area > found_area:
                            found_hwnd = hwnd
                            found_area = area
                            found_pid = window_pid.value

                    except Exception:
                        pass

                    return True

                user32.EnumWindows(WNDENUMPROC(enum_callback_exe), 0)

                if found_hwnd:
                    logger.info(f"Found window by exe name '{self.exe_name}' (PID {found_pid})")

        # Final fallback: find any NEW window that appeared after sandbox started
        if not found_hwnd and self._baseline_windows:
            current_windows = get_all_visible_windows()
            new_windows = {hwnd: info for hwnd, info in current_windows.items()
                          if hwnd not in self._baseline_windows}

            if new_windows:
                pid_to_exe = get_pid_to_exe_map()
                # Find the largest new window
                best_hwnd = None
                best_area = 0
                best_title = ""
                best_pid = 0

                for hwnd, (win_pid, title) in new_windows.items():
                    try:
                        rect = wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        width = rect.right - rect.left
                        height = rect.bottom - rect.top
                        area = width * height

                        # Ignore generic system overlays and shell UI.
                        if is_noise_window_title(title):
                            continue
                        win_exe = pid_to_exe.get(int(win_pid), "")
                        if win_exe in NOISE_WINDOW_PROCESS_NAMES:
                            continue

                        if area > best_area:
                            best_hwnd = hwnd
                            best_area = area
                            best_title = title
                            best_pid = int(win_pid)
                    except Exception:
                        pass

                if best_hwnd and best_area > 10000:
                    found_hwnd = best_hwnd
                    logger.info(
                        "Found NEW window: '%s' (pid=%s, appeared after sandbox started)",
                        best_title,
                        best_pid,
                    )

        return found_hwnd

    def _is_window_valid(self, hwnd: int) -> bool:
        """Check if a window handle is still valid."""
        if not IS_WINDOWS:
            return False
        return bool(user32.IsWindow(hwnd))

    def _get_window_title(self, hwnd: int) -> str:
        """Get the title of a window."""
        if not IS_WINDOWS:
            return ""

        try:
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                return buffer.value
        except Exception:
            pass
        return ""

    def _capture_frame(self, hwnd: int) -> CapturedFrame | None:
        """Capture a single frame from a window."""
        if not IS_WINDOWS:
            return None

        try:
            # Get window dimensions
            rect = wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            width = rect.right - rect.left
            height = rect.bottom - rect.top

            if width <= 0 or height <= 0:
                return None

            # Create compatible DC and bitmap
            hdc_window = user32.GetDC(hwnd)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_window)
            hbm = gdi32.CreateCompatibleBitmap(hdc_window, width, height)

            old_bm = gdi32.SelectObject(hdc_mem, hbm)

            # Try PrintWindow first (works even if partially occluded)
            result = user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)

            if not result:
                # Fallback to BitBlt
                gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_window, 0, 0, SRCCOPY)

            # Get bitmap data
            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", wintypes.DWORD),
                    ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD),
                ]

            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = width
            bmi.biHeight = -height  # Negative for top-down
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0  # BI_RGB

            buffer_size = width * height * 4
            buffer = ctypes.create_string_buffer(buffer_size)

            gdi32.GetDIBits(
                hdc_mem, hbm, 0, height,
                buffer, ctypes.byref(bmi), 0  # DIB_RGB_COLORS
            )

            # Cleanup
            gdi32.SelectObject(hdc_mem, old_bm)
            gdi32.DeleteObject(hbm)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(hwnd, hdc_window)

            return CapturedFrame(
                timestamp=datetime.now().isoformat(),
                frame_number=self._frame_count + 1,
                width=width,
                height=height,
                data=buffer.raw,
                window_title=self._window_title,
            )

        except Exception as e:
            logger.warning(f"Frame capture error: {e}")
            return None

    def _save_frame(self, frame: CapturedFrame) -> None:
        """Save a frame to disk as JPEG."""
        if not self._frames_folder:
            return

        try:
            # Convert BGRA to RGB and save as JPEG using PIL if available
            try:
                from PIL import Image

                # Create image from BGRA data
                img = Image.frombytes("RGBA", (frame.width, frame.height), frame.data, "raw", "BGRA")
                img = img.convert("RGB")

                # Save with compression
                filename = self._frames_folder / f"frame_{frame.frame_number:05d}.jpg"
                img.save(filename, "JPEG", quality=75)

                self.capture_stats["frames_saved"] = frame.frame_number

            except ImportError:
                # PIL not available, save raw (not recommended)
                pass

        except Exception as e:
            logger.warning(f"Failed to save frame: {e}")

    def generate_video(self, output_path: Path | None = None) -> Path | None:
        """
        Generate a video from saved frames.
        
        Requires OpenCV (cv2) to be installed.
        
        Returns:
            Path to the generated video, or None if failed
        """
        if not self._frames_folder or not self._frames_folder.exists():
            return None

        try:
            import cv2

            # Get all frame files
            frame_files = sorted(self._frames_folder.glob("frame_*.jpg"))
            if not frame_files:
                return None

            # Read first frame to get dimensions
            first_frame = cv2.imread(str(frame_files[0]))
            if first_frame is None:
                return None

            height, width = first_frame.shape[:2]

            # Create video writer - use session folder if output_path not specified
            if output_path is None:
                if self.session_folder:
                    output_path = self.session_folder / "preview.mp4"
                else:
                    return None
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(str(output_path), fourcc, self.fps, (width, height))

            # Write all frames
            for frame_file in frame_files:
                frame = cv2.imread(str(frame_file))
                if frame is not None:
                    out.write(frame)

            out.release()
            logger.info(f"Generated video: {output_path}")
            return output_path

        except ImportError:
            logger.warning("OpenCV not available for video generation")
            return None
        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            return None


# Singleton instance for reuse
_capture_service: WindowCaptureService | None = None


def get_window_capture_service() -> WindowCaptureService | None:
    """Get the active capture service instance."""
    return _capture_service


def create_window_capture_service(
    target_pid: int,
    session_folder: Path | None = None,
    frame_callback: Callable[[bytes, int, int], None] | None = None,
    **kwargs
) -> WindowCaptureService:
    """Create a new window capture service."""
    global _capture_service

    if _capture_service:
        _capture_service.stop()

    _capture_service = WindowCaptureService(
        target_pid=target_pid,
        session_folder=session_folder,
        frame_callback=frame_callback,
        **kwargs
    )

    return _capture_service
