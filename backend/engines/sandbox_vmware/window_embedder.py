"""Win32 VMware KVM window embedder for QML via QWindow.fromWinId().

Embeds the lightweight ``vmware-kvm.exe`` console window (pure borderless
render surface) instead of the full ``vmware.exe`` GUI.  KVM windows are
far easier to reparent because they have no complex XAML/WPF chrome, no
DWM redirection issues, and no multi-layer child windows.

Workflow:

    1.  Orchestrator launches ``vmware-kvm.exe <vmx>`` via Popen.
    2.  ``find_kvm_hwnd()`` polls for the KVM window class.
    3.  ``strip_window_chrome()`` removes any residual borders.
    4.  ``QWindow.fromWinId(hwnd)`` + QML ``WindowContainer`` embeds it.
    5.  On teardown, ``release()`` restores chrome, then orchestrator
        terminates the process and runs ``vmrun stop``.
"""

from __future__ import annotations

import logging
import sys
import time

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QWindow

logger = logging.getLogger(__name__)

# ── Win32 imports ────────────────────────────────────────────────────────────

_HAS_WIN32 = False

if sys.platform == "win32":
    try:
        import win32con  # noqa: F401
        import win32gui  # noqa: F401

        _HAS_WIN32 = True
    except ImportError:
        logger.warning(
            "pywin32 not installed — VMware window embedding will be unavailable"
        )

    import ctypes
    import ctypes.wintypes

    _user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    _user32.IsWindow.argtypes = [ctypes.wintypes.HWND]
    _user32.IsWindow.restype = ctypes.wintypes.BOOL

# ── KVM window-class name used by vmware-kvm.exe ────────────────────────────
_KVM_WINDOW_CLASS = "VMwareKvmWindowClass"


# ═════════════════════════════════════════════════════════════════════════════
# Public helpers (safe to call from worker thread — pure win32gui, no Qt GUI)
# ═════════════════════════════════════════════════════════════════════════════

def find_kvm_hwnd(
    timeout: int = 20,
    poll_interval: int = 1,
    vm_name: str | None = None,
) -> int:
    """Poll for a visible ``vmware-kvm.exe`` window and return its HWND.

    Detection strategy (first match wins):
      1. Window class equals ``VMwareKvmWindowClass``.
      2. Title ends with ``"- VMware Workstation"`` or contains
         ``"VMware Workstation"`` (fallback for version variance).
      3. If *vm_name* is supplied, title contains that substring.

    Only **visible** windows are considered, so phantom pre-load HWNDs
    created before the render surface is ready are skipped.

    Returns ``0`` if nothing is found within *timeout* seconds.
    """
    if sys.platform != "win32" or not _HAS_WIN32:
        return 0

    deadline = time.monotonic() + timeout
    attempt = 0

    while time.monotonic() < deadline:
        attempt += 1
        found_hwnd: int = 0

        def _enum_cb(hwnd: int, _lp: int) -> bool:
            nonlocal found_hwnd
            if not win32gui.IsWindowVisible(hwnd):
                return True
            try:
                cls_name = win32gui.GetClassName(hwnd)
                title = win32gui.GetWindowText(hwnd)
            except Exception:
                return True

            # Strategy 1: exact class match (fastest, most reliable)
            if cls_name == _KVM_WINDOW_CLASS:
                found_hwnd = hwnd
                logger.debug("KVM match by class %r HWND=%#x title=%r", cls_name, hwnd, title)
                return False

            if not title:
                return True

            # Strategy 2: title-based match (VMware Workstation pattern)
            if title.endswith("- VMware Workstation") or "VMware Workstation" in title:
                found_hwnd = hwnd
                logger.debug("KVM match by title HWND=%#x title=%r", hwnd, title)
                return False

            # Strategy 3: VM name substring match
            if vm_name and vm_name in title:
                found_hwnd = hwnd
                logger.debug("KVM match by vm_name HWND=%#x title=%r", hwnd, title)
                return False

            return True

        try:
            win32gui.EnumWindows(_enum_cb, 0)
        except Exception:
            pass  # EnumWindows raises when callback returns False

        if found_hwnd:
            logger.info(
                "find_kvm_hwnd: found HWND=%#x on attempt %d/%ds",
                found_hwnd, attempt, timeout,
            )
            return found_hwnd

        logger.debug("KVM finder attempt %d — no window yet, retrying", attempt)
        time.sleep(poll_interval)

    logger.warning("find_kvm_hwnd: no KVM window found after %ds", timeout)
    return 0


# Keep the old name as an alias so any external callers continue to work.
find_vmware_hwnd = find_kvm_hwnd


def strip_window_chrome(hwnd: int) -> tuple[int, int]:
    """Remove caption / border / system menu from *hwnd*.

    Makes the VMware window look like a flat, borderless video feed
    suitable for embedding inside the QML WindowContainer.

    Returns ``(original_style, original_ex_style)`` so they can be
    restored later with :func:`restore_window_chrome`.
    """
    original_style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    original_ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)

    new_style = (
        original_style
        & ~win32con.WS_CAPTION
        & ~win32con.WS_THICKFRAME
        & ~win32con.WS_SYSMENU
        & ~win32con.WS_MINIMIZEBOX
        & ~win32con.WS_MAXIMIZEBOX
    )
    win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, new_style)

    new_ex = original_ex & ~win32con.WS_EX_APPWINDOW & ~win32con.WS_EX_WINDOWEDGE
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_ex)

    # Force the window to redraw with new frame metrics
    win32gui.SetWindowPos(
        hwnd, 0, 0, 0, 0, 0,
        win32con.SWP_FRAMECHANGED | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
        | win32con.SWP_NOMOVE | win32con.SWP_NOSIZE,
    )
    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

    return original_style, original_ex


def restore_window_chrome(hwnd: int, style: int, ex_style: int) -> None:
    """Restore the original styles saved by :func:`strip_window_chrome`."""
    win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
    win32gui.SetWindowPos(
        hwnd, 0, 0, 0, 0, 0,
        win32con.SWP_FRAMECHANGED | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
        | win32con.SWP_NOMOVE | win32con.SWP_NOSIZE,
    )
    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)


# ═════════════════════════════════════════════════════════════════════════════
# QObject controller — manages the QWindow lifecycle for QML binding
# ═════════════════════════════════════════════════════════════════════════════

class VmwareWindowEmbedder(QObject):
    """Creates a ``QWindow`` from a VMware HWND and exposes it to QML.

    QML uses ``WindowContainer { window: VmwareEmbedder.vmWindow }``
    to embed it into the scenegraph.

    Lifecycle
    ---------
    1. Orchestrator launches ``vmware-kvm.exe`` and finds the HWND.
    2. Signal auto-queues to main thread → :pymethod:`embed` called.
    3. ``embed()`` strips any residual chrome, creates
       ``QWindow.fromWinId()``, emits :attr:`vmWindowChanged`.
    4. ``release()`` destroys the ``QWindow`` and restores chrome.
    """

    # Signals
    vmWindowChanged = Signal()
    embeddedChanged = Signal(bool)
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._vm_window: QWindow | None = None
        self._vmware_hwnd: int = 0
        self._orig_style: int = 0
        self._orig_ex_style: int = 0
        self._embedded: bool = False

    # ── Properties (QML-bindable) ─────────────────────────────────────────

    @Property(QObject, notify=vmWindowChanged)
    def vmWindow(self) -> QObject | None:  # noqa: N802
        """The QWindow wrapping the VMware HWND (or None).

        Typed as QObject for Property registration; QML WindowContainer
        will use it as a QWindow via duck-typing.
        """
        return self._vm_window

    @Property(bool, notify=embeddedChanged)
    def embedded(self) -> bool:  # noqa: D401
        return self._embedded

    # ── Public slots (MUST be called on the main / GUI thread) ────────────

    @Slot(int)
    def embed(self, vmware_hwnd: int) -> None:
        """Strip chrome, wrap HWND in QWindow, expose to QML."""
        if self._embedded:
            self.release()

        if sys.platform != "win32" or not _user32.IsWindow(vmware_hwnd):
            msg = f"HWND {vmware_hwnd:#x} is not a valid window"
            logger.warning(msg)
            self.errorOccurred.emit(msg)
            return

        self._vmware_hwnd = vmware_hwnd

        # Strip window decorations
        self._orig_style, self._orig_ex_style = strip_window_chrome(vmware_hwnd)

        # Create the QWindow wrapper — this is the critical step
        self._vm_window = QWindow.fromWinId(vmware_hwnd)
        logger.info("Created QWindow from VMware HWND %#x", vmware_hwnd)

        self._embedded = True
        self.vmWindowChanged.emit()
        self.embeddedChanged.emit(True)

    @Slot()
    def release(self) -> None:
        """Destroy the QWindow and restore the VMware window chrome."""
        if not self._embedded:
            return

        hwnd = self._vmware_hwnd

        # Drop the QWindow reference (Qt will un-adopt the HWND)
        if self._vm_window is not None:
            self._vm_window.destroy()
            self._vm_window = None

        # Restore original decorations
        if hwnd and sys.platform == "win32" and _user32.IsWindow(hwnd):
            restore_window_chrome(hwnd, self._orig_style, self._orig_ex_style)

        self._vmware_hwnd = 0
        self._orig_style = 0
        self._orig_ex_style = 0
        self._embedded = False
        self.vmWindowChanged.emit()
        self.embeddedChanged.emit(False)
        logger.info("VMware window released")
