"""Native WM_DROPFILES event filter for drag-and-drop in elevated processes.

Qt Quick's DropArea uses OLE drag-and-drop, which is blocked by Windows UIPI
when the application runs elevated (as administrator). This module provides a
QAbstractNativeEventFilter that intercepts the legacy WM_DROPFILES message
instead, extracts file paths via DragQueryFileW, and emits them as a Qt signal.

Requires:
    - DragAcceptFiles(hwnd, True) called on the window beforehand
    - ChangeWindowMessageFilterEx allowing WM_DROPFILES on the window
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import struct
import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

WM_DROPFILES = 0x0233

shell32 = ctypes.windll.shell32

# UINT DragQueryFileW(HDROP hDrop, UINT iFile, LPWSTR lpszFile, UINT cch)
shell32.DragQueryFileW.argtypes = [
    wintypes.HANDLE,
    wintypes.UINT,
    ctypes.c_wchar_p,
    wintypes.UINT,
]
shell32.DragQueryFileW.restype = wintypes.UINT

# void DragFinish(HDROP hDrop)
shell32.DragFinish.argtypes = [wintypes.HANDLE]
shell32.DragFinish.restype = None


class DropEventFilter(QAbstractNativeEventFilter, QObject):
    """Intercept WM_DROPFILES and emit *fileDropped* with the first file path."""

    fileDropped = Signal(str)

    def __init__(self, hwnd: int, parent: QObject | None = None):
        QObject.__init__(self, parent)
        QAbstractNativeEventFilter.__init__(self)
        self._hwnd = hwnd

    # ------------------------------------------------------------------
    def nativeEventFilter(self, event_type: bytes | bytearray, message):  # type: ignore[override]
        """Process Windows native messages.

        Parameters
        ----------
        event_type : bytes
            b"windows_generic_MSG" on Windows.
        message : shiboken wrapper around MSG*
            Opaque pointer to a Windows MSG struct. We read it as raw bytes.

        Returns
        -------
        tuple[bool, int]
            (handled, result)
        """
        if event_type != b"windows_generic_MSG":
            return False, 0

        try:
            # `message` is a voidptr wrapping a native MSG*.
            # MSG struct on 64-bit:  HWND(8) UINT(4) pad(4) WPARAM(8) LPARAM(8) ...
            # We need to read the message id (UINT at offset 8) and wParam (at offset 16).
            msg_ptr = int(message)
            if sys.maxsize > 2**32:
                # 64-bit: HWND(8) + UINT(4) + pad(4) + WPARAM(8)
                data = (ctypes.c_char * 24).from_address(msg_ptr)
                raw = bytes(data)
                msg_hwnd = struct.unpack_from("<Q", raw, 0)[0]
                msg_id = struct.unpack_from("<I", raw, 8)[0]
                w_param = struct.unpack_from("<Q", raw, 16)[0]
            else:
                # 32-bit: HWND(4) + UINT(4) + WPARAM(4)
                data = (ctypes.c_char * 12).from_address(msg_ptr)
                raw = bytes(data)
                msg_hwnd = struct.unpack_from("<I", raw, 0)[0]
                msg_id = struct.unpack_from("<I", raw, 4)[0]
                w_param = struct.unpack_from("<I", raw, 8)[0]

            if msg_id != WM_DROPFILES:
                return False, 0

            hDrop = w_param

            # How many files were dropped?
            count = shell32.DragQueryFileW(hDrop, 0xFFFFFFFF, None, 0)
            if count < 1:
                shell32.DragFinish(hDrop)
                return True, 0

            # Read the first file path
            buf_size = 1024
            buf = ctypes.create_unicode_buffer(buf_size)
            shell32.DragQueryFileW(hDrop, 0, buf, buf_size)
            file_path = buf.value

            shell32.DragFinish(hDrop)

            if file_path:
                print(f"[DROP] Native WM_DROPFILES: {file_path}")
                self.fileDropped.emit(file_path)

            return True, 0

        except Exception as exc:
            print(f"[WARNING] DropEventFilter error: {exc}")
            return False, 0
