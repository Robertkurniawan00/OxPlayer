"""
VLC-style Interactive Resume Playback Banner.
Floats at the top-left of the video canvas offering:
'Lanjutkan dari 00:43:59?' [Lanjutkan] [Mulai dari Awal] [✕]
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QToolButton,
    QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, pyqtSignal


class ResumePromptBanner(QWidget):
    """
    VLC-style interactive Resume Playback Banner.
    Owned Tool window floating above the video canvas, immune to LibVLC Direct3D occlusion.
    """
    resume_requested = pyqtSignal(int)
    restart_requested = pyqtSignal()
    dismissed = pyqtSignal()

    def __init__(self, main_win=None):
        parent = main_win
        if main_win and hasattr(main_win, "main_win"):
            parent = main_win.main_win
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.main_win = parent
        self.target_ms = 0

        self.setObjectName("ResumePromptBanner")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._setup_ui()
        self._setup_animation()
        self.hide()

    def _setup_ui(self):
        self.setStyleSheet("""
            QWidget#ResumeContainer {
                background-color: rgba(20, 20, 24, 0.94);
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 6px;
            }
            QLabel {
                color: #e4e4e7;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
            }
            QLabel#TimeHighlight {
                color: #ffffff;
                font-weight: 600;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }
            QPushButton#ResumeBtn {
                background-color: rgba(255, 255, 255, 0.16);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.24);
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#ResumeBtn:hover {
                background-color: rgba(255, 255, 255, 0.25);
                border-color: rgba(255, 255, 255, 0.35);
            }
            QPushButton#RestartBtn {
                background-color: rgba(255, 255, 255, 0.08);
                color: #d4d4d8;
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
            }
            QPushButton#RestartBtn:hover {
                background-color: rgba(255, 255, 255, 0.16);
                color: #ffffff;
            }
            QToolButton#CloseBtn {
                background: transparent;
                color: #a1a1aa;
                border: none;
                font-size: 12px;
                padding: 2px 5px;
                border-radius: 3px;
            }
            QToolButton#CloseBtn:hover {
                background-color: rgba(255, 255, 255, 0.14);
                color: #ffffff;
            }
        """)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget(self)
        self.container.setObjectName("ResumeContainer")
        c_layout = QHBoxLayout(self.container)
        c_layout.setContentsMargins(12, 6, 8, 6)
        c_layout.setSpacing(8)

        self.text_lbl = QLabel("Lanjutkan menonton dari")
        c_layout.addWidget(self.text_lbl)

        self.time_lbl = QLabel("00:00?")
        self.time_lbl.setObjectName("TimeHighlight")
        c_layout.addWidget(self.time_lbl)

        self.resume_btn = QPushButton("Lanjutkan")
        self.resume_btn.setObjectName("ResumeBtn")
        self.resume_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.resume_btn.clicked.connect(self._on_resume_clicked)
        c_layout.addWidget(self.resume_btn)

        self.restart_btn = QPushButton("Mulai dari Awal")
        self.restart_btn.setObjectName("RestartBtn")
        self.restart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restart_btn.clicked.connect(self._on_restart_clicked)
        c_layout.addWidget(self.restart_btn)

        self.close_btn = QToolButton()
        self.close_btn.setObjectName("CloseBtn")
        self.close_btn.setText("✕")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self._on_dismiss_clicked)
        c_layout.addWidget(self.close_btn)

        main_layout.addWidget(self.container)

    def _setup_animation(self):
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.auto_hide_timer = QTimer(self)
        self.auto_hide_timer.setSingleShot(True)
        self.auto_hide_timer.setInterval(10000)
        self.auto_hide_timer.timeout.connect(self.fade_out)

    def show_prompt(self, target_ms: int, time_str: str):
        if not self.main_win or not self.main_win.isVisible() or self.main_win.isMinimized() or getattr(self.main_win, "pip_mode", False):
            return
        self.target_ms = target_ms
        self.time_lbl.setText(f"{time_str}?")
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()

        self.anim.stop()
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(1.0)
        self.anim.start()

        self.auto_hide_timer.start()

    def reposition(self):
        if not self.main_win or not self.main_win.isVisible() or self.main_win.isMinimized() or getattr(self.main_win, "pip_mode", False):
            self.hide_immediate()
            return
        vw = getattr(self.main_win, "video_widget", None)
        if not vw:
            return
        v_global = vw.mapToGlobal(QPoint(0, 0))
        self.move(v_global.x() + 20, v_global.y() + 20)

    def hide_immediate(self):
        self.auto_hide_timer.stop()
        self.anim.stop()
        self.opacity_effect.setOpacity(0.0)
        self.hide()

    def fade_out(self):
        self.anim.stop()
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(0.0)
        self.anim.finished.connect(self._on_fade_finished)
        self.anim.start()

    def _on_fade_finished(self):
        try:
            self.anim.finished.disconnect(self._on_fade_finished)
        except Exception:
            pass
        if self.opacity_effect.opacity() == 0.0:
            self.hide()
            self.dismissed.emit()

    def _on_resume_clicked(self):
        self.auto_hide_timer.stop()
        self.resume_requested.emit(self.target_ms)
        self.fade_out()

    def _on_restart_clicked(self):
        self.auto_hide_timer.stop()
        self.restart_requested.emit()
        self.fade_out()

    def _on_dismiss_clicked(self):
        self.auto_hide_timer.stop()
        self.fade_out()

    def enterEvent(self, event):
        self.auto_hide_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.isVisible() and self.opacity_effect.opacity() > 0.1:
            self.auto_hide_timer.start(5000)
        super().leaveEvent(event)
