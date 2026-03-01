"""
Installer Autopilot - Safe automated interaction for installers.

Provides minimal, safe automation for stepping through installers:
- Only activates for known installer patterns (MSI, setup EXEs)
- Only clicks safe buttons: Next, Install, I Agree, Finish
- Runs entirely within sandbox
- Stops after installation completes or timeout

This is NOT a general-purpose automation tool.
"""

import ctypes
import logging
import re
import threading
import time
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from typing import List, Optional, Set

logger = logging.getLogger(__name__)

IS_WINDOWS = ctypes.windll is not None if hasattr(ctypes, "windll") else False

if IS_WINDOWS:
    user32 = ctypes.windll.user32

    # Button click message
    BM_CLICK = 0x00F5
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202

    # Window enumeration
    GW_CHILD = 5
    GW_HWNDNEXT = 2

    # Window class buffer size
    MAX_CLASS_NAME = 256


# Safe button patterns (case-insensitive)
SAFE_BUTTON_PATTERNS = [
    r"^next\s*[>»]?$",
    r"^>?\s*next$",
    r"^install$",
    r"^i\s+agree$",
    r"^accept$",
    r"^yes$",
    r"^ok$",
    r"^continue$",
    r"^finish$",
    r"^done$",
    r"^close$",
    r"^exit$",
]

# Installer detection patterns
INSTALLER_PATTERNS = [
    r"setup\.exe$",
    r"install.*\.exe$",
    r".*installer.*\.exe$",
    r".*_setup\.exe$",
    r"\.msi$",
]

# Window title patterns that indicate installer
INSTALLER_TITLE_PATTERNS = [
    r"setup",
    r"install",
    r"wizard",
    r"license agreement",
    r"end-user license",
    r"terms and conditions",
]


@dataclass
class AutopilotAction:
    """Record of an autopilot action."""
    timestamp: str
    action_type: str  # "click", "wait", "skip"
    target: str  # Button text or description
    window_title: str
    success: bool
    details: str = ""


class InstallerAutopilot:
    """
    Safe autopilot for stepping through installers.
    
    Only performs minimal, safe interactions:
    - Clicks Next/Install/Finish buttons
    - Waits between actions
    - Stops when installer closes
    """

    def __init__(
        self,
        target_pid: int,
        action_callback: Callable[[AutopilotAction], None] | None = None,
        max_actions: int = 20,
        action_delay: float = 2.0,
        timeout: float = 120.0,
    ):
        """
        Initialize the autopilot.
        
        Args:
            target_pid: PID of the installer process
            action_callback: Called for each action taken
            max_actions: Maximum number of button clicks
            action_delay: Seconds to wait between actions
            timeout: Overall timeout in seconds
        """
        self.target_pid = target_pid
        self.action_callback = action_callback
        self.max_actions = max_actions
        self.action_delay = action_delay
        self.timeout = timeout

        # State
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._actions: list[AutopilotAction] = []
        self._action_count = 0
        self._clicked_buttons: set[int] = set()  # HWNDs we've clicked

    @staticmethod
    def is_installer(file_path: str) -> bool:
        """Check if a file appears to be an installer."""
        file_lower = file_path.lower()

        for pattern in INSTALLER_PATTERNS:
            if re.search(pattern, file_lower):
                return True

        return False

    def start(self) -> None:
        """Start the autopilot in background thread."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._autopilot_loop, daemon=True)
        self._thread.start()
        logger.info(f"Installer autopilot started for PID {self.target_pid}")

    def stop(self) -> list[AutopilotAction]:
        """Stop the autopilot and return action history."""
        self._running = False
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        logger.info(f"Installer autopilot stopped. Performed {self._action_count} actions.")
        return self._actions.copy()

    def _autopilot_loop(self) -> None:
        """Main autopilot loop."""
        start_time = time.time()

        while self._running and not self._stop_event.is_set():
            try:
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed >= self.timeout:
                    logger.info("Autopilot timeout reached")
                    break

                # Check action limit
                if self._action_count >= self.max_actions:
                    logger.info("Autopilot action limit reached")
                    break

                # Find installer window
                hwnd = self._find_installer_window()
                if not hwnd:
                    # No window, maybe installer finished
                    time.sleep(1.0)
                    continue

                # Find and click safe buttons
                clicked = self._try_click_safe_button(hwnd)

                if clicked:
                    # Wait before next action
                    self._stop_event.wait(self.action_delay)
                else:
                    # No button found, short wait
                    self._stop_event.wait(0.5)

            except Exception as e:
                logger.warning(f"Autopilot error: {e}")
                time.sleep(0.5)

    def _find_installer_window(self) -> int | None:
        """Find the main installer window for the target PID."""
        if not IS_WINDOWS:
            return None

        found_hwnd = None

        def enum_callback(hwnd, lparam):
            nonlocal found_hwnd

            try:
                # Check if window belongs to our process
                window_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))

                if window_pid.value != self.target_pid:
                    return True

                # Check if visible
                if not user32.IsWindowVisible(hwnd):
                    return True

                # Get window title
                title = self._get_window_text(hwnd)
                if not title:
                    return True

                # Check if it looks like an installer window
                title_lower = title.lower()
                for pattern in INSTALLER_TITLE_PATTERNS:
                    if re.search(pattern, title_lower):
                        found_hwnd = hwnd
                        return False  # Stop enumeration

                # If no installer pattern matched but it's a visible window, use it
                if not found_hwnd:
                    found_hwnd = hwnd

            except Exception:
                pass

            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

        return found_hwnd

    def _try_click_safe_button(self, hwnd: int) -> bool:
        """Try to find and click a safe button in the window."""
        if not IS_WINDOWS:
            return False

        # Find all buttons in the window
        buttons = self._find_buttons(hwnd)

        for btn_hwnd, btn_text in buttons:
            # Skip if we've already clicked this button
            if btn_hwnd in self._clicked_buttons:
                continue

            # Check if it's a safe button
            if self._is_safe_button(btn_text):
                # Click it
                success = self._click_button(btn_hwnd)

                if success:
                    self._clicked_buttons.add(btn_hwnd)
                    self._action_count += 1

                    # Record action
                    from datetime import datetime
                    action = AutopilotAction(
                        timestamp=datetime.now().isoformat(),
                        action_type="click",
                        target=btn_text,
                        window_title=self._get_window_text(hwnd),
                        success=True,
                        details=f"Clicked button: {btn_text}"
                    )
                    self._actions.append(action)

                    if self.action_callback:
                        try:
                            self.action_callback(action)
                        except Exception as e:
                            logger.warning(f"Action callback error: {e}")

                    logger.info(f"Autopilot clicked: {btn_text}")
                    return True

        return False

    def _find_buttons(self, hwnd: int) -> list[tuple]:
        """Find all buttons in a window and its children."""
        buttons = []

        def enum_child_callback(child_hwnd, lparam):
            try:
                # Get window class
                class_name = ctypes.create_unicode_buffer(MAX_CLASS_NAME)
                user32.GetClassNameW(child_hwnd, class_name, MAX_CLASS_NAME)

                # Check if it's a button
                if class_name.value.lower() == "button":
                    text = self._get_window_text(child_hwnd)
                    if text:
                        buttons.append((child_hwnd, text))

            except Exception:
                pass

            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumChildWindows(hwnd, WNDENUMPROC(enum_child_callback), 0)

        return buttons

    def _is_safe_button(self, text: str) -> bool:
        """Check if a button text matches safe patterns."""
        if not text:
            return False

        # Remove accelerator keys (&) and extra whitespace
        clean_text = text.replace("&", "").strip().lower()

        for pattern in SAFE_BUTTON_PATTERNS:
            if re.match(pattern, clean_text, re.IGNORECASE):
                return True

        return False

    def _click_button(self, btn_hwnd: int) -> bool:
        """Click a button by sending BM_CLICK message."""
        if not IS_WINDOWS:
            return False

        try:
            # Send button click message
            user32.SendMessageW(btn_hwnd, BM_CLICK, 0, 0)
            return True
        except Exception as e:
            logger.warning(f"Failed to click button: {e}")
            return False

    def _get_window_text(self, hwnd: int) -> str:
        """Get the text of a window or control."""
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


# Convenience function
def create_autopilot_if_installer(
    file_path: str,
    pid: int,
    enabled: bool = True,
    action_callback: Callable[[AutopilotAction], None] | None = None,
) -> InstallerAutopilot | None:
    """
    Create an autopilot if the file is an installer and autopilot is enabled.
    
    Args:
        file_path: Path to the file being executed
        pid: PID of the process
        enabled: Whether autopilot is enabled
        action_callback: Callback for actions
    
    Returns:
        InstallerAutopilot instance or None
    """
    if not enabled:
        return None

    if not InstallerAutopilot.is_installer(file_path):
        logger.info(f"File does not appear to be an installer: {file_path}")
        return None

    logger.info(f"Creating autopilot for installer: {file_path}")
    return InstallerAutopilot(
        target_pid=pid,
        action_callback=action_callback,
    )
