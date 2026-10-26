"""
Picture-in-Picture (PiP) Floating Player Window.
Real, polished borderless floating player with hover controls, smooth drag-to-move,
aspect-ratio resizing, and Always-On-Top capability.
"""

import sys
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32 if sys.platform.startswith("win") else None
if sys.platform.startswith("win") and user32:
    try:
        user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetClientRect.restype = wintypes.BOOL

        user32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
        user32.MoveWindow.restype = wintypes.BOOL

        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumChildWindows.argtypes = [wintypes.HWND, WNDENUMPROC, wintypes.LPARAM]
        user32.EnumChildWindows.restype = wintypes.BOOL
    except Exception:
        pass

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton,
    QToolButton, QFrame, QSizeGrip
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QMouseEvent


class PiPVideoCanvas(QFrame):
    """
    Dedicated video rendering surface for PiP mode.
    Equipped with native Win32 window attributes and child window synchronization
    to ensure LibVLC Direct3D video outputs render with 100% hardware fill without black screens.
    """
    def __init__(self, pip_win, parent=None):
        super().__init__(parent)
        self.pip_win = pip_win
        self.setStyleSheet("background-color: #000000;")
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        self.setMouseTracking(True)

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter
        painter = QPainter(self)
        painter.fillRect(event.rect(), Qt.GlobalColor.black)

    def sync_child_size(self):
        """Ensures the VLC video child window respects aspect ratio without distortion."""
        if sys.platform.startswith("win") and user32:
            try:
                hwnd = int(self.winId())
                rect = wintypes.RECT()
                if user32.GetClientRect(hwnd, ctypes.byref(rect)):
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top
                else:
                    dpr = self.devicePixelRatioF()
                    w = int(round(self.width() * dpr))
                    h = int(round(self.height() * dpr))

                if w > 0 and h > 0:
                    aspect_ratio = 0.0
                    try:
                        aspect_ratio = self.pip_win.main_win.engine.get_video_aspect_ratio()
                    except Exception:
                        pass

                    if aspect_ratio > 0:
                        container_ar = w / float(h)
                        if container_ar > aspect_ratio:
                            target_h = h
                            target_w = int(round(h * aspect_ratio))
                            target_x = (w - target_w) // 2
                            target_y = 0
                        else:
                            target_w = w
                            target_h = int(round(w / aspect_ratio))
                            target_x = 0
                            target_y = (h - target_h) // 2
                    else:
                        target_x, target_y, target_w, target_h = 0, 0, w, h

                    def enum_proc(child_hwnd, lparam):
                        parent_of_child = user32.GetParent(child_hwnd)
                        if parent_of_child == hwnd:
                            user32.MoveWindow(child_hwnd, target_x, target_y, target_w, target_h, True)
                        else:
                            user32.MoveWindow(child_hwnd, 0, 0, target_w, target_h, True)
                        return True
                    proc = WNDENUMPROC(enum_proc)
                    user32.EnumChildWindows(hwnd, proc, 0)
                    self.update()
            except Exception:
                pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sync_child_size()
        QTimer.singleShot(50, self.sync_child_size)
        QTimer.singleShot(150, self.sync_child_size)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pip_win.drag_position = event.globalPosition().toPoint() - self.pip_win.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and self.pip_win.drag_position:
            self.pip_win.move(event.globalPosition().toPoint() - self.pip_win.drag_position)
            event.accept()
        else:
            self.pip_win.show_controls()
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.pip_win.drag_position = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pip_win.restore_requested.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)


class PiPWindow(QWidget):
    """
    True Picture-in-Picture Floating Window.
    Always on top, borderless, draggable, with auto-hiding overlay controls.
    Detached from parent so it remains floating even when the main player window is minimized.
    """
    restore_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, main_win, parent=None):
        # Detached top-level window so minimizing main window will not hide PiP
        super().__init__(None)
        self.main_win = main_win
        self.drag_position = None

        # Floating window properties
        self.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.resize(440, 248)
        self.setMinimumSize(280, 160)

        self._setup_ui()
        self._setup_hide_timer()

    def _setup_ui(self):
        # Video canvas fills entire window
        self.canvas = PiPVideoCanvas(self, self)
        self.canvas.setGeometry(0, 0, self.width(), self.height())

        # Floating Controls Overlay Container (child of PiPWindow floating above canvas)
        self.overlay = QFrame(self)
        self.overlay.setStyleSheet("""
            QFrame {
                background-color: rgba(12, 15, 20, 220);
                border-top: 1px solid rgba(255, 255, 255, 0.18);
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
                padding: 4px;
            }
            QToolButton, QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.18);
                color: #ffffff;
                border-radius: 4px;
                padding: 3px 7px;
                font-size: 11px;
                font-weight: 600;
            }
            QToolButton:hover, QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.22);
                border-color: rgba(255, 255, 255, 0.35);
            }
            QLabel {
                color: #f4f4f5;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                font-weight: 600;
            }
        """)

        ov_layout = QHBoxLayout(self.overlay)
        ov_layout.setContentsMargins(6, 2, 6, 2)
        ov_layout.setSpacing(6)

        # Seek backward 5s
        self.back_btn = QToolButton()
        self.back_btn.setText("⏪")
        self.back_btn.setToolTip("Mundur 5 Detik")
        self.back_btn.clicked.connect(lambda: self.main_win.seek_relative(-5000))
        ov_layout.addWidget(self.back_btn)

        # Play/Pause
        self.play_btn = QToolButton()
        self.play_btn.setText("▶")
        self.play_btn.setToolTip("Putar / Jeda")
        self.play_btn.clicked.connect(self.main_win.toggle_play_pause)
        ov_layout.addWidget(self.play_btn)

        # Seek forward 5s
        self.fwd_btn = QToolButton()
        self.fwd_btn.setText("⏩")
        self.fwd_btn.setToolTip("Maju 5 Detik")
        self.fwd_btn.clicked.connect(lambda: self.main_win.seek_relative(5000))
        ov_layout.addWidget(self.fwd_btn)

        # Time label
        self.pip_time_label = QLabel("00:00")
        ov_layout.addWidget(self.pip_time_label)

        ov_layout.addStretch()

        # Volume Mute
        self.mute_btn = QToolButton()
        self.mute_btn.setText("🔊")
        self.mute_btn.setToolTip("Bisu / Bunyikan (M)")
        self.mute_btn.clicked.connect(self.main_win.toggle_mute)
        ov_layout.addWidget(self.mute_btn)

        # Restore button (Return to full window)
        self.restore_btn = QToolButton()
        self.restore_btn.setText("🗖")
        self.restore_btn.setToolTip("Kembali ke Pemutar Utama")
        self.restore_btn.clicked.connect(self.restore_requested.emit)
        ov_layout.addWidget(self.restore_btn)

        # Close PiP button
        self.close_btn = QToolButton()
        self.close_btn.setText("✕")
        self.close_btn.setToolTip("Tutup PiP (Esc)")
        self.close_btn.clicked.connect(self.close_requested.emit)
        ov_layout.addWidget(self.close_btn)

        # Discreet size grip at bottom-right corner
        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("background: transparent;")
        self.size_grip.resize(16, 16)

    def _setup_hide_timer(self):
        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(2500)
        self.hide_timer.timeout.connect(self._hide_controls)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.canvas.setGeometry(0, 0, self.width(), self.height())
        ov_height = 36
        self.overlay.setGeometry(0, self.height() - ov_height, self.width(), ov_height)
        self.overlay.raise_()
        self.size_grip.move(self.width() - self.size_grip.width(), self.height() - self.size_grip.height())
        self.size_grip.raise_()
        self.canvas.sync_child_size()

    def show_controls(self):
        self.overlay.show()
        self.overlay.raise_()
        self.size_grip.raise_()
        self.hide_timer.start()

    def _hide_controls(self):
        if not self.overlay.underMouse() and not self.underMouse():
            self.overlay.hide()

    def enterEvent(self, event):
        self.show_controls()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hide_timer.start(1200)
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
        else:
            self.show_controls()
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.drag_position = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.restore_requested.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def update_status(self, is_playing: bool, time_str: str, is_muted: bool):
        self.play_btn.setText("⏸" if is_playing else "▶")
        self.pip_time_label.setText(time_str)
        self.mute_btn.setText("🔇" if is_muted else "🔊")
