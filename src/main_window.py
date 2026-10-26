"""
Supercharged Main Application Window for Hybrid Media Player.
Integrates:
- Mouse Gestures (Left: Brightness, Right: Volume 250%, Center: Seek)
- Video Rotation (90°, 180°, 270°) & Mirror Flip (R key)
- Bookmarks & Chapter markers (B / Shift+B)
- Jump to Time / Start From Timestamp (Ctrl+G)
- Shortcuts & Gestures Visual Cheat Sheet HUD (F1)
- True Picture-in-Picture (PiP) borderless floating player
- Auto-Load same-name subtitles & Seekbar timestamp tooltip
- Volume boost up to 250%, Crystal Clear Audio, and Spatializer
"""

import os
import sys
import json
import ctypes
from ctypes import wintypes
from typing import Optional

user32 = ctypes.windll.user32 if sys.platform.startswith("win") else None
if sys.platform.startswith("win") and user32:
    try:
        user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetClientRect.restype = wintypes.BOOL

        user32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
        user32.MoveWindow.restype = wintypes.BOOL

        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.SetWindowPos.restype = wintypes.BOOL

        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = wintypes.LONG

        user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
        user32.SetWindowLongW.restype = wintypes.LONG

        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumChildWindows.argtypes = [wintypes.HWND, WNDENUMPROC, wintypes.LPARAM]
        user32.EnumChildWindows.restype = wintypes.BOOL
    except Exception:
        pass

# 64-bit safe Win32 constants for SetWindowPos
HWND_TOPMOST = ctypes.c_void_p(-1).value
HWND_NOTOPMOST = ctypes.c_void_p(-2).value

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QPushButton, QToolButton, QFrame, QFileDialog,
    QMenu, QSplitter, QApplication, QSizePolicy,
    QGraphicsOpacityEffect, QToolTip
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF, QRectF, QEvent, QPropertyAnimation, QEasingCurve, QDateTime, pyqtProperty
from PyQt6.QtGui import (
    QActionGroup, QKeySequence, QMouseEvent, QWheelEvent,
    QDragEnterEvent, QDropEvent, QKeyEvent,
    QPainter, QPen, QBrush, QColor, QPolygonF, QLinearGradient
)

from .engine import PlayerEngine, parse_timestamp_to_ms
from .osd import OSDOverlay, LiveStatsHUD
from .resume_banner import ResumePromptBanner
from .next_episode_banner import NextEpisodeBanner
from .playlist import PlaylistWidget, SUPPORTED_MEDIA_EXTENSIONS
from .pip_window import PiPWindow
from .dialogs import (
    AudioEffectsDialog, VideoAdjustDialog, MediaInfoDialog,
    OpenStreamDialog, SubtitleStyleDialog,
    JumpToTimeDialog, BookmarkManagerDialog, ShortcutsCheatSheetDialog,
    ContinueWatchingDialog, OnlineSubtitlesDialog
)
from .styles import get_theme_stylesheet


class CenterPlayButton(QWidget):
    """
    Minimalist borderless Play / Pause HUD indicator positioned precisely at the center
    of the video viewport.
    - Owned Tool window (NOT ToolTip) so it respects Windows Z-order and never bleeds over other apps.
    - Direct QPainter alpha animation without QGraphicsOpacityEffect to eliminate layered-window ghosting.
    - Transparent for mouse events so clicks pass cleanly to VideoWidget without stealing window focus.
    """
    def __init__(self, main_win):
        super().__init__(main_win, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.main_win = main_win
        self.setObjectName("CenterPlayIndicator")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFixedSize(100, 100)

        self._opacity = 0.0

        # Fade animation driving self.hud_opacity directly
        self.anim = QPropertyAnimation(self, b"hud_opacity")
        self.anim.setDuration(150)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim.finished.connect(self._on_anim_finished)

        # Auto-hide timer
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.setInterval(1200)
        self.hide_timer.timeout.connect(self.fade_out)

        self.is_hovered = False
        self.state = "play"  # "play" or "pause"
        self.hide()

    @pyqtProperty(float)
    def hud_opacity(self) -> float:
        return self._opacity

    @hud_opacity.setter
    def hud_opacity(self, val: float):
        self._opacity = max(0.0, min(1.0, float(val)))
        self.update()

    def position_on_player(self):
        if not self.main_win.isVisible() or self.main_win.isMinimized() or self.main_win.pip_mode:
            self.hide_immediate()
            return
        if not self.main_win.isActiveWindow() and not getattr(self.main_win, "always_on_top", False):
            self.hide_immediate()
            return
        if not self.main_win.engine.is_media_loaded():
            self.hide_immediate()
            return
        vw = self.main_win.video_widget
        v_global = vw.mapToGlobal(QPoint(0, 0))
        cx = v_global.x() + (vw.width() - self.width()) // 2
        cy = v_global.y() + (vw.height() - self.height()) // 2
        self.move(cx, cy)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Clear background completely to prevent ghosting on transparent windows
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        if self._opacity <= 0.01:
            return

        center_x = self.width() / 2.0   # Exactly 50.0
        center_y = self.height() / 2.0  # Exactly 50.0

        fg_alpha = int(round((255 if self.is_hovered else 235) * self._opacity))
        sh_alpha = int(round(140 * self._opacity))
        fg_color = QColor(255, 255, 255, fg_alpha)
        shadow_color = QColor(0, 0, 0, sh_alpha)

        if self.state == "pause":
            # --- PAUSE ICON: ❚❚ (Two symmetrical rounded vertical bars) ---
            bar_w = 11.0
            bar_h = 42.0
            total_w = 36.0
            x1 = center_x - total_w / 2.0        # 32.0
            x2 = center_x + total_w / 2.0 - bar_w # 57.0
            y = center_y - bar_h / 2.0           # 29.0

            # 1. Subtle drop-shadow (offset dx=+1.5, dy=+2.0)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(shadow_color))
            painter.drawRoundedRect(QRectF(x1 + 1.5, y + 2.0, bar_w, bar_h), 3.0, 3.0)
            painter.drawRoundedRect(QRectF(x2 + 1.5, y + 2.0, bar_w, bar_h), 3.0, 3.0)

            # 2. Foreground bars
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(fg_color))
            painter.drawRoundedRect(QRectF(x1, y, bar_w, bar_h), 3.0, 3.0)
            painter.drawRoundedRect(QRectF(x2, y, bar_w, bar_h), 3.0, 3.0)

        else:
            # --- PLAY ICON: ▶ (Balanced isosceles triangle) ---
            tri_w = 38.0
            tri_h = 44.0
            x_left = center_x - tri_w / 2.0   # 31.0
            x_right = center_x + tri_w / 2.0  # 69.0
            y_top = center_y - tri_h / 2.0    # 28.0
            y_bottom = center_y + tri_h / 2.0 # 72.0

            # 1. Drop-shadow triangle (offset dx=+1.5, dy=+2.0)
            shadow_poly = QPolygonF([
                QPointF(x_left + 1.5, y_top + 2.0),
                QPointF(x_right + 1.5, center_y + 2.0),
                QPointF(x_left + 1.5, y_bottom + 2.0)
            ])
            painter.setPen(QPen(shadow_color, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(QBrush(shadow_color))
            painter.drawPolygon(shadow_poly)

            # 2. Foreground triangle
            tri_poly = QPolygonF([
                QPointF(x_left, y_top),
                QPointF(x_right, center_y),
                QPointF(x_left, y_bottom)
            ])
            painter.setPen(QPen(fg_color, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(QBrush(fg_color))
            painter.drawPolygon(tri_poly)

    def flash(self, state: str = "play", duration_ms: int = 1100):
        """Displays indicator briefly then smoothly fades out."""
        if not self.main_win.isVisible() or self.main_win.isMinimized() or self.main_win.pip_mode:
            self.hide_immediate()
            return
        if not self.main_win.isActiveWindow() and not getattr(self.main_win, "always_on_top", False):
            self.hide_immediate()
            return
        if not self.main_win.engine.is_media_loaded():
            self.hide_immediate()
            return

        self.state = state
        self.position_on_player()

        # Stop existing fade animations and timer
        self.anim.stop()
        self.hide_timer.stop()

        self._opacity = 1.0
        self.update()
        if not self.isVisible():
            self.show()

        # Auto-hide after duration
        self.hide_timer.start(min(duration_ms, 1200))

    def fade_in(self, state: Optional[str] = None):
        """Compatibility wrapper for flash()."""
        if state is None:
            state = "play" if self.main_win.engine.is_playing() else "pause"
        self.flash(state, 1100)

    def fade_out(self):
        """Smoothly fades out and hides widget."""
        self.hide_timer.stop()
        if self._opacity > 0.05 and self.isVisible():
            self.anim.stop()
            self.anim.setDuration(220)
            self.anim.setStartValue(self._opacity)
            self.anim.setEndValue(0.0)
            self.anim.start()
        else:
            self.hide_immediate()

    def hide_immediate(self):
        self.hide_timer.stop()
        self.anim.stop()
        self._opacity = 0.0
        self.update()
        self.hide()

    def _on_anim_finished(self):
        if self._opacity <= 0.05:
            self.hide_immediate()


class ClickSeekSlider(QSlider):
    """Horizontal seekbar with instant jump-to-click precision, smooth scrubbing, hover tooltip, and mouse wheel."""
    def __init__(self, orientation=Qt.Orientation.Horizontal, main_win=None, parent=None):
        super().__init__(orientation, parent)
        self.main_win = main_win
        self._is_dragging = False
        self.setMouseTracking(True)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            w = self.width()
            if w > 0:
                ratio = max(0.0, min(1.0, event.position().x() / float(w)))
                val = int(round(self.minimum() + ratio * (self.maximum() - self.minimum())))
                self.setValue(val)
                self.sliderPressed.emit()
                self.sliderMoved.emit(val)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        w = self.width()
        if self._is_dragging:
            if w > 0:
                ratio = max(0.0, min(1.0, event.position().x() / float(w)))
                val = int(round(self.minimum() + ratio * (self.maximum() - self.minimum())))
                self.setValue(val)
                self.sliderMoved.emit(val)
            event.accept()
        else:
            super().mouseMoveEvent(event)

        # Floating Hover Tooltip: Time preview under cursor
        if w > 0 and self.main_win and hasattr(self.main_win, "engine"):
            tot_ms = self.main_win.engine.get_length()
            if tot_ms > 0:
                ratio = max(0.0, min(1.0, event.position().x() / float(w)))
                hover_ms = int(ratio * tot_ms)
                time_str = self.main_win._format_time(hover_ms)
                tot_str = self.main_win._format_time(tot_ms)
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    f" {time_str} / {tot_str} ",
                    self
                )

    def leaveEvent(self, event):
        QToolTip.hideText()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            self._is_dragging = False
            w = self.width()
            if w > 0:
                ratio = max(0.0, min(1.0, event.position().x() / float(w)))
                val = int(round(self.minimum() + ratio * (self.maximum() - self.minimum())))
                self.setValue(val)
            self.sliderReleased.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.main_win:
            self.main_win.toggle_play_pause()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta != 0 and self.main_win:
            self.main_win.seek_relative(5000 if delta > 0 else -5000)
            event.accept()
            return
        super().wheelEvent(event)


class ModernFloatingDock(QWidget):
    """
    Floating Glassmorphic Control Dock.
    Capsule/pill shaped card container hovering above the bottom of the video.
    Top row: full-width white-thumb timeline seekbar.
    Bottom row:
      - [▶ / ⏸] [🔊] [=== vol slider ===] [0:00 / 0:14]
      - [Flexible Spacer]
      - [1x ˅] [⧉ PiP] [⛶ Fullscreen] [☰ Fitur]
    Auto-hides with smooth fade-out when idle during playback;
    smoothly fades in on mouse activity.
    """
    def __init__(self, main_win):
        super().__init__(main_win, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.main_win = main_win
        self.setObjectName("ModernFloatingDock")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)

        self.is_dragging = False

        # Opacity animation
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim.finished.connect(self._on_anim_finished)

        # Idle auto-hide timer (2.4s)
        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.timeout.connect(self._on_idle_timeout)

        self._build_ui()
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()

        # Clean background slate to prevent alpha artifacts
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(rect, Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0.0, QColor(12, 12, 15, 0))
        gradient.setColorAt(0.22, QColor(16, 16, 20, 210))
        gradient.setColorAt(1.0, QColor(12, 12, 16, 242))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawRect(rect)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 4, 14, 8)
        layout.setSpacing(4)

        # 1. Full-width Seekbar (Timeline)
        self.seek_slider = ClickSeekSlider(Qt.Orientation.Horizontal, main_win=self.main_win, parent=self)
        self.seek_slider.setObjectName("DockSeekSlider")
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self.seek_slider.sliderMoved.connect(self._on_seek_moved)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        layout.addWidget(self.seek_slider)

        # 2. Controls Row
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)
        btn_box.setContentsMargins(0, 2, 0, 0)

        # Previous Track Button
        self.prev_btn = QPushButton("⏮")
        self.prev_btn.setObjectName("DockTileBtn")
        self.prev_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.prev_btn.setToolTip("Sebelumnya")
        self.prev_btn.clicked.connect(self.main_win.playlist.play_previous)
        btn_box.addWidget(self.prev_btn)

        # Play / Pause Button
        self.play_btn = QPushButton("▶")
        self.play_btn.setObjectName("DockTileBtn")
        self.play_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.play_btn.setToolTip("Putar / Jeda (Space)")
        self.play_btn.clicked.connect(self.main_win.toggle_play_pause)
        btn_box.addWidget(self.play_btn)

        # Next Track Button
        self.next_btn = QPushButton("⏭")
        self.next_btn.setObjectName("DockTileBtn")
        self.next_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_btn.setToolTip("Selanjutnya")
        self.next_btn.clicked.connect(self.main_win.playlist.play_next)
        btn_box.addWidget(self.next_btn)

        # Volume Mute Button
        self.vol_btn = QToolButton()
        self.vol_btn.setObjectName("DockTileBtn")
        self.vol_btn.setText("🔊")
        self.vol_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.vol_btn.setToolTip("Bisu / Bunyikan (M)")
        self.vol_btn.clicked.connect(self.main_win.toggle_mute)
        btn_box.addWidget(self.vol_btn)

        # Volume Slider
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setObjectName("DockVolumeSlider")
        self.vol_slider.setRange(0, 250)
        self.vol_slider.setValue(100)
        self.vol_slider.setSingleStep(5)
        self.vol_slider.setPageStep(10)
        self.vol_slider.setFixedWidth(75)
        self.vol_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.vol_slider.setToolTip("Volume (Scroll mouse untuk ubah)")
        self.vol_slider.valueChanged.connect(self.main_win._on_volume_changed)
        btn_box.addWidget(self.vol_slider)

        # Volume percentage label
        self.vol_text = QLabel("100%")
        self.vol_text.setObjectName("DockVolText")
        self.vol_text.setStyleSheet("color: #a1a1aa; font-size: 11px; font-weight: 500; min-width: 38px;")
        btn_box.addWidget(self.vol_text)

        btn_box.addSpacing(6)

        # Duration Timestamp Label
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setObjectName("DockTimeLabel")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        btn_box.addWidget(self.time_label)

        # Compatibility aliases
        self.cur_label = QLabel()
        self.total_label = QLabel()

        # Flexible Spacer
        btn_box.addStretch()

        # Speed Button: "1x ˅"
        self.speed_btn = QPushButton("1x ˅")
        self.speed_btn.setObjectName("DockSpeedPillBtn")
        self.speed_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.speed_btn.setToolTip("Kecepatan Putar")
        self.speed_btn.clicked.connect(self._show_speed_menu)
        btn_box.addWidget(self.speed_btn)

        # Playlist Drawer Button
        self.playlist_btn = QPushButton("☰")
        self.playlist_btn.setObjectName("DockTileBtn")
        self.playlist_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.playlist_btn.setToolTip("Daftar Putar (F8)")
        self.playlist_btn.clicked.connect(self.main_win.toggle_playlist)
        btn_box.addWidget(self.playlist_btn)

        # Picture-in-Picture (PiP) Button
        self.pip_btn = QPushButton("⧉")
        self.pip_btn.setObjectName("DockTileBtn")
        self.pip_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pip_btn.setToolTip("Picture-in-Picture (Ctrl+M)")
        self.pip_btn.clicked.connect(self.main_win.toggle_pip_mode)
        btn_box.addWidget(self.pip_btn)

        # Fullscreen Button
        self.fs_btn = QPushButton("⛶")
        self.fs_btn.setObjectName("DockTileBtn")
        self.fs_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.fs_btn.setToolTip("Layar Penuh (F11)")
        self.fs_btn.clicked.connect(self.main_win.toggle_fullscreen)
        btn_box.addWidget(self.fs_btn)

        layout.addLayout(btn_box)

    def update_hw_btn(self, is_hw: bool):
        pass

    def _show_speed_menu(self):
        menu = QMenu(self)
        speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
        cur_spd = self.main_win.engine.get_rate()
        for s in speeds:
            checked = abs(s - cur_spd) < 0.05
            prefix = "✓ " if checked else "   "
            title = f"{prefix}{s}x (Normal)" if s == 1.0 else f"{prefix}{s}x"
            act = menu.addAction(title)
            act.triggered.connect(lambda _, val=s: self._set_speed(val))
        menu.exec(self.speed_btn.mapToGlobal(QPoint(0, self.speed_btn.height() + 4)))

    def _set_speed(self, speed: float):
        self.main_win.engine.set_rate(speed)
        txt = f"{speed:g}x ˅"
        self.speed_btn.setText(txt)
        self.main_win.osd.show_message(f"Kecepatan: {speed}x")

    def position_on_player(self):
        if not self.main_win.isVisible() or self.main_win.isMinimized() or self.main_win.pip_mode:
            self.hide_immediate()
            return
        if QApplication.activeWindow() is None and not getattr(self.main_win, "always_on_top", False):
            self.hide_immediate()
            return
        vw = self.main_win.video_widget
        v_global = vw.mapToGlobal(QPoint(0, 0))
        vw_w = vw.width()
        vw_h = vw.height()

        # Responsive layout adaptation based on available width
        is_compact = (vw_w < 640)
        is_ultra_compact = (vw_w < 460)

        self.vol_slider.setVisible(not is_compact)
        self.vol_text.setVisible(not is_compact)
        self.speed_btn.setVisible(not is_compact)

        self.prev_btn.setVisible(not is_ultra_compact)
        self.next_btn.setVisible(not is_ultra_compact)
        self.pip_btn.setVisible(not is_ultra_compact)

        # Stretch dock to fit full width of player window (edge to edge)
        dock_w = vw_w
        dock_h = 74
        dock_x = v_global.x()
        dock_y = v_global.y() + vw_h - dock_h
        self.setGeometry(dock_x, dock_y, dock_w, dock_h)

    def update_sync(self, cur_ms: int, total_ms: int, cur_str: str, total_str: str, is_playing: bool, vol: int):
        self.play_btn.setText("⏸" if is_playing else "▶")
        self.time_label.setText(f"{cur_str} / {total_str}")
        self.cur_label.setText(cur_str)
        self.total_label.setText(total_str)

        if not self.is_dragging and total_ms > 0:
            val = int((cur_ms / total_ms) * 1000)
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(val)
            self.seek_slider.blockSignals(False)

        self.vol_slider.blockSignals(True)
        self.vol_slider.setValue(vol)
        self.vol_slider.blockSignals(False)
        self.vol_btn.setText("🔇" if self.main_win.engine.is_muted() else "🔊")
        self.vol_text.setText(f"{vol}%")

    def set_playing(self, playing: bool):
        self.play_btn.setText("⏸" if playing else "▶")
        if playing:
            self.reset_idle_timer()
        else:
            self.idle_timer.stop()
            self.fade_in()

    def update_fs_icon(self, is_fs: bool):
        self.fs_btn.setText("⛶" if not is_fs else "🗗")

    def _on_seek_pressed(self):
        self.is_dragging = True
        self.main_win.is_slider_dragging = True
        self.idle_timer.stop()

    def _on_seek_moved(self, val: int):
        length = self.main_win.engine.get_length()
        target_ratio = max(0.0, min(1.0, val / 1000.0))
        if length > 0:
            target_ms = int(target_ratio * length)
            cur_str = self.main_win._format_time(target_ms)
            tot_str = self.main_win._format_time(length)
            self.time_label.setText(f"{cur_str} / {tot_str}")
            self.cur_label.setText(cur_str)
            self.total_label.setText(tot_str)
            self.main_win.osd.show_message(f"Posisi: {cur_str}")
        else:
            pct = int(target_ratio * 100)
            self.main_win.osd.show_message(f"Posisi: {pct}%")

    def _on_seek_released(self):
        val = self.seek_slider.value()
        target_ratio = max(0.0, min(1.0, val / 1000.0))
        length = self.main_win.engine.get_length()
        if length > 0:
            target_ms = int(target_ratio * length)
            self.main_win.engine.set_time(target_ms)
        else:
            self.main_win.engine.set_position(target_ratio)

        self.is_dragging = False
        self.main_win.is_slider_dragging = False
        if self.main_win.engine.is_playing():
            self.reset_idle_timer()

    def fade_in(self):
        if not self.main_win.isVisible() or self.main_win.isMinimized() or self.main_win.pip_mode:
            return
        if QApplication.activeWindow() is None and not getattr(self.main_win, "always_on_top", False):
            return
        self.position_on_player()
        if not self.isVisible():
            self.show()
        if self.opacity_effect.opacity() < 0.95 and self.anim.state() != QPropertyAnimation.State.Running:
            self.anim.stop()
            self.anim.setStartValue(self.opacity_effect.opacity())
            self.anim.setEndValue(1.0)
            self.anim.start()
        if self.main_win.engine.is_playing():
            self.reset_idle_timer()

    def fade_out(self):
        if self.is_dragging or not self.main_win.engine.is_playing():
            return
        if self.opacity_effect.opacity() > 0.05 and self.anim.state() != QPropertyAnimation.State.Running:
            self.anim.stop()
            self.anim.setStartValue(self.opacity_effect.opacity())
            self.anim.setEndValue(0.0)
            self.anim.start()

    def hide_immediate(self):
        self.idle_timer.stop()
        self.anim.stop()
        self.opacity_effect.setOpacity(0.0)
        self.hide()

    def reset_idle_timer(self):
        if self.main_win.engine.is_playing():
            self.idle_timer.start(2400)
        else:
            self.idle_timer.stop()

    def _on_idle_timeout(self):
        if not self.is_dragging and self.main_win.engine.is_playing():
            self.fade_out()

    def _on_anim_finished(self):
        if self.opacity_effect.opacity() <= 0.05:
            self.hide()

    def enterEvent(self, event):
        self.fade_in()
        self.idle_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.main_win.engine.is_playing():
            self.reset_idle_timer()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        self.main_win.on_user_activity()
        if self.main_win.engine.is_playing():
            self.reset_idle_timer()
        super().mouseMoveEvent(event)


class VideoWidget(QFrame):
    """
    High-performance video canvas with:
    - Automatic Win32 Direct3D child window synchronization (no letterboxing / scaling bugs)
    - Fullscreen & window resizing anchor
    - Mouse Gestures (Left: Brightness, Right: Volume 250%, Center: Seek)
    - Right-click Context Menu triggering
    - Single click: Play/Pause, Double click: Fullscreen
    """
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Qt.GlobalColor.black)
        self.setPalette(palette)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda pos: self.main_win.show_context_menu(pos, is_global=False))

        # Gesture tracking state
        self.drag_start_pos = None
        self.drag_mode = None  # 'brightness', 'volume', 'seek', None
        self.initial_brightness = 1.0
        self.initial_volume = 100
        self.initial_time_ms = 0
        self.target_seek_ms = 0

        # Single click debounce timer for clean double-click fullscreen
        self.single_click_timer = QTimer(self)
        self.single_click_timer.setSingleShot(True)
        self.single_click_timer.setInterval(220)
        self.single_click_timer.timeout.connect(self._on_single_click_timeout)

    def paintEvent(self, event):
        # Fill canvas with solid black (provides seamless letterbox / pillarbox bars)
        painter = QPainter(self)
        painter.fillRect(event.rect(), Qt.GlobalColor.black)

    def _on_single_click_timeout(self):
        self.main_win.toggle_play_pause()

    def sync_child_size(self):
        """Ensures the VLC video child window maintains correct aspect ratio (letterboxing/pillarboxing) and respects Windows Z-order occlusion."""
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
                    GWL_STYLE = -16
                    GWL_EXSTYLE = -20
                    WS_CLIPCHILDREN = 0x02000000
                    WS_CLIPSIBLINGS = 0x04000000
                    WS_EX_TOPMOST = 0x00000008

                    # Enforce WS_CLIPCHILDREN and WS_CLIPSIBLINGS on parent window
                    parent_style = user32.GetWindowLongW(hwnd, GWL_STYLE)
                    if not (parent_style & (WS_CLIPCHILDREN | WS_CLIPSIBLINGS)):
                        user32.SetWindowLongW(hwnd, GWL_STYLE, parent_style | WS_CLIPCHILDREN | WS_CLIPSIBLINGS)

                    # Compute proportional letterbox / pillarbox rect to prevent video stretching
                    aspect_ratio = self.main_win.engine.get_video_aspect_ratio()
                    if aspect_ratio > 0:
                        container_ar = w / float(h)
                        if container_ar > aspect_ratio:
                            # Window is wider than video -> Pillarbox (black bars on left and right)
                            target_h = h
                            target_w = int(round(h * aspect_ratio))
                            target_x = (w - target_w) // 2
                            target_y = 0
                        else:
                            # Window is taller than video -> Letterbox (black bars on top and bottom)
                            target_w = w
                            target_h = int(round(w / aspect_ratio))
                            target_x = 0
                            target_y = (h - target_h) // 2
                    else:
                        target_x, target_y, target_w, target_h = 0, 0, w, h

                    def enum_proc(child_hwnd, lparam):
                        # Strip WS_EX_TOPMOST from child vout if main window is not in always_on_top mode
                        if not getattr(self.main_win, "always_on_top", False):
                            child_ex = user32.GetWindowLongW(child_hwnd, GWL_EXSTYLE)
                            if child_ex & WS_EX_TOPMOST:
                                user32.SetWindowLongW(child_hwnd, GWL_EXSTYLE, child_ex & ~WS_EX_TOPMOST)
                                user32.SetWindowPos(child_hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, 0x0013)

                        # Enforce WS_CLIPSIBLINGS so the child Direct3D window clips behind occluding windows
                        child_style = user32.GetWindowLongW(child_hwnd, GWL_STYLE)
                        if not (child_style & WS_CLIPSIBLINGS):
                            user32.SetWindowLongW(child_hwnd, GWL_STYLE, child_style | WS_CLIPSIBLINGS)

                        # Distinguish direct child vout container vs grandchild Direct3D swapchain surface
                        parent_of_child = user32.GetParent(child_hwnd)
                        if parent_of_child == hwnd:
                            # Direct child vout container: position at letterbox / pillarbox offset
                            user32.MoveWindow(child_hwnd, target_x, target_y, target_w, target_h, True)
                        else:
                            # Grandchild Direct3D surface: fill parent container completely
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
        if hasattr(self.main_win, "resume_banner") and self.main_win.resume_banner.isVisible():
            self.main_win.resume_banner.reposition()
        if hasattr(self.main_win, "next_episode_banner") and self.main_win.next_episode_banner.isVisible():
            self.main_win.next_episode_banner.reposition()

    def contextMenuEvent(self, event):
        self.main_win.show_context_menu(event.globalPos(), is_global=True)
        event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            if self.main_win.fullscreen_mode or self.main_win.isFullScreen():
                self.main_win.toggle_fullscreen()
                event.accept()
                return
        self.main_win.keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            self.main_win.show_context_menu(event.globalPosition().toPoint(), is_global=True)
            event.accept()
            return
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.main_win.toggle_mute()
            event.accept()
            return
        elif event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.pos()
            self.drag_mode = None
            self.initial_brightness = self.main_win.engine.brightness
            self.initial_volume = self.main_win.engine.get_volume()
            self.initial_time_ms = self.main_win.engine.get_time()
            self.target_seek_ms = self.initial_time_ms
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        self.main_win.on_user_activity()

        # Handle Floating Dock auto-show / proximity in fullscreen mode
        if hasattr(self.main_win, "floating_dock") and (self.main_win.isActiveWindow() or self.main_win.always_on_top):
            if self.main_win.fullscreen_mode or self.main_win.isFullScreen():
                if event.pos().y() >= self.height() - 150:
                    self.main_win.floating_dock.fade_in()
                elif event.pos().y() < self.height() - 220:
                    self.main_win.floating_dock.fade_out()
            else:
                self.main_win.floating_dock.fade_in()

        # Handle Drag Gestures
        if (event.buttons() & Qt.MouseButton.LeftButton) and self.drag_start_pos:
            dx = event.pos().x() - self.drag_start_pos.x()
            dy = event.pos().y() - self.drag_start_pos.y()

            # Identify gesture type if not locked yet
            if self.drag_mode is None:
                if abs(dy) > 12 and abs(dy) > abs(dx):
                    w = max(1, self.width())
                    if self.drag_start_pos.x() < (w * 0.35):
                        self.drag_mode = "brightness"
                    elif self.drag_start_pos.x() > (w * 0.65):
                        self.drag_mode = "volume"
                elif abs(dx) > 16 and abs(dx) > abs(dy):
                    self.drag_mode = "seek"

            # Execute active gesture
            h = max(1, self.height())
            w = max(1, self.width())

            if self.drag_mode == "brightness":
                delta_b = -dy / (h * 0.6)
                new_b = max(0.0, min(2.0, self.initial_brightness + delta_b))
                self.main_win.engine.set_video_adjustments(
                    brightness=new_b,
                    contrast=self.main_win.engine.contrast,
                    saturation=self.main_win.engine.saturation,
                    hue=self.main_win.engine.hue,
                    gamma=self.main_win.engine.gamma
                )
                self.main_win.osd.show_message(f"Kecerahan: {int(new_b * 100)}%")
                event.accept()
                return

            elif self.drag_mode == "volume":
                delta_vol = int((-dy / (h * 0.6)) * 120)
                new_vol = max(0, min(250, self.initial_volume + delta_vol))
                self.main_win.vol_slider.setValue(new_vol)
                event.accept()
                return

            elif self.drag_mode == "seek":
                tot_ms = self.main_win.engine.get_length()
                if tot_ms > 0:
                    delta_ms = int((dx / (w * 0.8)) * min(tot_ms, 180000))
                    self.target_seek_ms = max(0, min(tot_ms, self.initial_time_ms + delta_ms))
                    time_str = self.main_win._format_time(self.target_seek_ms)
                    sign = "+" if delta_ms >= 0 else ""
                    self.main_win.osd.show_message(f"Lompat: {sign}{delta_ms // 1000}s -> {time_str}")
                event.accept()
                return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.drag_mode == "seek" and self.target_seek_ms is not None:
                self.main_win.engine.set_time(self.target_seek_ms)
            elif self.drag_mode is None and self.drag_start_pos:
                # If moved less than 8px, count as single click play/pause with double-click debounce
                dist = (event.pos() - self.drag_start_pos).manhattanLength()
                if dist < 8:
                    self.single_click_timer.start()

            self.drag_mode = None
            self.drag_start_pos = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.single_click_timer.stop()
            self.main_win.toggle_fullscreen()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        # Focus widget on scroll and notify user activity
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.main_win.on_user_activity()

        delta_y = event.angleDelta().y()
        delta_x = event.angleDelta().x()

        modifiers = event.modifiers()

        # 1. Shift + Scroll: Seeking 5 seconds
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            delta = delta_y if delta_y != 0 else delta_x
            if delta != 0:
                self.main_win.seek_relative(5000 if delta > 0 else -5000)
            event.accept()
            return

        # 2. Ctrl + Scroll: Seeking 30 seconds
        elif modifiers & Qt.KeyboardModifier.ControlModifier:
            delta = delta_y if delta_y != 0 else delta_x
            if delta != 0:
                self.main_win.seek_relative(30000 if delta > 0 else -30000)
            event.accept()
            return

        # 3. Horizontal Wheel Tilt: Seeking 5 seconds
        elif delta_x != 0 and abs(delta_x) > abs(delta_y):
            self.main_win.seek_relative(5000 if delta_x > 0 else -5000)
            event.accept()
            return

        # 4. Standard Vertical Scroll: Volume adjustment (+/- 5%)
        elif delta_y != 0:
            self.main_win.adjust_volume(5 if delta_y > 0 else -5)
            event.accept()
            return

        super().wheelEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OXPlayer")
        self.resize(1100, 700)
        self.setMinimumSize(640, 420)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)

        self.is_slider_dragging = False
        self.fullscreen_mode = False
        self.pip_mode = False
        self.always_on_top = False
        self.current_file_path = ""
        self._media_ended_handled = False

        # Initialize Player Engine
        self.engine = PlayerEngine()

        # Active Theme System
        self.current_theme_name = self.engine.config_data.get("theme", "Obsidian Dark")
        self.setStyleSheet(get_theme_stylesheet(self.current_theme_name))

        # True PiP Floating Window
        self.pip_window = PiPWindow(self)
        self.pip_window.restore_requested.connect(self.exit_pip_mode)
        self.pip_window.close_requested.connect(self.exit_pip_mode)

        # Recent files storage
        self.recent_files_file = os.path.join(os.path.expanduser("~"), ".oxplayer_recent.json")
        self.recent_files = self._load_recent_files()

        # Background / auto pause on minimize & Auto-Play Next in Folder
        self.auto_pause_on_minimize = bool(self.engine.config_data.get("auto_pause_on_minimize", False))
        self.auto_queue_folder = bool(self.engine.config_data.get("auto_queue_folder", True))
        self.auto_binge_watching = bool(self.engine.config_data.get("auto_binge_watching", True))
        self._next_episode_prompt_active = False
        self._next_episode_cancelled_for_media = False
        self._was_playing_before_minimize = False

        self._setup_ui()
        self._setup_menu_bar()
        self._setup_timers()
        self._setup_seek_tooltip()

        # Install global application event filter for Escape key and global shortcuts
        QApplication.instance().installEventFilter(self)


        # Connect HWND
        self.engine.set_hwnd(self.video_widget.winId())

    def _load_recent_files(self) -> list:
        try:
            if os.path.exists(self.recent_files_file):
                with open(self.recent_files_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_recent_files(self):
        try:
            with open(self.recent_files_file, "w", encoding="utf-8") as f:
                json.dump(self.recent_files[:12], f, indent=2)
        except Exception:
            pass

    def add_to_recent_files(self, path: str):
        if not path or path.startswith(("http://", "https://", "rtsp://")):
            return
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self._save_recent_files()
        self._update_recent_menu()

    def clear_recent_files(self):
        self.recent_files.clear()
        self._save_recent_files()
        self._update_recent_menu()
        self.osd.show_message("Riwayat Berkas Dihapus")

    def _setup_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(True)

        video_container = QWidget()
        video_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        video_layout = QVBoxLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(0)

        self.video_widget = VideoWidget(self, video_container)
        video_layout.addWidget(self.video_widget)

        self.osd = OSDOverlay(self)
        self.stats_hud = LiveStatsHUD(self)

        # VLC-style Interactive Resume Playback Banner (owned Tool window, floats above Direct3D)
        self.resume_banner = ResumePromptBanner(self)
        self.resume_banner.resume_requested.connect(self._on_resume_banner_confirmed)
        self.resume_banner.restart_requested.connect(self._on_resume_banner_restart)
        self.resume_banner.hide()

        # Binge-Watching Next Episode Notification Banner (owned Tool window, floats above Direct3D)
        self.next_episode_banner = NextEpisodeBanner(self)
        self.next_episode_banner.play_next_requested.connect(self._on_next_episode_confirmed)
        self.next_episode_banner.cancelled.connect(self._on_next_episode_cancelled)
        self.next_episode_banner.hide()

        self.playlist = PlaylistWidget(self)
        self.playlist.track_selected.connect(self.play_file)
        self.playlist.hide()

        self.splitter.addWidget(video_container)
        self.splitter.addWidget(self.playlist)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        # Video container receives full vertical stretch priority (1)
        main_layout.addWidget(self.splitter, 1)

        # Floating Overlays: Center Play Button and Modern Floating Control Dock
        self.center_play_btn = CenterPlayButton(self)
        self.floating_dock = ModernFloatingDock(self)
        self.fs_overlay = self.floating_dock  # Compatibility alias
        self.control_bar = self.floating_dock  # Compatibility alias

        # Control aliases for seamless backward compatibility
        self.seek_slider = self.floating_dock.seek_slider
        self.vol_slider = self.floating_dock.vol_slider
        self.play_btn = self.floating_dock.play_btn
        self.prev_btn = self.floating_dock.prev_btn
        self.next_btn = self.floating_dock.next_btn
        self.playlist_btn = self.floating_dock.playlist_btn
        self.vol_btn = self.floating_dock.vol_btn
        self.time_label = self.floating_dock.time_label
        self.cur_time_label = self.floating_dock.cur_label
        self.total_time_label = self.floating_dock.total_label
        self.speed_btn = self.floating_dock.speed_btn
        self.fs_btn = self.floating_dock.fs_btn
        self.pip_btn = self.floating_dock.pip_btn

    def _setup_menu_bar(self):
        menubar = self.menuBar()
        menubar.show()

        # 1. Media
        media_menu = menubar.addMenu("&Media")
        open_act = media_menu.addAction("Buka File...")
        open_act.setShortcut(QKeySequence("Ctrl+O"))
        open_act.triggered.connect(self.open_file_dialog)

        open_stream_act = media_menu.addAction("Buka Network Stream / URL...")
        open_stream_act.setShortcut(QKeySequence("Ctrl+U"))
        open_stream_act.triggered.connect(self.open_stream_dialog)

        open_folder_act = media_menu.addAction("Buka Folder Media...")
        open_folder_act.triggered.connect(self.open_folder_dialog)

        history_act = media_menu.addAction("Riwayat Tontonan & Lanjut (Continue Watching)...")
        history_act.setShortcut(QKeySequence("Ctrl+Y"))
        history_act.triggered.connect(self.open_continue_watching)

        self.recent_menu = media_menu.addMenu("Riwayat File (Recent Media)")
        self._update_recent_menu()

        media_menu.addSeparator()
        close_media_act = media_menu.addAction("Tutup Pemutaran")
        close_media_act.setShortcut(QKeySequence("Ctrl+W"))
        close_media_act.triggered.connect(self.close_media)

        exit_act = media_menu.addAction("Keluar")
        exit_act.setShortcut(QKeySequence("Alt+F4"))
        exit_act.triggered.connect(self.close)

        # 2. Playback
        play_menu = menubar.addMenu("&Playback")
        play_pause_act = play_menu.addAction("Putar / Jeda")
        play_pause_act.setShortcut(QKeySequence(Qt.Key.Key_Space))
        play_pause_act.triggered.connect(self.toggle_play_pause)

        stop_act = play_menu.addAction("Hentikan (Stop)")
        stop_act.triggered.connect(self.stop)

        play_menu.addSeparator()
        rew_act = play_menu.addAction("Lompat Mundur 10 Detik")
        rew_act.setShortcut(QKeySequence("Left"))
        rew_act.triggered.connect(lambda: self.seek_relative(-10000))

        fwd_act = play_menu.addAction("Lompat Maju 10 Detik")
        fwd_act.setShortcut(QKeySequence("Right"))
        fwd_act.triggered.connect(lambda: self.seek_relative(10000))

        rew_5_act = play_menu.addAction("Lompat Mundur 5 Detik")
        rew_5_act.setShortcut(QKeySequence("Shift+Left"))
        rew_5_act.triggered.connect(lambda: self.seek_relative(-5000))

        fwd_5_act = play_menu.addAction("Lompat Maju 5 Detik")
        fwd_5_act.setShortcut(QKeySequence("Shift+Right"))
        fwd_5_act.triggered.connect(lambda: self.seek_relative(5000))

        rew_30_act = play_menu.addAction("Lompat Mundur 30 Detik")
        rew_30_act.setShortcut(QKeySequence("Ctrl+Left"))
        rew_30_act.triggered.connect(lambda: self.seek_relative(-30000))

        fwd_30_act = play_menu.addAction("Lompat Maju 30 Detik")
        fwd_30_act.setShortcut(QKeySequence("Ctrl+Right"))
        fwd_30_act.triggered.connect(lambda: self.seek_relative(30000))

        step_act = play_menu.addAction("Langkah Frame (Frame Step)")
        step_act.setShortcut(QKeySequence("F"))
        step_act.triggered.connect(self.frame_step)

        jump_act = play_menu.addAction("Lompat ke Waktu...")
        jump_act.setShortcut(QKeySequence("Ctrl+G"))
        jump_act.triggered.connect(self.open_jump_to_time)

        play_menu.addSeparator()
        speed_sub = play_menu.addMenu("Kecepatan Putar (Speed)")
        for sp_val in [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
            title = f"{sp_val}x (Normal)" if sp_val == 1.0 else f"{sp_val}x"
            act = speed_sub.addAction(title)
            act.triggered.connect(lambda checked, val=sp_val: self._set_speed_exact(val))
        speed_sub.addSeparator()
        speed_up = speed_sub.addAction("Percepat (+0.1x)")
        speed_up.setShortcut(QKeySequence("C"))
        speed_up.triggered.connect(lambda: self.adjust_speed(0.1))
        speed_down = speed_sub.addAction("Perlambat (-0.1x)")
        speed_down.setShortcut(QKeySequence("X"))
        speed_down.triggered.connect(lambda: self.adjust_speed(-0.1))
        speed_reset = speed_sub.addAction("Reset Kecepatan (1.0x)")
        speed_reset.setShortcut(QKeySequence("Z"))
        speed_reset.triggered.connect(self.reset_speed)

        play_menu.addSeparator()
        # Bookmarks sub-menu
        bm_sub = play_menu.addMenu("Penanda Momen (Bookmarks)")
        bm_add = bm_sub.addAction("Tambah Bookmark pada Detik Ini")
        bm_add.setShortcut(QKeySequence("B"))
        bm_add.triggered.connect(self.add_bookmark_now)

        bm_next = bm_sub.addAction("Lompat ke Bookmark Berikutnya")
        bm_next.setShortcut(QKeySequence("Shift+B"))
        bm_next.triggered.connect(self.jump_next_bookmark)

        bm_prev = bm_sub.addAction("Lompat ke Bookmark Sebelumnya")
        bm_prev.setShortcut(QKeySequence("Ctrl+Shift+B"))
        bm_prev.triggered.connect(self.jump_prev_bookmark)

        bm_manage = bm_sub.addAction("Kelola Semua Bookmark...")
        bm_manage.triggered.connect(self.open_bookmark_manager)

        play_menu.addSeparator()
        # A-B Repeat
        ab_sub = play_menu.addMenu("Mode Ulang (A-B Repeat)")
        ab_set_a = ab_sub.addAction("Set Titik A ([)")
        ab_set_a.setShortcut(QKeySequence("["))
        ab_set_a.triggered.connect(self.set_ab_point_a)
        ab_set_b = ab_sub.addAction("Set Titik B (])")
        ab_set_b.setShortcut(QKeySequence("]"))
        ab_set_b.triggered.connect(self.set_ab_point_b)
        ab_reset = ab_sub.addAction("Reset A-B Repeat (\\)")
        ab_reset.setShortcut(QKeySequence("\\"))
        ab_reset.triggered.connect(self.clear_ab_repeat)

        play_menu.addSeparator()
        # Resume Playback Settings (VLC style)
        resume_menu = play_menu.addMenu("Lanjut Menonton (Resume Playback)")
        self.resume_group = QActionGroup(self)
        self.resume_group.setExclusive(True)

        ask_act = resume_menu.addAction("Tanya Sebelum Melanjutkan (Seperti VLC)")
        ask_act.setCheckable(True)
        self.resume_group.addAction(ask_act)
        ask_act.triggered.connect(lambda: self.set_resume_mode("ask"))

        always_act = resume_menu.addAction("Selalu Lanjutkan Otomatis")
        always_act.setCheckable(True)
        self.resume_group.addAction(always_act)
        always_act.triggered.connect(lambda: self.set_resume_mode("always"))

        never_act = resume_menu.addAction("Jangan Pernah Lanjutkan (Mulai dari Awal)")
        never_act.setCheckable(True)
        self.resume_group.addAction(never_act)
        never_act.triggered.connect(lambda: self.set_resume_mode("never"))

        current_res_mode = self.engine.config_data.get("resume_mode", "ask")
        if current_res_mode == "always":
            always_act.setChecked(True)
        elif current_res_mode == "never":
            never_act.setChecked(True)
        else:
            ask_act.setChecked(True)

        play_menu.addSeparator()
        self.auto_queue_act = play_menu.addAction("Antrean Otomatis Episode Satu Folder (Auto-Play Next in Folder)")
        self.auto_queue_act.setCheckable(True)
        self.auto_queue_act.setChecked(self.auto_queue_folder)
        self.auto_queue_act.toggled.connect(self.toggle_auto_queue_folder)

        self.binge_act = play_menu.addAction("Binge-Watching Otomatis (Hitung Mundur Episode Selanjutnya)")
        self.binge_act.setCheckable(True)
        self.binge_act.setChecked(self.auto_binge_watching)
        self.binge_act.toggled.connect(self.toggle_binge_watching)

        self.auto_pause_act = play_menu.addAction("Jeda Otomatis Saat Diminimalkan (Auto-Pause on Minimize)")
        self.auto_pause_act.setCheckable(True)
        self.auto_pause_act.setChecked(self.auto_pause_on_minimize)
        self.auto_pause_act.toggled.connect(self.toggle_auto_pause_on_minimize)

        # 3. Audio
        audio_menu = menubar.addMenu("&Audio")
        cycle_aud_act = audio_menu.addAction("Ganti Track Audio (A)")
        cycle_aud_act.setShortcut(QKeySequence("A"))
        cycle_aud_act.triggered.connect(self.cycle_audio_track)

        self.audio_track_menu = audio_menu.addMenu("Pilih Track Audio")
        self.audio_track_menu.aboutToShow.connect(self._populate_audio_tracks)

        surround_sub = audio_menu.addMenu("Mode Output Audio")
        for s_mode, s_code in [("Stereo (Default)", "Original"),
                               ("Virtual Surround", "Dolby"),
                               ("Pelebar Stereo", "DTS"),
                               ("Stereo Downmix", "Stereo")]:
            act = surround_sub.addAction(s_mode)
            act.triggered.connect(lambda chk, c=s_code, m=s_mode: self._set_surround_mode(c, m))

        crystal_act = audio_menu.addAction("Penguat Vokal")
        crystal_act.triggered.connect(self.toggle_crystal_clear)

        norm_act = audio_menu.addAction("Normalisasi Volume (Night Mode)")
        norm_act.setShortcut(QKeySequence("Shift+N"))
        norm_act.triggered.connect(self.toggle_audio_normalizer)

        audio_fx_act = audio_menu.addAction("Equalizer & Pengaturan Audio...")
        audio_fx_act.setShortcut(QKeySequence("Ctrl+A"))
        audio_fx_act.triggered.connect(self.open_audio_effects)

        audio_menu.addSeparator()
        vol_up_act = audio_menu.addAction("Naikkan Volume (+5%)")
        vol_up_act.setShortcut(QKeySequence("Up"))
        vol_up_act.triggered.connect(lambda: self.adjust_volume(5))

        vol_down_act = audio_menu.addAction("Turunkan Volume (-5%)")
        vol_down_act.setShortcut(QKeySequence("Down"))
        vol_down_act.triggered.connect(lambda: self.adjust_volume(-5))

        mute_act = audio_menu.addAction("Bisu / Bunyikan (Mute)")
        mute_act.setShortcut(QKeySequence("M"))
        mute_act.triggered.connect(self.toggle_mute)

        aud_del_plus = audio_menu.addAction("Audio Delay (+50ms)")
        aud_del_plus.setShortcut(QKeySequence("+"))
        aud_del_plus.triggered.connect(lambda: self.adjust_audio_delay(50000))

        aud_del_min = audio_menu.addAction("Audio Delay (-50ms)")
        aud_del_min.setShortcut(QKeySequence("-"))
        aud_del_min.triggered.connect(lambda: self.adjust_audio_delay(-50000))

        # 4. Video
        video_menu = menubar.addMenu("&Video")
        self.hw_menu_act = video_menu.addAction("Decoding Hardware (GPU)")
        self.hw_menu_act.setCheckable(True)
        self.hw_menu_act.setChecked(self.engine.hw_accel_enabled)
        self.hw_menu_act.setShortcut(QKeySequence("Ctrl+H"))
        self.hw_menu_act.triggered.connect(self.toggle_hw_accel)
        video_menu.addSeparator()

        rot_sub = video_menu.addMenu("Rotasi & Balik")
        rot_90 = rot_sub.addAction("Putar 90° (R)")
        rot_90.setShortcut(QKeySequence("R"))
        rot_90.triggered.connect(self.cycle_rotation)
        rot_180 = rot_sub.addAction("Putar 180°")
        rot_180.triggered.connect(lambda: self.set_rotation_angle(180))
        rot_270 = rot_sub.addAction("Putar 270°")
        rot_270.triggered.connect(lambda: self.set_rotation_angle(270))
        rot_0 = rot_sub.addAction("Reset Rotasi (0°)")
        rot_0.triggered.connect(lambda: self.set_rotation_angle(0))
        rot_sub.addSeparator()
        flip_h = rot_sub.addAction("Balik Horizontal")
        flip_h.triggered.connect(lambda: self.set_flip_mode("hflip"))
        flip_v = rot_sub.addAction("Balik Vertikal")
        flip_v.triggered.connect(lambda: self.set_flip_mode("vflip"))
        flip_none = rot_sub.addAction("Normal")
        flip_none.triggered.connect(lambda: self.set_flip_mode("none"))

        self.ratio_menu = video_menu.addMenu("Rasio Aspek")
        self.ratio_menu.aboutToShow.connect(self._refresh_ratio_menu)
        self._refresh_ratio_menu()

        snapshot_act = video_menu.addAction("Simpan Tangkapan Layar (Snapshot)")
        snapshot_act.setShortcut(QKeySequence("Ctrl+E"))
        snapshot_act.triggered.connect(self.take_snapshot)

        copy_snap_act = video_menu.addAction("Salin Tangkapan Layar ke Clipboard")
        copy_snap_act.setShortcut(QKeySequence("Ctrl+Shift+C"))
        copy_snap_act.triggered.connect(self.copy_snapshot_to_clipboard)

        video_adj_act = video_menu.addAction("Pengaturan Gambar & Warna...")
        video_adj_act.triggered.connect(self.open_video_adjust)

        # 5. Subtitle
        sub_menu = menubar.addMenu("&Subtitle")
        cycle_sub_act = sub_menu.addAction("Ganti Track Subtitle (V)")
        cycle_sub_act.setShortcut(QKeySequence("V"))
        cycle_sub_act.triggered.connect(self.cycle_subtitle_track)

        self.sub_track_menu = sub_menu.addMenu("Pilih Track Subtitle")
        self.sub_track_menu.aboutToShow.connect(self._populate_sub_tracks)

        online_sub_act = sub_menu.addAction("Cari Subtitle Online...")
        online_sub_act.setShortcut(QKeySequence("Ctrl+Shift+S"))
        online_sub_act.triggered.connect(self.open_online_subtitles)

        load_sub_act = sub_menu.addAction("Muat File Subtitle (.srt, .ass, .vtt)...")
        load_sub_act.triggered.connect(self.load_subtitle_file)

        sub_style_act = sub_menu.addAction("Pengaturan Subtitle...")
        sub_style_act.triggered.connect(self.open_subtitle_style)

        sub_menu.addSeparator()
        sub_del_plus = sub_menu.addAction("Subtitle Delay (+50ms)")
        sub_del_plus.setShortcut(QKeySequence("Shift+]"))
        sub_del_plus.triggered.connect(lambda: self.adjust_sub_delay(50000))

        sub_del_min = sub_menu.addAction("Subtitle Delay (-50ms)")
        sub_del_min.setShortcut(QKeySequence("Shift+["))
        sub_del_min.triggered.connect(lambda: self.adjust_sub_delay(-50000))

        # 6. Tools
        tools_menu = menubar.addMenu("&Tools")
        t_aud_act = tools_menu.addAction("Equalizer & Pengaturan Audio...")
        t_aud_act.triggered.connect(self.open_audio_effects)

        t_vid_act = tools_menu.addAction("Pengaturan Gambar & Warna...")
        t_vid_act.triggered.connect(self.open_video_adjust)

        t_bm_act = tools_menu.addAction("Kelola Bookmark...")
        t_bm_act.triggered.connect(self.open_bookmark_manager)

        tools_menu.addSeparator()
        info_act = tools_menu.addAction("Informasi Media & Codec...")
        info_act.setShortcut(QKeySequence("Ctrl+J"))
        info_act.triggered.connect(self.open_media_info)

        # 7. View
        view_menu = menubar.addMenu("&View")
        fs_act = view_menu.addAction("Layar Penuh (Fullscreen)")
        fs_act.setShortcuts([QKeySequence("Alt+Return"), QKeySequence("F11")])
        fs_act.triggered.connect(self.toggle_fullscreen)

        pip_act = view_menu.addAction("Picture-in-Picture (PiP)")
        pip_act.setShortcut(QKeySequence("Ctrl+M"))
        pip_act.triggered.connect(self.toggle_pip_mode)

        ontop_act = view_menu.addAction("Selalu di Atas (Always on Top)")
        ontop_act.setShortcut(QKeySequence("Ctrl+T"))
        ontop_act.setCheckable(True)
        ontop_act.setChecked(self.always_on_top)
        ontop_act.triggered.connect(self.toggle_always_on_top)
        self.ontop_act = ontop_act

        pl_act = view_menu.addAction("Daftar Putar (Playlist)")
        pl_act.setShortcut(QKeySequence("F8"))
        pl_act.triggered.connect(self.toggle_playlist)

        self.stats_hud_act = view_menu.addAction("Informasi Stream (Tab)")
        self.stats_hud_act.setShortcut(QKeySequence("Tab"))
        self.stats_hud_act.setCheckable(True)
        self.stats_hud_act.setChecked(False)
        self.stats_hud_act.triggered.connect(self.toggle_stats_hud)

        view_menu.addSeparator()
        scale_sub = view_menu.addMenu("Ukuran Jendela")
        scale_50 = scale_sub.addAction("Ukuran 50%")
        scale_50.setShortcut(QKeySequence("1"))
        scale_50.triggered.connect(lambda: self.set_window_scale(0.5))
        scale_100 = scale_sub.addAction("Ukuran 100% (Normal)")
        scale_100.setShortcut(QKeySequence("2"))
        scale_100.triggered.connect(lambda: self.set_window_scale(1.0))
        scale_150 = scale_sub.addAction("Ukuran 150%")
        scale_150.setShortcut(QKeySequence("3"))
        scale_150.triggered.connect(lambda: self.set_window_scale(1.5))
        scale_200 = scale_sub.addAction("Ukuran 200%")
        scale_200.setShortcut(QKeySequence("4"))
        scale_200.triggered.connect(lambda: self.set_window_scale(2.0))

        # 8. Help
        help_menu = menubar.addMenu("&Help")
        shortcuts_act = help_menu.addAction("Pintasan Keyboard & Mouse...")
        shortcuts_act.setShortcut(QKeySequence("F1"))
        shortcuts_act.triggered.connect(self.open_shortcuts_cheat_sheet)

    def _update_recent_menu(self):
        self.recent_menu.clear()
        if not self.recent_files:
            act = self.recent_menu.addAction("Belum ada riwayat")
            act.setEnabled(False)
            return
        for path in self.recent_files:
            name = os.path.basename(path)
            act = self.recent_menu.addAction(name)
            act.triggered.connect(lambda chk, p=path: self.play_file(p))
        self.recent_menu.addSeparator()
        clear_act = self.recent_menu.addAction("Hapus Riwayat Berkas")
        clear_act.triggered.connect(self.clear_recent_files)

    def _setup_timers(self):
        self.timer = QTimer(self)
        initial_interval = 250 if self.engine.low_spec_mode else 100
        self.timer.setInterval(initial_interval)
        self.timer.timeout.connect(self._update_playback_ui)
        self.timer.start()

        self.hide_cursor_timer = QTimer(self)
        self.hide_cursor_timer.setInterval(2500)
        self.hide_cursor_timer.timeout.connect(self._auto_hide_fullscreen_controls)

    def _setup_seek_tooltip(self):
        self.seek_tooltip = QLabel(self, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.seek_tooltip.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.seek_tooltip.setStyleSheet("""
            QLabel {
                background-color: rgba(20, 22, 28, 245);
                color: #f4f4f5;
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 4px;
                padding: 3px 8px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                font-weight: 600;
            }
        """)
        self.seek_tooltip.hide()
        self.seek_slider.installEventFilter(self)

    def eventFilter(self, watched, event):
        # 1. Seek Slider Hover Tooltip
        if watched == self.seek_slider:
            if event.type() == QEvent.Type.MouseMove:
                tot_ms = self.engine.get_length()
                width = self.seek_slider.width()
                if width > 0:
                    x = event.pos().x()
                    ratio = max(0.0, min(1.0, x / width))
                    if tot_ms > 0:
                        target_ms = int(ratio * tot_ms)
                        self.seek_tooltip.setText(self._format_time(target_ms))
                    elif self.engine.is_media_loaded():
                        self.seek_tooltip.setText(f"{int(ratio * 100)}%")
                    else:
                        self.seek_tooltip.setText("0:00")
                    self.seek_tooltip.adjustSize()
                    global_pt = self.seek_slider.mapToGlobal(event.pos())
                    self.seek_tooltip.move(global_pt.x() - self.seek_tooltip.width() // 2, global_pt.y() - 34)
                    self.seek_tooltip.show()
            elif event.type() == QEvent.Type.Leave:
                self.seek_tooltip.hide()

        # 2. KeyPress & KeyRelease Handling (Space & Media Keys global guarantee)
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            key = event.key()
            from PyQt6.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit
            focused = QApplication.focusWidget()
            is_text_field = isinstance(focused, (QLineEdit, QTextEdit, QPlainTextEdit))

            if not is_text_field:
                # Dedicated Space Key Intercept: guarantees play/pause without focus loss
                if key == Qt.Key.Key_Space:
                    if event.type() == QEvent.Type.KeyPress and not event.isAutoRepeat():
                        self.toggle_play_pause()
                    return True

                # Hardware Multimedia Keyboard & Bluetooth Headset Keys
                elif key in (Qt.Key.Key_MediaPlay, Qt.Key.Key_MediaPause, Qt.Key.Key_MediaTogglePlayPause):
                    if event.type() == QEvent.Type.KeyPress and not event.isAutoRepeat():
                        self.toggle_play_pause()
                    return True
                elif key == Qt.Key.Key_MediaNext:
                    if event.type() == QEvent.Type.KeyPress and not event.isAutoRepeat():
                        self.playlist.play_next()
                    return True
                elif key == Qt.Key.Key_MediaPrevious:
                    if event.type() == QEvent.Type.KeyPress and not event.isAutoRepeat():
                        self.playlist.play_previous()
                    return True
                elif key == Qt.Key.Key_MediaStop:
                    if event.type() == QEvent.Type.KeyPress and not event.isAutoRepeat():
                        self.stop()
                    return True
                elif key == Qt.Key.Key_VolumeUp:
                    if event.type() == QEvent.Type.KeyPress:
                        self.adjust_volume(5)
                    return True
                elif key == Qt.Key.Key_VolumeDown:
                    if event.type() == QEvent.Type.KeyPress:
                        self.adjust_volume(-5)
                    return True
                elif key == Qt.Key.Key_VolumeMute:
                    if event.type() == QEvent.Type.KeyPress and not event.isAutoRepeat():
                        self.toggle_mute()
                    return True

                elif event.type() == QEvent.Type.KeyPress:
                    if self._handle_playback_shortcut(event):
                        return True

        return super().eventFilter(watched, event)

    def _handle_playback_shortcut(self, event: QKeyEvent) -> bool:
        key = event.key()
        modifiers = event.modifiers()

        # ESC key: Exit fullscreen or PiP
        if key == Qt.Key.Key_Escape:
            if self.fullscreen_mode or self.isFullScreen():
                self.toggle_fullscreen()
                return True
            if self.pip_mode:
                self.exit_pip_mode()
                return True
            return False

        # Media playback shortcuts
        if key == Qt.Key.Key_Space:
            self.toggle_play_pause()
            return True
        elif key == Qt.Key.Key_Left:
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.seek_relative(-30000)
            elif modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.seek_relative(-5000)
            else:
                self.seek_relative(-10000)
            return True
        elif key == Qt.Key.Key_Right:
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.seek_relative(30000)
            elif modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.seek_relative(5000)
            else:
                self.seek_relative(10000)
            return True
        elif key == Qt.Key.Key_Up:
            self.adjust_volume(5)
            return True
        elif key == Qt.Key.Key_Down:
            self.adjust_volume(-5)
            return True
        elif key == Qt.Key.Key_M:
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.toggle_pip_mode()
            else:
                self.toggle_mute()
            return True
        elif key == Qt.Key.Key_F:
            self.frame_step()
            return True
        elif key == Qt.Key.Key_A:
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.open_audio_effects()
            elif modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.cycle_aspect_ratio()
            else:
                self.cycle_audio_track()
            return True
        elif key == Qt.Key.Key_V:
            if (modifiers & Qt.KeyboardModifier.ControlModifier) and (modifiers & Qt.KeyboardModifier.ShiftModifier):
                self.open_subtitle_style()
            elif not (modifiers & Qt.KeyboardModifier.ControlModifier):
                self.cycle_subtitle_track()
            return True
        elif key == Qt.Key.Key_N:
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.toggle_audio_normalizer()
            elif modifiers & Qt.KeyboardModifier.ControlModifier:
                self.open_stream_dialog()
            else:
                self.playlist.play_next()
            return True
        elif key == Qt.Key.Key_P and not (modifiers & Qt.KeyboardModifier.ControlModifier):
            self.playlist.play_previous()
            return True
        elif key == Qt.Key.Key_K and (modifiers & Qt.KeyboardModifier.ControlModifier):
            self.open_video_adjust()
            return True
        elif key == Qt.Key.Key_O and (modifiers & Qt.KeyboardModifier.ControlModifier):
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.open_folder_dialog()
            else:
                self.open_file_dialog()
            return True
        elif key == Qt.Key.Key_E and (modifiers & Qt.KeyboardModifier.ControlModifier):
            self.take_snapshot()
            return True
        elif key == Qt.Key.Key_PageDown:
            self.playlist.play_next()
            return True
        elif key == Qt.Key.Key_PageUp:
            self.playlist.play_previous()
            return True
        elif key == Qt.Key.Key_S:
            if (modifiers & Qt.KeyboardModifier.ControlModifier) and (modifiers & Qt.KeyboardModifier.ShiftModifier):
                self.open_online_subtitles()
            elif modifiers & Qt.KeyboardModifier.ControlModifier:
                self.copy_snapshot_to_clipboard()
            else:
                self.take_snapshot()
            return True
        elif key == Qt.Key.Key_C:
            if (modifiers & Qt.KeyboardModifier.ControlModifier) and (modifiers & Qt.KeyboardModifier.ShiftModifier):
                self.copy_snapshot_to_clipboard()
            else:
                self.adjust_speed(0.1)
            return True
        elif key == Qt.Key.Key_X:
            self.adjust_speed(-0.1)
            return True
        elif key == Qt.Key.Key_Z:
            self.reset_speed()
            return True
        elif key == Qt.Key.Key_R:
            if not (modifiers & Qt.KeyboardModifier.ControlModifier):
                self.cycle_rotation()
            return True
        elif key == Qt.Key.Key_B:
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                if modifiers & Qt.KeyboardModifier.ControlModifier:
                    self.jump_prev_bookmark()
                else:
                    self.jump_next_bookmark()
            elif modifiers & Qt.KeyboardModifier.ControlModifier:
                self.open_bookmark_manager()
            else:
                self.add_bookmark_now()
            return True
        elif key == Qt.Key.Key_G and (modifiers & Qt.KeyboardModifier.ControlModifier):
            self.open_jump_to_time()
            return True
        elif key == Qt.Key.Key_H and (modifiers & Qt.KeyboardModifier.ControlModifier):
            self.toggle_hw_accel()
            return True
        elif key == Qt.Key.Key_J and (modifiers & Qt.KeyboardModifier.ControlModifier):
            self.open_media_info()
            return True
        elif key == Qt.Key.Key_T and (modifiers & Qt.KeyboardModifier.ControlModifier):
            self.toggle_always_on_top(not self.always_on_top)
            return True
        elif key == Qt.Key.Key_Y and (modifiers & Qt.KeyboardModifier.ControlModifier):
            self.open_continue_watching()
            return True
        elif key == Qt.Key.Key_Tab:
            self.toggle_stats_hud()
            return True
        elif key in (Qt.Key.Key_F1, Qt.Key.Key_Question):
            self.open_shortcuts_cheat_sheet()
            return True
        elif key == Qt.Key.Key_F8:
            self.toggle_playlist()
            return True
        elif key == Qt.Key.Key_F11 or (key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (modifiers & Qt.KeyboardModifier.AltModifier)):
            self.toggle_fullscreen()
            return True
        elif key == Qt.Key.Key_1:
            self.set_window_scale(0.5)
            return True
        elif key == Qt.Key.Key_2:
            self.set_window_scale(1.0)
            return True
        elif key == Qt.Key.Key_3:
            self.set_window_scale(1.5)
            return True
        elif key == Qt.Key.Key_4:
            self.set_window_scale(2.0)
            return True
        elif key == Qt.Key.Key_BracketLeft:
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.adjust_sub_delay(-50000)
            else:
                self.set_ab_point_a()
            return True
        elif key == Qt.Key.Key_BracketRight:
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.adjust_sub_delay(50000)
            else:
                self.set_ab_point_b()
            return True
        elif key == Qt.Key.Key_Backslash:
            self.clear_ab_repeat()
            return True
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.adjust_audio_delay(50000)
            return True
        elif key == Qt.Key.Key_Minus:
            self.adjust_audio_delay(-50000)
            return True

        return False

    def on_user_activity(self):
        if self.fullscreen_mode:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.hide_cursor_timer.start()

    def _auto_hide_fullscreen_controls(self):
        if self.fullscreen_mode:
            if hasattr(self, "fs_overlay") and not self.fs_overlay.is_dragging:
                self.fs_overlay.fade_out()
            if self.engine.is_playing():
                self.setCursor(Qt.CursorShape.BlankCursor)

    def _update_playback_ui(self):
        self.engine.check_pending_seek()
        cur_ms = self.engine.get_time()
        tot_ms = self.engine.get_length()

        self.engine.check_ab_loop(cur_ms)

        # Guarantee all floating overlays are hidden when OXPlayer is behind another app
        if QApplication.activeWindow() is None and not self.always_on_top:
            if hasattr(self, "center_play_btn") and self.center_play_btn.isVisible():
                self.center_play_btn.hide_immediate()
            if hasattr(self, "floating_dock") and self.floating_dock.isVisible():
                self.floating_dock.hide_immediate()
            if hasattr(self, "osd") and self.osd.isVisible():
                self.osd.hide()
            if hasattr(self, "seek_tooltip") and self.seek_tooltip.isVisible():
                self.seek_tooltip.hide()

        is_dragging = getattr(self, "is_slider_dragging", False) or (hasattr(self, "floating_dock") and getattr(self.floating_dock, "is_dragging", False))
        if not is_dragging and tot_ms > 0:
            pos = int((cur_ms / tot_ms) * 1000)
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(pos)
            self.seek_slider.blockSignals(False)

        if not is_dragging:
            cur_str = self._format_time(cur_ms)
            tot_str = self._format_time(tot_ms)
            self.cur_time_label.setText(cur_str)
            self.total_time_label.setText(tot_str)
            self.time_label.setText(f"{cur_str} / {tot_str}")
        else:
            cur_str = self.cur_time_label.text()
            tot_str = self.total_time_label.text()

        if self.engine.is_media_loaded():
            cur_sz = self.engine.get_video_size()
            if cur_sz[0] > 0 and cur_sz != getattr(self, "_last_synced_video_size", (0, 0)):
                self._last_synced_video_size = cur_sz
                self.video_widget.sync_child_size()
                if hasattr(self, "pip_window") and self.pip_window.isVisible():
                    self.pip_window.canvas.sync_child_size()

        is_playing = self.engine.is_playing()
        if hasattr(self, "floating_dock"):
            self.floating_dock.update_sync(cur_ms, tot_ms, cur_str, tot_str, is_playing, self.engine.get_volume())

        if hasattr(self, "center_play_btn") and self.center_play_btn.isVisible():
            self.center_play_btn.position_on_player()

        if self.pip_mode and self.pip_window.isVisible():
            self.pip_window.update_status(is_playing, cur_str, self.engine.is_muted())

        # Binge-Watching Next Episode Trigger (Netflix / Crunchyroll style)
        import vlc
        state = self.engine.get_state()
        if getattr(self, "auto_binge_watching", True) and not getattr(self, "_next_episode_cancelled_for_media", False):
            if tot_ms >= 30000:
                rem_ms = tot_ms - cur_ms
                if (rem_ms <= 16000 or state == vlc.State.Ended) and is_playing:
                    if not self._next_episode_prompt_active:
                        next_item = self.playlist.get_next_item() if hasattr(self, "playlist") else None
                        if next_item and hasattr(self, "next_episode_banner"):
                            self._next_episode_prompt_active = True
                            rem_sec = max(3, min(10, rem_ms // 1000))
                            self.next_episode_banner.show_prompt(next_item.title, countdown_sec=rem_sec)
                elif rem_ms > 22000 and self._next_episode_prompt_active:
                    self._next_episode_prompt_active = False
                    if hasattr(self, "next_episode_banner"):
                        self.next_episode_banner.fade_out()

        # Automatic Playback Continuity (Auto-Next / Auto-Repeat) on media completion
        if state == vlc.State.Ended:
            if not self._media_ended_handled:
                self._media_ended_handled = True
                if hasattr(self, "next_episode_banner"):
                    self.next_episode_banner.hide_immediate()
                self._next_episode_prompt_active = False

                if self.playlist.repeat_mode == 2:  # Repeat One (Fix: stop demuxer before restarting)
                    self.engine.stop()
                    self.engine.play()
                    self.engine.set_time(0)
                elif not getattr(self, "_next_episode_cancelled_for_media", False):
                    if hasattr(self, "playlist") and self.playlist.items:
                        self.playlist.play_next()
        elif is_playing and self._media_ended_handled:
            self._media_ended_handled = False

    def _format_time(self, ms: int) -> str:
        sec = max(0, ms // 1000)
        mins, secs = divmod(sec, 60)
        hrs, mins = divmod(mins, 60)
        if hrs > 0:
            return f"{hrs}:{mins:02d}:{secs:02d}"
        return f"{mins}:{secs:02d}"

    # --- Actions ---
    def play_file(self, path: str, start_time_str: str = "", title: str = ""):
        self.current_file_path = path
        self._media_ended_handled = False
        self._next_episode_prompt_active = False
        self._next_episode_cancelled_for_media = False
        if hasattr(self, "next_episode_banner"):
            self.next_episode_banner.hide_immediate()
        base_name = title or os.path.basename(path) or path
        self.add_to_recent_files(path)

        # Synchronize playlist index and auto-queue folder siblings if enabled
        if hasattr(self, "playlist"):
            if getattr(self, "auto_queue_folder", True) and os.path.isfile(path):
                self.playlist.queue_folder_siblings(path)
            else:
                self.playlist.sync_playing_path(path)

        self.engine.load_media(path)
        self.engine.play()
        if hasattr(self, "stats_hud") and self.stats_hud.isVisible():
            self.stats_hud.refresh_stats()
        if hasattr(self, "center_play_btn"):
            self.center_play_btn.flash("play", 2000)
        self.setWindowTitle(f"{base_name} - OXPlayer")

        # Sync child window size to ensure immediate fill
        QTimer.singleShot(100, self.video_widget.sync_child_size)
        QTimer.singleShot(350, self.video_widget.sync_child_size)

        self._auto_discover_subtitle(path)

        # Check explicit start_time_str first (CLI or URL argument)
        if start_time_str:
            target_ms = parse_timestamp_to_ms(start_time_str)
            if target_ms is not None:
                self.engine.set_time(target_ms)
                self.osd.show_message(f"Mulai dari: {self._format_time(target_ms)}")
                return

        # Check intentional fixed custom start time (set via JumpToTimeDialog)
        custom_ms = self.engine.get_custom_start_time(path)
        if custom_ms is not None and custom_ms > 0:
            self.engine.set_time(custom_ms)
            self.osd.show_message(f"Mulai dari: {self._format_time(custom_ms)}")
            return

        # Optional VLC-style Resume from previous playback history
        saved_ms = self.engine.get_resume_position(path)
        if saved_ms and saved_ms > 3000:
            res_mode = self.engine.config_data.get("resume_mode", "ask")
            time_str = self._format_time(saved_ms)
            if res_mode == "always":
                self.engine.set_time(saved_ms)
                self.osd.show_message(f"Melanjutkan dari: {time_str}")
            elif res_mode == "ask":
                # Start video playback from beginning and display interactive prompt banner
                self.resume_banner.show_prompt(saved_ms, time_str)
                self._show_playback_start_osd(base_name, path)
            else:
                # 'never' -> play from start without prompting
                self._show_playback_start_osd(base_name, path)
        else:
            self._show_playback_start_osd(base_name, path)

    def _show_playback_start_osd(self, base_name: str, path: str):
        self.osd.show_message(f"Memutar: {base_name}")

    def _on_resume_banner_confirmed(self, target_ms: int):
        self.engine.set_time(target_ms)
        self.osd.show_message(f"Melanjutkan dari: {self._format_time(target_ms)}")
        self.resume_banner.fade_out()

    def _on_resume_banner_restart(self):
        self.engine.set_time(0)
        self.osd.show_message("Memutar dari Awal")
        self.resume_banner.fade_out()

    def _on_next_episode_confirmed(self):
        self._next_episode_prompt_active = False
        if hasattr(self, "playlist") and self.playlist.items:
            self.playlist.play_next()

    def _on_next_episode_cancelled(self):
        self._next_episode_prompt_active = False
        self._next_episode_cancelled_for_media = True
        self.osd.show_message("Auto-Play Dibatalkan (Tetap Menonton)")

    def toggle_binge_watching(self, checked: bool):
        self.auto_binge_watching = checked
        self.engine.config_data["auto_binge_watching"] = checked
        self.engine.save_config()
        if hasattr(self, "binge_act"):
            self.binge_act.setChecked(checked)
        if not checked and hasattr(self, "next_episode_banner"):
            self.next_episode_banner.fade_out()
        status = "Aktif" if checked else "Nonaktif"
        self.osd.show_message(f"Binge-Watching Otomatis: {status}")

    def set_resume_mode(self, mode: str):
        self.engine.config_data["resume_mode"] = mode
        self.engine.save_config()
        labels = {
            "ask": "Tanya Sebelum Melanjutkan (Seperti VLC)",
            "always": "Selalu Lanjutkan Otomatis",
            "never": "Jangan Pernah Lanjutkan (Mulai dari Awal)"
        }
        self.osd.show_message(f"Lanjut Menonton: {labels.get(mode, mode)}")

    def _auto_discover_subtitle(self, video_path: str):
        if not video_path or not os.path.exists(video_path):
            return
        folder = os.path.dirname(os.path.abspath(video_path))
        base_no_ext, _ = os.path.splitext(os.path.abspath(video_path))

        # 1. Fast direct path check (<0.1ms without folder scanning)
        direct_suffixes = [
            ".srt", ".ass", ".vtt", ".sub",
            ".id.srt", ".ind.srt", ".en.srt", ".eng.srt",
            ".id.ass", ".ind.ass", ".en.ass", ".eng.ass"
        ]
        for suffix in direct_suffixes:
            candidate = base_no_ext + suffix
            if os.path.isfile(candidate):
                self.engine.add_subtitle_file(candidate)
                self.osd.show_message(f"Subtitle otomatis: {os.path.basename(candidate)}")
                return

        # 2. Heuristic scan if no exact matching name found
        base_name_lower = os.path.splitext(os.path.basename(video_path))[0].lower()
        sub_exts = {".srt", ".ass", ".vtt", ".sub"}
        try:
            with os.scandir(folder) as it:
                for entry in it:
                    if entry.is_file():
                        f_lower = entry.name.lower()
                        ext = os.path.splitext(f_lower)[1]
                        if ext in sub_exts and base_name_lower in f_lower:
                            self.engine.add_subtitle_file(entry.path)
                            self.osd.show_message(f"Subtitle otomatis: {entry.name}")
                            break
        except Exception:
            pass

    def toggle_play_pause(self):
        if self.engine.is_playing():
            self.engine.pause()
            self.osd.show_message("Jeda (Paused)")
            if hasattr(self, "center_play_btn"):
                self.center_play_btn.flash("pause", 2000)
            if hasattr(self, "floating_dock"):
                self.floating_dock.set_playing(False)
        else:
            self.engine.play()
            self.osd.show_message("Memutar (Playing)")
            if hasattr(self, "center_play_btn"):
                self.center_play_btn.flash("play", 2000)
            if hasattr(self, "floating_dock"):
                self.floating_dock.set_playing(True)

    def stop(self):
        self.engine.stop()
        self.seek_slider.setValue(0)
        self.time_label.setText("0:00 / 0:00")
        if hasattr(self, "center_play_btn"):
            self.center_play_btn.flash("pause", 2000)
        if hasattr(self, "floating_dock"):
            self.floating_dock.set_playing(False)
        self.osd.show_message("Berhenti (Stopped)")

    def close_media(self):
        self.engine.stop()
        self.engine.current_mrl = None
        self.engine.current_media = None
        self.seek_slider.setValue(0)
        self.time_label.setText("0:00 / 0:00")
        if hasattr(self, "center_play_btn"):
            self.center_play_btn.hide_immediate()
        if hasattr(self, "floating_dock"):
            self.floating_dock.seek_slider.setValue(0)
            self.floating_dock.time_label.setText("0:00 / 0:00")
            self.floating_dock.set_playing(False)
        self.setWindowTitle("OXPlayer")
        self.osd.show_message("Media Ditutup")

    def frame_step(self):
        self.engine.frame_step()
        self.osd.show_message("Langkah Frame (Frame Step)")

    def adjust_volume(self, delta: int):
        new_vol = max(0, min(250, self.vol_slider.value() + delta))
        self.vol_slider.setValue(new_vol)

    def _on_volume_changed(self, val: int):
        self.engine.set_volume(val)
        self.osd.show_message(f"Volume: {val}%")

    def toggle_mute(self):
        muted = self.engine.toggle_mute()
        self.vol_btn.setText("Mute" if muted else "Vol")
        self.osd.show_message("Volume: Bisu (Muted)" if muted else f"Volume: {self.vol_slider.value()}%")

    def toggle_hw_accel(self):
        new_state = self.engine.toggle_hw_accel()
        if hasattr(self, "floating_dock"):
            self.floating_dock.update_hw_btn(new_state)
        if hasattr(self, "hw_menu_act"):
            self.hw_menu_act.setChecked(new_state)
        if hasattr(self, "hw_context_act"):
            self.hw_context_act.setChecked(new_state)
        mode_str = "Hardware (GPU)" if new_state else "Software (CPU)"
        self.osd.show_message(f"Decoding: {mode_str}")

    def toggle_crystal_clear(self):
        new_state = not self.engine.crystal_clear_enabled
        self.engine.set_crystal_clear_audio(new_state)
        self.osd.show_message(f"Penjernih Vokal: {'Aktif' if new_state else 'Nonaktif'}")

    def toggle_audio_normalizer(self):
        new_state = not self.engine.normalizer_enabled
        self.engine.set_audio_normalizer(new_state)
        self.osd.show_message(f"Audio Normalizer: {'Aktif' if new_state else 'Nonaktif'}")

    def _set_surround_mode(self, code: str, name: str):
        self.engine.set_surround_mode(code)
        self.osd.show_message(f"Tata Suara: {name}")

    def adjust_speed(self, delta: float):
        cur = self.engine.get_rate()
        new_rate = round(cur + delta, 2)
        self.engine.set_rate(new_rate)
        actual = self.engine.get_rate()
        self.speed_btn.setText(f"{actual:.1f}x")
        self.osd.show_message(f"Kecepatan: {actual:.2f}x")

    def reset_speed(self):
        self.engine.set_rate(1.0)
        self.speed_btn.setText("1.0x")
        self.osd.show_message("Kecepatan: 1.00x (Normal)")

    def seek_relative(self, delta_ms: int):
        if not self.engine.is_media_loaded():
            return
        self.engine.seek_relative(delta_ms)
        sign = "+" if delta_ms > 0 else ""
        cur_time_str = self._format_time(self.engine.get_time())
        self.osd.show_message(f"Lompat: {sign}{delta_ms // 1000}s ({cur_time_str})")

    def adjust_audio_delay(self, delta_us: int):
        cur = self.engine.get_audio_delay()
        target = cur + delta_us
        self.engine.set_audio_delay(target)
        self.osd.show_message(f"Audio Delay: {target // 1000} ms")

    def adjust_sub_delay(self, delta_us: int):
        cur = self.engine.get_subtitle_delay()
        target = cur + delta_us
        self.engine.set_subtitle_delay(target)
        self.osd.show_message(f"Subtitle Delay: {target // 1000} ms")

    # --- Video Rotation & Flip Actions ---
    def cycle_rotation(self):
        ang = self.engine.cycle_rotation()
        self.video_widget.sync_child_size()
        if hasattr(self, "pip_window") and self.pip_window.isVisible():
            self.pip_window.canvas.sync_child_size()
        self.osd.show_message(f"Rotasi Video: {ang}°")

    def set_rotation_angle(self, angle: int):
        self.engine.set_rotation(angle)
        self.video_widget.sync_child_size()
        if hasattr(self, "pip_window") and self.pip_window.isVisible():
            self.pip_window.canvas.sync_child_size()
        self.osd.show_message(f"Rotasi Video: {angle}°")

    def set_flip_mode(self, mode: str):
        self.engine.set_flip(mode)
        mode_names = {"hflip": "Balik Horizontal (Mirror)", "vflip": "Balik Vertikal", "none": "Normal"}
        self.osd.show_message(f"Cermin Video: {mode_names.get(mode, mode)}")

    # --- Bookmark Actions ---
    def add_bookmark_now(self):
        bm = self.engine.add_bookmark()
        if bm:
            self.osd.show_message(f"Bookmark Ditambahkan: {bm.get('label')}")

    def jump_next_bookmark(self):
        ms = self.engine.jump_next_bookmark()
        if ms is not None:
            self.osd.show_message(f"Lompat Bookmark: {self._format_time(ms)}")

    def jump_prev_bookmark(self):
        ms = self.engine.jump_prev_bookmark()
        if ms is not None:
            self.osd.show_message(f"Lompat Bookmark: {self._format_time(ms)}")

    def open_bookmark_manager(self):
        self._hide_overlays_for_dialog()
        dlg = BookmarkManagerDialog(self.engine, osd_callback=self.osd.show_message, parent=self)
        dlg.exec()

    # --- Jump to Time Dialog ---
    def open_jump_to_time(self):
        self._hide_overlays_for_dialog()
        dlg = JumpToTimeDialog(self.engine, osd_callback=self.osd.show_message, parent=self)
        dlg.exec()

    # --- Shortcuts Cheat Sheet Dialog ---
    def open_shortcuts_cheat_sheet(self):
        self._hide_overlays_for_dialog()
        dlg = ShortcutsCheatSheetDialog(parent=self)
        dlg.exec()

    # --- A-B Repeat Controls ---
    def set_ab_point_a(self):
        self.engine.set_ab_point_a()
        t_str = self._format_time(self.engine.ab_a_ms)
        self.osd.show_message(f"A-B Loop: Titik A diset pada {t_str}")

    def set_ab_point_b(self):
        if self.engine.ab_a_ms is None:
            self.set_ab_point_a()
            return
        self.engine.set_ab_point_b()
        t_str = self._format_time(self.engine.ab_b_ms)
        self.osd.show_message(f"A-B Loop: Titik B diset pada {t_str} (Looping)")

    def clear_ab_repeat(self):
        self.engine.clear_ab_repeat()
        self.osd.show_message("A-B Loop: Direset")

    def _refresh_ratio_menu(self):
        if not hasattr(self, "ratio_menu"):
            return
        self.ratio_menu.clear()
        cur_ratio = getattr(self, "current_aspect_ratio_val", "")
        for r_name, r_val in [("Default / Otomatis", ""), ("16:9 (Widescreen)", "16:9"), ("4:3 (Klasik)", "4:3"),
                              ("2.35:1 (Cinemascope)", "2.35:1"), ("21:9 (Ultrawide)", "21:9"), ("1:1 (Square)", "1:1"),
                              ("Penuhi Jendela (Stretch)", "stretch")]:
            is_active = (r_val == cur_ratio)
            act = self.ratio_menu.addAction(f"✓  {r_name}" if is_active else f"    {r_name}")
            act.triggered.connect(lambda chk, v=r_val, n=r_name: self.set_aspect_ratio(v, n))

    def set_aspect_ratio(self, ratio_val: str, ratio_name: str):
        self.current_aspect_ratio_val = ratio_val
        self.engine.set_aspect_ratio(ratio_val)
        self.video_widget.sync_child_size()
        if hasattr(self, "pip_window") and self.pip_window.isVisible():
            self.pip_window.canvas.sync_child_size()
        self._refresh_ratio_menu()
        self.osd.show_message(f"Rasio Aspek: {ratio_name}")

    def cycle_aspect_ratio(self):
        ratios = [
            ("", "Default (Asli)"),
            ("16:9", "16:9 (Layar Lebar)"),
            ("4:3", "4:3 (Standar TV)"),
            ("2.35:1", "2.35:1 (Sinema Lebar)"),
            ("21:9", "21:9 (Ultrawide)"),
            ("1:1", "1:1 (Kotak)"),
            ("stretch", "Penuhi Jendela (Stretch)")
        ]
        cur = getattr(self, "_current_aspect_idx", 0)
        next_idx = (cur + 1) % len(ratios)
        self._current_aspect_idx = next_idx
        val, name = ratios[next_idx]
        self.set_aspect_ratio(val, name)

    def take_snapshot(self):
        pictures_dir = os.path.expanduser("~/Pictures")
        if not os.path.exists(pictures_dir):
            pictures_dir = os.path.expanduser("~")
        filename = f"Snapshot_{QDateTime.currentDateTime().toString('yyyyMMdd_hhmmss_zzz')}.png"
        save_path = os.path.join(pictures_dir, filename)
        success = self.engine.take_snapshot(save_path)
        if success:
            self.osd.show_message(f"Snapshot disimpan: {filename}")
        else:
            self.osd.show_message("Gagal mengambil snapshot")

    def copy_snapshot_to_clipboard(self):
        import tempfile
        from PyQt6.QtGui import QImage
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            temp_path = tf.name
        try:
            success = self.engine.take_snapshot(temp_path)
            if success:
                # LibVLC writes PNG snapshots asynchronously; wait up to 500ms for flush
                for _ in range(10):
                    if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                        break
                    time.sleep(0.05)
            if success and os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                img = QImage(temp_path)
                if not img.isNull():
                    QApplication.clipboard().setImage(img)
                    self.osd.show_message("Snapshot disalin ke clipboard!")
                else:
                    self.osd.show_message("Gagal memproses snapshot")
            else:
                self.osd.show_message("Gagal mengambil snapshot")
        except Exception as e:
            self.osd.show_message(f"Error clipboard: {e}")
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def cycle_audio_track(self):
        track_name = self.engine.cycle_audio_track()
        self.osd.show_message(f"Audio Track: {track_name}")

    def cycle_subtitle_track(self):
        sub_name = self.engine.cycle_subtitle_track()
        self.osd.show_message(f"Subtitle: {sub_name}")

    def toggle_auto_pause_on_minimize(self, checked: bool):
        self.auto_pause_on_minimize = checked
        self.engine.config_data["auto_pause_on_minimize"] = checked
        self.engine.save_config()
        status = "Aktif" if checked else "Nonaktif"
        self.osd.show_message(f"Jeda Otomatis Saat Diminimalkan: {status}")

    def toggle_auto_queue_folder(self, checked: bool):
        self.auto_queue_folder = checked
        self.engine.config_data["auto_queue_folder"] = checked
        self.engine.save_config()
        if hasattr(self, "auto_queue_act"):
            self.auto_queue_act.setChecked(checked)
        if checked and self.current_file_path and os.path.isfile(self.current_file_path):
            count = self.playlist.queue_folder_siblings(self.current_file_path)
            self.osd.show_message(f"Auto-Play Episode Berikutnya: Aktif ({count} berkas sefolder)")
        else:
            status = "Aktif" if checked else "Nonaktif"
            self.osd.show_message(f"Auto-Play Episode Berikutnya (Sefolder): {status}")

    def toggle_stats_hud(self, checked: bool = None):
        if not hasattr(self, "stats_hud"):
            return
        active = self.stats_hud.toggle_hud()
        if hasattr(self, "stats_hud_act"):
            self.stats_hud_act.blockSignals(True)
            self.stats_hud_act.setChecked(active)
            self.stats_hud_act.blockSignals(False)
        self.osd.show_message("Informasi Teknis: Aktif (Tab)" if active else "Informasi Teknis: Nonaktif")

    # --- Continue Watching Dashboard ---
    def open_continue_watching(self):
        self._hide_overlays_for_dialog()
        dlg = ContinueWatchingDialog(
            self.engine,
            on_play_callback=self._on_continue_watching_play,
            parent=self
        )
        dlg.exec()

    def _on_continue_watching_play(self, mrl: str, pos_ms: int):
        if os.path.exists(mrl) or mrl.startswith(("http://", "https://", "rtsp://")):
            self.play_file(mrl)
            if pos_ms > 0:
                self.engine.set_time(pos_ms)
            self.osd.show_message(f"Melanjutkan: {os.path.basename(mrl)}")
        else:
            self.osd.show_message("Berkas tidak ditemukan di penyimpanan lokal")

    # --- Fullscreen Mode ---
    def toggle_fullscreen(self):
        if self.fullscreen_mode or self.isFullScreen():
            self.showNormal()
            self.fullscreen_mode = False
            self.menuBar().show()
            self.floating_dock.update_fs_icon(False)
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.hide_cursor_timer.stop()
            self.video_widget.sync_child_size()
            QTimer.singleShot(80, self.video_widget.sync_child_size)
            QTimer.singleShot(250, self.video_widget.sync_child_size)
            self.floating_dock.position_on_player()
            self.center_play_btn.position_on_player()
            self.osd.show_message("Jendela Normal")
        else:
            if self.pip_mode:
                self.exit_pip_mode()
            self.showFullScreen()
            self.fullscreen_mode = True
            self.menuBar().hide()
            self.floating_dock.update_fs_icon(True)
            self.hide_cursor_timer.start()
            self.video_widget.sync_child_size()
            QTimer.singleShot(80, self.video_widget.sync_child_size)
            QTimer.singleShot(250, self.video_widget.sync_child_size)
            self.floating_dock.position_on_player()
            self.center_play_btn.position_on_player()
            self.osd.show_message("Layar Penuh (Esc untuk keluar)")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.video_widget.sync_child_size()
        if hasattr(self, "floating_dock"):
            self.floating_dock.position_on_player()
        if hasattr(self, "center_play_btn"):
            self.center_play_btn.position_on_player()
        if hasattr(self, "osd") and self.osd.isVisible():
            self.osd.position_on_player()
        if hasattr(self, "stats_hud") and self.stats_hud.isVisible():
            self.stats_hud.position_on_player()

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, "floating_dock"):
            self.floating_dock.position_on_player()
        if hasattr(self, "center_play_btn"):
            self.center_play_btn.position_on_player()
        if hasattr(self, "osd") and self.osd.isVisible():
            self.osd.position_on_player()
        if hasattr(self, "stats_hud") and self.stats_hud.isVisible():
            self.stats_hud.position_on_player()
        if hasattr(self, "resume_banner") and self.resume_banner.isVisible():
            self.resume_banner.reposition()
        if hasattr(self, "next_episode_banner") and self.next_episode_banner.isVisible():
            self.next_episode_banner.reposition()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                if getattr(self, "auto_pause_on_minimize", False) and self.engine.is_playing():
                    self._was_playing_before_minimize = True
                    self.engine.pause()
            else:
                if getattr(self, "auto_pause_on_minimize", False) and getattr(self, "_was_playing_before_minimize", False):
                    self._was_playing_before_minimize = False
                    if not self.engine.is_playing():
                        self.engine.play()
            QTimer.singleShot(80, self.video_widget.sync_child_size)
            QTimer.singleShot(250, self.video_widget.sync_child_size)
            if hasattr(self, "floating_dock"):
                if self.isMinimized():
                    self.floating_dock.hide_immediate()
                else:
                    self.floating_dock.position_on_player()
            if hasattr(self, "center_play_btn"):
                if self.isMinimized() or not self.engine.is_media_loaded():
                    self.center_play_btn.hide_immediate()
                else:
                    self.center_play_btn.position_on_player()
            if hasattr(self, "osd"):
                if self.isMinimized():
                    self.osd.hide()
                elif self.osd.isVisible():
                    self.osd.position_on_player()
            if hasattr(self, "stats_hud"):
                if self.isMinimized():
                    self.stats_hud.hide()
                elif self.stats_hud.hud_active:
                    self.stats_hud.show()
                    self.stats_hud.position_on_player()
        elif event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow() and not self.always_on_top:
                if hasattr(self, "center_play_btn"):
                    self.center_play_btn.hide_immediate()
                if hasattr(self, "floating_dock"):
                    self.floating_dock.hide_immediate()
                if hasattr(self, "osd"):
                    self.osd.hide()
                if hasattr(self, "seek_tooltip"):
                    self.seek_tooltip.hide()
            elif self.isActiveWindow():
                if hasattr(self, "floating_dock") and not self.pip_mode and not self.isMinimized():
                    self.floating_dock.position_on_player()
                    self.floating_dock.fade_in()
                if hasattr(self, "stats_hud") and self.stats_hud.hud_active and not self.pip_mode and not self.isMinimized():
                    self.stats_hud.position_on_player()
                    self.stats_hud.show()

    # --- True Picture-in-Picture (PiP) Mode ---
    def toggle_pip_mode(self):
        if self.pip_mode:
            self.exit_pip_mode()
        else:
            self.enter_pip_mode()

    def enter_pip_mode(self):
        if not self.engine.is_media_loaded():
            self.osd.show_message("Tidak ada media untuk PiP")
            return

        self.was_maximized_before_pip = self.isMaximized()

        if self.fullscreen_mode:
            self.toggle_fullscreen()

        self.pip_mode = True

        # 1. Position and show PiP window on current active monitor first so HWND is valid
        current_screen = self.screen() or QApplication.primaryScreen()
        screen = current_screen.geometry()
        w, h = 440, 248
        self.pip_window.setGeometry(screen.x() + screen.width() - w - 30, screen.y() + screen.height() - h - 60, w, h)
        self.pip_window.show()
        self.pip_window.raise_()
        self.pip_window.activateWindow()
        QApplication.processEvents()

        # 2. Transfer LibVLC Direct3D output to PiP canvas HWND
        self.engine.switch_video_hwnd(int(self.pip_window.canvas.winId()))
        self.pip_window.canvas.sync_child_size()
        QTimer.singleShot(100, self.pip_window.canvas.sync_child_size)
        QTimer.singleShot(300, self.pip_window.canvas.sync_child_size)

        # 3. Minimize main window
        if hasattr(self, "osd"):
            self.osd.hide()
        if hasattr(self, "stats_hud"):
            self.stats_hud.hide()
        self.showMinimized()

    def exit_pip_mode(self):
        self.pip_mode = False
        self.pip_window.hide()

        # 1. Restore and display main window first so video_widget HWND is active and visible
        if getattr(self, "was_maximized_before_pip", False):
            self.showMaximized()
        else:
            self.showNormal()
        self.raise_()
        self.activateWindow()
        QApplication.processEvents()

        # 2. Transfer LibVLC Direct3D output back to main video widget
        self.engine.switch_video_hwnd(int(self.video_widget.winId()))
        self.video_widget.sync_child_size()
        QTimer.singleShot(100, self.video_widget.sync_child_size)
        QTimer.singleShot(300, self.video_widget.sync_child_size)

        self.osd.show_message("Kembali ke Pemutar Utama")

    def toggle_always_on_top(self, checked: bool = None):
        if checked is None:
            checked = not self.always_on_top
        self.always_on_top = checked
        if hasattr(self, "ontop_act"):
            self.ontop_act.blockSignals(True)
            self.ontop_act.setChecked(checked)
            self.ontop_act.blockSignals(False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
        self.show()
        if sys.platform.startswith("win") and user32:
            try:
                hwnd = int(self.winId())
                target_z = HWND_TOPMOST if checked else HWND_NOTOPMOST
                user32.SetWindowPos(hwnd, target_z, 0, 0, 0, 0, 0x0013)  # SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            except Exception:
                pass
        self.video_widget.sync_child_size()
        QTimer.singleShot(50, self.video_widget.sync_child_size)
        self.osd.show_message("Selalu di Atas: Aktif" if checked else "Selalu di Atas: Nonaktif")

    def toggle_playlist(self):
        if self.playlist.isVisible():
            self.playlist.hide()
        else:
            self.playlist.show()

    # --- Window Scaling (50%, 100%, 150%, 200%) ---
    def set_window_scale(self, factor: float):
        if self.fullscreen_mode or self.isFullScreen():
            self.toggle_fullscreen()
        vw, vh = 0, 0
        if self.engine.is_media_loaded():
            vw, vh = self.engine.get_video_size()
        if vw <= 0 or vh <= 0:
            vw, vh = 1280, 720
        target_w = int(vw * factor)
        target_h = int(vh * factor)
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            target_w = max(640, min(target_w, avail.width() - 40))
            target_h = max(420, min(target_h, avail.height() - 60))
            self.resize(target_w, target_h)
            new_x = avail.x() + (avail.width() - target_w) // 2
            new_y = avail.y() + (avail.height() - target_h) // 2
            self.move(new_x, new_y)
        else:
            self.resize(target_w, target_h)
        self.osd.show_message(f"Ukuran Jendela: {int(factor * 100)}%")

    # --- Sliders Seeking ---
    def _on_seek_pressed(self):
        if hasattr(self, "floating_dock"):
            self.floating_dock._on_seek_pressed()
        else:
            self.is_slider_dragging = True

    def _on_seek_released(self):
        if hasattr(self, "floating_dock"):
            self.floating_dock._on_seek_released()
        else:
            self.is_slider_dragging = False
            target_pos = self.seek_slider.value() / 1000.0
            self.engine.set_position(target_pos)

    def _on_seek_moved(self, val: int):
        if hasattr(self, "floating_dock"):
            self.floating_dock._on_seek_moved(val)
        elif self.is_slider_dragging:
            tot_ms = self.engine.get_length()
            cur_ms = int((val / 1000.0) * tot_ms)
            self.time_label.setText(f"{self._format_time(cur_ms)} / {self._format_time(tot_ms)}")

    # --- Dialog Openers ---
    def _hide_overlays_for_dialog(self):
        if hasattr(self, "center_play_btn"):
            self.center_play_btn.hide_immediate()
        if hasattr(self, "floating_dock"):
            self.floating_dock.hide_immediate()

    def open_file_dialog(self):
        self._hide_overlays_for_dialog()
        all_ext_filter = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_MEDIA_EXTENSIONS))
        filter_str = (
            f"Semua Format OXPlayer ({all_ext_filter});;"
            "Video Modern & HD (*.mp4 *.mkv *.webm *.m4v *.mov *.ts *.mts *.m2ts);;"
            "Video Broadcast & DVD (*.vob *.mpg *.mpeg *.m2v *.wtv *.dvr-ms *.evo *.tp *.trp);;"
            "Video Klasik & Web (*.avi *.divx *.xvid *.wmv *.asf *.flv *.f4v *.rm *.rmvb *.3gp *.3g2 *.ogv);;"
            "Audio Spasial & Lossless (*.flac *.alac *.wav *.ape *.wv *.ac3 *.eac3 *.dts *.dtshd *.thd *.aiff);;"
            "Audio Musik (*.mp3 *.aac *.m4a *.opus *.ogg *.wma *.mpc *.mid);;"
            "Daftar Putar (*.m3u *.m3u8 *.pls *.xspf);;"
            "All Files (*.*)"
        )
        files, _ = QFileDialog.getOpenFileNames(self, "Buka File Media", "", filter_str)
        if files:
            if len(files) > 1 or not getattr(self, "auto_queue_folder", True):
                self.playlist.add_paths(files, auto_play=False)
            self.play_file(files[0])

    def open_folder_dialog(self):
        self._hide_overlays_for_dialog()
        folder = QFileDialog.getExistingDirectory(self, "Buka Folder Media")
        if folder:
            prev_len = len(self.playlist.items)
            self.playlist.add_paths([folder], auto_play=False)
            if len(self.playlist.items) > prev_len:
                self.playlist.play_index(prev_len)

    def open_stream_dialog(self):
        self._hide_overlays_for_dialog()
        dlg = OpenStreamDialog(self)
        if dlg.exec() == OpenStreamDialog.DialogCode.Accepted and dlg.url:
            title = getattr(dlg, "media_title", "")
            self.playlist.add_paths([dlg.url], auto_play=False)
            self.play_file(dlg.url, title=title)

    def open_online_subtitles(self):
        self._hide_overlays_for_dialog()
        dlg = OnlineSubtitlesDialog(
            self.engine,
            current_path=self.current_file_path,
            on_sub_loaded=lambda path, ok: self.osd.show_message("Subtitle online berhasil dimuat!" if ok else "Gagal memuat subtitle"),
            parent=self
        )
        dlg.exec()

    def load_subtitle_file(self):
        self._hide_overlays_for_dialog()
        sub_path, _ = QFileDialog.getOpenFileName(
            self, "Muat Subtitle", "", "Subtitles (*.srt *.ass *.vtt *.sub);;All Files (*.*)"
        )
        if sub_path:
            success = self.engine.add_subtitle_file(sub_path)
            self.osd.show_message("Subtitle dimuat" if success else "Gagal memuat subtitle")

    def open_subtitle_style(self):
        self._hide_overlays_for_dialog()
        dlg = SubtitleStyleDialog(osd_callback=self.osd.show_message, parent=self)
        dlg.exec()

    def open_audio_effects(self):
        self._hide_overlays_for_dialog()
        dlg = AudioEffectsDialog(self.engine, osd_callback=self.osd.show_message, parent=self)
        dlg.exec()

    def open_video_adjust(self):
        self._hide_overlays_for_dialog()
        dlg = VideoAdjustDialog(self.engine, osd_callback=self.osd.show_message, parent=self)
        dlg.exec()

    def open_media_info(self):
        self._hide_overlays_for_dialog()
        dlg = MediaInfoDialog(self.engine, parent=self)
        dlg.exec()

    # --- Tracks sub-menus ---
    def _populate_audio_tracks(self):
        self.audio_track_menu.clear()
        tracks = self.engine.get_audio_tracks()
        if not tracks:
            act = self.audio_track_menu.addAction("Tidak ada track audio")
            act.setEnabled(False)
            return
        for tid, name in tracks:
            act = self.audio_track_menu.addAction(name)
            act.triggered.connect(lambda chk, t=tid, n=name: self._set_audio_track(t, n))

    def _set_audio_track(self, tid: int, name: str):
        self.engine.set_audio_track(tid)
        self.osd.show_message(f"Audio: {name}")

    def _populate_sub_tracks(self):
        self.sub_track_menu.clear()
        tracks = self.engine.get_subtitle_tracks()
        if not tracks:
            act = self.sub_track_menu.addAction("Tidak ada subtitle")
            act.setEnabled(False)
            return
        for sid, name in tracks:
            act = self.sub_track_menu.addAction(name)
            act.triggered.connect(lambda chk, s=sid, n=name: self._set_sub_track(s, n))

    def _set_sub_track(self, sid: int, name: str):
        self.engine.set_subtitle_track(sid)
        self.osd.show_message(f"Subtitle: {name}")

    def _set_speed_exact(self, speed: float):
        self.engine.set_rate(speed)
        self.speed_btn.setText(f"{speed:.2f}x" if speed != 1.0 else "1.0x")
        self.osd.show_message(f"Kecepatan: {speed:.2f}x")

    def _populate_audio_tracks_menu(self, menu: QMenu):
        menu.clear()
        tracks = self.engine.get_audio_tracks()
        if not tracks:
            act = menu.addAction("Default")
            act.setEnabled(False)
            return
        for tid, name in tracks:
            act = menu.addAction(name)
            act.triggered.connect(lambda chk, t=tid, n=name: self._set_audio_track(t, n))

    def _populate_sub_tracks_menu(self, menu: QMenu):
        menu.clear()
        tracks = self.engine.get_subtitle_tracks()
        if not tracks:
            act = menu.addAction("Tidak ada subtitle")
            act.setEnabled(False)
            return
        for sid, name in tracks:
            act = menu.addAction(name)
            act.triggered.connect(lambda chk, s=sid, n=name: self._set_sub_track(s, n))

    # --- Context Menu (Comprehensive VLC-Style Hierarchy) ---
    def show_context_menu(self, pos: QPoint, is_global: bool = False):
        target_pos = pos if is_global else self.video_widget.mapToGlobal(pos)
        menu = QMenu(self)

        # 1. Media Submenu
        media_menu = menu.addMenu("Media")
        act = media_menu.addAction("Buka Berkas Media...")
        act.setShortcut(QKeySequence("Ctrl+O"))
        act.triggered.connect(self.open_file_dialog)
        act = media_menu.addAction("Buka Folder Media...")
        act.triggered.connect(self.playlist._open_add_folder_dialog)
        act = media_menu.addAction("Buka Network Stream / URL...")
        act.setShortcut(QKeySequence("Ctrl+U"))
        act.triggered.connect(self.open_stream_dialog)

        recent_sub = media_menu.addMenu("Riwayat Berkas Terakhir")
        if not self.recent_files:
            empty_act = recent_sub.addAction("Riwayat Kosong")
            empty_act.setEnabled(False)
        else:
            for rf in self.recent_files[:10]:
                r_act = recent_sub.addAction(os.path.basename(rf))
                r_act.triggered.connect(lambda chk, f=rf: self.play_file(f))
            recent_sub.addSeparator()
            clr_act = recent_sub.addAction("Hapus Semua Riwayat")
            clr_act.triggered.connect(self.clear_recent_files)

        menu.addSeparator()

        # 2. Pemutaran / Playback Submenu
        play_menu = menu.addMenu("Pemutaran")
        p_act = play_menu.addAction("Jeda" if self.engine.is_playing() else "Putar")
        p_act.setShortcut(QKeySequence("Space"))
        p_act.triggered.connect(self.toggle_play_pause)

        s_act = play_menu.addAction("Hentikan (Stop)")
        s_act.triggered.connect(self.stop)

        play_menu.addSeparator()
        rew_act = play_menu.addAction("Mundur 10 Detik")
        rew_act.setShortcut(QKeySequence("Left"))
        rew_act.triggered.connect(lambda: self.seek_relative(-10000))

        fwd_act = play_menu.addAction("Maju 10 Detik")
        fwd_act.setShortcut(QKeySequence("Right"))
        fwd_act.triggered.connect(lambda: self.seek_relative(10000))

        step_act = play_menu.addAction("Langkah Frame (Frame Step)")
        step_act.setShortcut(QKeySequence("F"))
        step_act.triggered.connect(self.frame_step)

        jump_act = play_menu.addAction("Lompat ke Waktu Spesifik...")
        jump_act.setShortcut(QKeySequence("Ctrl+G"))
        jump_act.triggered.connect(self.open_jump_to_time)

        play_menu.addSeparator()
        speed_sub = play_menu.addMenu("Kecepatan Putar")
        for sp_val, sp_lbl in [(0.25, "0.25x (Sangat Lambat)"), (0.5, "0.50x (Lambat)"),
                               (0.75, "0.75x"), (1.0, "1.00x (Normal)"),
                               (1.25, "1.25x"), (1.5, "1.50x (Cepat)"), (2.0, "2.00x (Ganda)")]:
            act = speed_sub.addAction(sp_lbl)
            act.triggered.connect(lambda chk, s=sp_val: self._set_speed_exact(s))

        ab_sub = play_menu.addMenu("Mode Loop A-B")
        ab_sub.addAction("Set Titik A ([)").triggered.connect(self.set_ab_point_a)
        ab_sub.addAction("Set Titik B (])").triggered.connect(self.set_ab_point_b)
        ab_sub.addAction("Reset Loop (\\)").triggered.connect(self.clear_ab_repeat)

        bm_sub = play_menu.addMenu("Penanda Bookmark")
        bm_sub.addAction("Tambah Penanda Saat Ini (B)").triggered.connect(self.add_bookmark_now)
        bm_sub.addAction("Lompat ke Bookmark Berikutnya (Shift+B)").triggered.connect(self.jump_next_bookmark)
        bm_sub.addAction("Kelola Semua Bookmark...").triggered.connect(self.open_bookmark_manager)

        # 3. Audio Submenu
        # 3. Audio Submenu
        audio_menu = menu.addMenu("Audio")
        track_sub = audio_menu.addMenu("Pilih Track Audio")
        self._populate_audio_tracks_menu(track_sub)

        surround_sub = audio_menu.addMenu("Mode Kanal & Stereo")
        for s_mode, s_code in [("Original (Default)", "Original"),
                               ("Headphone Virtual Surround", "Dolby"),
                               ("Pelebar Stereo (Stereo Widener)", "DTS"),
                               ("Downmix Stereo (2-Channel)", "Stereo")]:
            act = surround_sub.addAction(s_mode)
            act.triggered.connect(lambda chk, c=s_code, m=s_mode: self._set_surround_mode(c, m))

        crystal_act = audio_menu.addAction("Penjernih Vokal (Vocal Boost)")
        crystal_act.setCheckable(True)
        crystal_act.setChecked(self.engine.crystal_clear_enabled)
        crystal_act.triggered.connect(self.toggle_crystal_clear)

        norm_act = audio_menu.addAction("Normalisasi Volume (Night Mode) (Shift+N)")
        norm_act.setCheckable(True)
        norm_act.setChecked(self.engine.normalizer_enabled)
        norm_act.triggered.connect(self.toggle_audio_normalizer)

        audio_fx_act = audio_menu.addAction("Equalizer & Efek Audio...")
        audio_fx_act.triggered.connect(self.open_audio_effects)

        audio_menu.addSeparator()
        aud_del_sub = audio_menu.addMenu("Sinkronisasi Suara (Audio Delay)")
        aud_del_sub.addAction("Maju (+50ms)").triggered.connect(lambda: self.adjust_audio_delay(50000))
        aud_del_sub.addAction("Mundur (-50ms)").triggered.connect(lambda: self.adjust_audio_delay(-50000))
        aud_del_sub.addAction("Reset (0ms)").triggered.connect(lambda: self.engine.set_audio_delay(0))

        # 4. Video Submenu
        video_menu = menu.addMenu("Video")
        self.hw_context_act = video_menu.addAction("Akselerasi Perangkat Keras (GPU)")
        self.hw_context_act.setCheckable(True)
        self.hw_context_act.setChecked(self.engine.hw_accel_enabled)
        self.hw_context_act.triggered.connect(self.toggle_hw_accel)
        video_menu.addSeparator()

        ratio_sub = video_menu.addMenu("Rasio Aspek (Aspect Ratio)")
        cur_ratio = getattr(self, "current_aspect_ratio_val", "")
        for r_name, r_val in [("Default / Otomatis", ""), ("16:9 (Widescreen)", "16:9"), ("4:3 (Klasik)", "4:3"),
                              ("2.35:1 (Cinemascope)", "2.35:1"), ("21:9 (Ultrawide)", "21:9"), ("1:1 (Square)", "1:1"),
                              ("Penuhi Jendela (Stretch)", "stretch")]:
            is_active = (r_val == cur_ratio)
            act = ratio_sub.addAction(f"✓  {r_name}" if is_active else f"    {r_name}")
            act.triggered.connect(lambda chk, v=r_val, n=r_name: self.set_aspect_ratio(v, n))

        rot_sub = video_menu.addMenu("Rotasi & Balik Video (R)")
        cur_rot = getattr(self.engine, "rotation_angle", 0)
        cur_flip = getattr(self.engine, "flip_mode", "none")
        for angle, lbl in [(0, "Normal (0°)"), (90, "Putar 90°"), (180, "Putar 180°"), (270, "Putar 270°")]:
            pref = "✓  " if cur_rot == angle else "    "
            rot_sub.addAction(f"{pref}{lbl}").triggered.connect(lambda chk, a=angle: self.set_rotation_angle(a))
        rot_sub.addSeparator()
        for f_mode, f_lbl in [("none", "Cermin: Nonaktif"), ("hflip", "Balik Cermin Horizontal"), ("vflip", "Balik Cermin Vertikal")]:
            pref = "✓  " if cur_flip == f_mode else "    "
            rot_sub.addAction(f"{pref}{f_lbl}").triggered.connect(lambda chk, m=f_mode: self.set_flip_mode(m))

        video_adj_act = video_menu.addAction("Pengaturan Gambar & Warna...")
        video_adj_act.triggered.connect(self.open_video_adjust)

        snap_act = video_menu.addAction("Ambil Tangkapan Layar (Snapshot PNG)")
        snap_act.setShortcut(QKeySequence("Ctrl+E"))
        snap_act.triggered.connect(self.take_snapshot)

        # 5. Subtitle Submenu
        sub_menu = menu.addMenu("Subtitle")
        s_track_sub = sub_menu.addMenu("Pilih Track Subtitle")
        self._populate_sub_tracks_menu(s_track_sub)

        online_sub_act = sub_menu.addAction("Cari Subtitle Online (Ctrl+Shift+S)...")
        online_sub_act.triggered.connect(self.open_online_subtitles)

        load_sub_act = sub_menu.addAction("Muat File Subtitle Manual (.srt, .ass)...")
        load_sub_act.triggered.connect(self.load_subtitle_file)

        sub_del_sub = sub_menu.addMenu("Sinkronisasi Delay Subtitle")
        sub_del_sub.addAction("Maju (+50ms)").triggered.connect(lambda: self.adjust_sub_delay(50000))
        sub_del_sub.addAction("Mundur (-50ms)").triggered.connect(lambda: self.adjust_sub_delay(-50000))
        sub_del_sub.addAction("Reset (0ms)").triggered.connect(lambda: self.engine.set_subtitle_delay(0))

        sub_style_act = sub_menu.addAction("Pengaturan Tampilan Subtitle...")
        sub_style_act.triggered.connect(self.open_subtitle_style)

        # 6. Tampilan Submenu
        view_menu = menu.addMenu("Tampilan")
        fs_act = view_menu.addAction("Layar Penuh (Fullscreen)")
        fs_act.setShortcuts([QKeySequence("Alt+Return"), QKeySequence("F11")])
        fs_act.triggered.connect(self.toggle_fullscreen)

        pip_act = view_menu.addAction("Picture-in-Picture (PiP)")
        pip_act.setShortcut(QKeySequence("Ctrl+M"))
        pip_act.triggered.connect(self.toggle_pip_mode)

        ontop_act = view_menu.addAction("Selalu di Atas (Always on Top)")
        ontop_act.setCheckable(True)
        ontop_act.setChecked(self.always_on_top)
        ontop_act.triggered.connect(self.toggle_always_on_top)

        pl_act = view_menu.addAction("Daftar Putar (Playlist)")
        pl_act.setShortcut(QKeySequence("F8"))
        pl_act.triggered.connect(self.toggle_playlist)

        hud_act = view_menu.addAction("Informasi Teknis (Tab)")
        hud_act.setShortcut(QKeySequence("Tab"))
        hud_act.setCheckable(True)
        hud_act.setChecked(hasattr(self, "stats_hud") and self.stats_hud.hud_active)
        hud_act.triggered.connect(self.toggle_stats_hud)

        view_menu.addSeparator()
        info_act = view_menu.addAction("Properti Media & Codec")
        info_act.setShortcut(QKeySequence("Ctrl+J"))
        info_act.triggered.connect(self.open_media_info)

        help_act = view_menu.addAction("Daftar Pintasan Keyboard")
        help_act.setShortcut(QKeySequence("F1"))
        help_act.triggered.connect(self.open_shortcuts_cheat_sheet)

        menu.addSeparator()
        exit_act = menu.addAction("Keluar")
        exit_act.setShortcut(QKeySequence("Ctrl+Q"))
        exit_act.triggered.connect(self.close)

        menu.exec(target_pos)

    # --- Keyboard Shortcuts Handler ---
    def keyPressEvent(self, event: QKeyEvent):
        if self._handle_playback_shortcut(event):
            event.accept()
            return
        super().keyPressEvent(event)

    # --- Drag & Drop ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            paths = [u.toLocalFile() for u in urls if os.path.exists(u.toLocalFile())]
            if paths:
                sub_exts = {".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx"}
                sub_paths = [p for p in paths if os.path.splitext(p)[1].lower() in sub_exts]
                media_paths = [p for p in paths if os.path.splitext(p)[1].lower() not in sub_exts]

                for sp in sub_paths:
                    if self.engine.is_media_loaded():
                        self.engine.add_subtitle_file(sp)
                        self.osd.show_message(f"Subtitle dimuat: {os.path.basename(sp)}")

                if media_paths:
                    if len(media_paths) > 1 or not getattr(self, "auto_queue_folder", True):
                        self.playlist.add_paths(media_paths, auto_play=False)
                    self.play_file(media_paths[0])
        event.acceptProposedAction()

    def closeEvent(self, event):
        if hasattr(self, "timer") and self.timer:
            self.timer.stop()
        self.engine.save_current_position()
        self.engine.stop()
        if hasattr(self, "floating_dock") and self.floating_dock:
            self.floating_dock.close()
        if hasattr(self, "center_play_btn") and self.center_play_btn:
            self.center_play_btn.close()
        if hasattr(self, "osd") and self.osd:
            self.osd.close()
        if hasattr(self, "stats_hud") and self.stats_hud:
            self.stats_hud.close()
        if self.pip_window:
            self.pip_window.close()
        super().closeEvent(event)
