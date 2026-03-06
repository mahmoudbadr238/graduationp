"""
Sandbox Preview Image Provider - Streams sandbox window frames to QML.

Implements QQuickImageProvider to efficiently deliver captured frames
from the sandbox window to the QML UI at video-like refresh rates.
"""

import logging
import threading

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider

logger = logging.getLogger(__name__)


class SandboxPreviewProvider(QQuickImageProvider):
    """
    QQuickImageProvider that serves sandbox window capture frames.

    Usage in QML:
        Image {
            source: "image://sandboxpreview/frame"
            cache: false
        }

    Call update_frame() from backend to push new frames.
    """

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._current_frame: QImage | None = None
        self._placeholder: QImage = self._create_placeholder()
        self._lock = threading.Lock()
        self._frame_counter = 0

    def _create_placeholder(self) -> QImage:
        """Create a placeholder image for when no frame is available."""
        # Create a dark placeholder with "Waiting for window..." text
        img = QImage(640, 480, QImage.Format.Format_RGB32)
        img.fill(0xFF1A1A2E)  # Dark blue-gray
        return img

    def requestImage(self, id: str, size, requestedSize) -> QImage:
        """
        Called by QML to request the current frame.

        Args:
            id: Image identifier (ignored, we only have one stream)
            size: Output size (will be set to actual frame size)
            requestedSize: Requested size from QML (may be ignored)

        Returns:
            Current frame or placeholder
        """
        with self._lock:
            if self._current_frame and not self._current_frame.isNull():
                return self._current_frame.copy()
            return self._placeholder.copy()

    def update_frame(self, data: bytes, width: int, height: int) -> None:
        """
        Update the current frame from BGRA pixel data.

        Args:
            data: Raw BGRA pixel data
            width: Frame width
            height: Frame height
        """
        try:
            # Create QImage from raw BGRA data
            img = QImage(data, width, height, width * 4, QImage.Format.Format_ARGB32)

            # Make a deep copy since the data buffer may be reused
            with self._lock:
                self._current_frame = img.copy()
                self._frame_counter += 1

        except Exception as e:
            logger.warning(f"Failed to update frame: {e}")

    def clear(self) -> None:
        """Clear the current frame."""
        with self._lock:
            self._current_frame = None
            self._frame_counter = 0

    @property
    def frame_count(self) -> int:
        """Get the number of frames received."""
        return self._frame_counter

    @property
    def has_frame(self) -> bool:
        """Check if we have a valid frame."""
        with self._lock:
            return self._current_frame is not None and not self._current_frame.isNull()


class SandboxPreviewController(QObject):
    """
    Controller for sandbox preview that can be exposed to QML.

    Manages the preview state and provides signals for UI updates.
    """

    # Signals
    frameUpdated = Signal()  # Emitted when a new frame is available
    previewStarted = Signal()
    previewStopped = Signal()
    statusChanged = Signal(str)  # Status message
    windowFound = Signal(str)  # Window title when found

    def __init__(self, provider: SandboxPreviewProvider, parent=None):
        super().__init__(parent)
        self._provider = provider
        self._is_active = False
        self._status = "Idle"
        self._window_title = ""
        self._frame_counter = 0

        # Refresh timer for QML
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_refresh_tick)
        self._refresh_interval = 100  # 100ms = 10 FPS max for UI updates

    def _on_refresh_tick(self):
        """Called periodically to signal frame updates to QML."""
        if self._provider.frame_count != self._frame_counter:
            self._frame_counter = self._provider.frame_count
            self.frameUpdated.emit()

    @Slot()
    def start(self):
        """Start the preview refresh."""
        self._is_active = True
        self._refresh_timer.start(self._refresh_interval)
        self._status = "Waiting for window..."
        self.statusChanged.emit(self._status)
        self.previewStarted.emit()

    @Slot()
    def stop(self):
        """Stop the preview refresh."""
        self._is_active = False
        self._refresh_timer.stop()
        self._provider.clear()
        self._status = "Stopped"
        self.statusChanged.emit(self._status)
        self.previewStopped.emit()

    def set_window_found(self, title: str):
        """Called when the sandbox window is found."""
        self._window_title = title
        self._status = (
            f"Capturing: {title[:40]}..." if len(title) > 40 else f"Capturing: {title}"
        )
        self.statusChanged.emit(self._status)
        self.windowFound.emit(title)

    def set_status(self, status: str):
        """Update the status message."""
        self._status = status
        self.statusChanged.emit(status)

    @Property(bool, notify=previewStarted)
    def isActive(self) -> bool:
        return self._is_active

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(str, notify=windowFound)
    def windowTitle(self) -> str:
        return self._window_title

    @Property(bool, notify=frameUpdated)
    def hasFrame(self) -> bool:
        return self._provider.has_frame

    @Property(int, notify=frameUpdated)
    def frameCount(self) -> int:
        return self._provider.frame_count


# Global instances
_preview_provider: SandboxPreviewProvider | None = None
_preview_controller: SandboxPreviewController | None = None


def get_preview_provider() -> SandboxPreviewProvider:
    """Get or create the preview image provider."""
    global _preview_provider
    if _preview_provider is None:
        _preview_provider = SandboxPreviewProvider()
    return _preview_provider


def get_preview_controller() -> SandboxPreviewController:
    """Get or create the preview controller."""
    global _preview_controller, _preview_provider
    if _preview_controller is None:
        _preview_controller = SandboxPreviewController(get_preview_provider())
    return _preview_controller


def register_preview_provider(engine, backend=None) -> SandboxPreviewController:
    """
    Register the preview provider with a QML engine.

    Call this during application initialization:
        controller = register_preview_provider(engine, backend)
        engine.rootContext().setContextProperty("SandboxPreview", controller)

    Then use in QML:
        Image { source: "image://sandboxpreview/frame?t=" + frameCounter }

    Args:
        engine: QQmlApplicationEngine instance
        backend: Optional BackendBridge to connect signals

    Returns:
        SandboxPreviewController for QML property binding
    """
    provider = get_preview_provider()
    controller = get_preview_controller()

    # Register image provider with engine
    engine.addImageProvider("sandboxpreview", provider)

    # Connect backend signals if provided
    if backend is not None:
        try:
            # Store provider and controller references in backend
            backend._preview_provider = provider
            backend._preview_controller = controller

            # Connect backend preview signals to controller
            if hasattr(backend, "sandboxPreviewStarted"):
                backend.sandboxPreviewStarted.connect(controller.start)
            if hasattr(backend, "sandboxPreviewStopped"):
                backend.sandboxPreviewStopped.connect(controller.stop)
            if hasattr(backend, "sandboxWindowFound"):
                backend.sandboxWindowFound.connect(
                    lambda found: (
                        controller.set_window_found("Sandbox Window")
                        if found
                        else controller.set_status("Waiting for window...")
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to connect backend signals: {e}")

    logger.info("Sandbox preview provider registered")
    return controller
