"""
Netflix / Crunchyroll style Binge-Watching Next Episode Banner.
Floats in the bottom-right corner of the video canvas when an episode nears completion:
'🎬 EPISODE BERIKUTNYA'
'Episode 16: Nama Judul Episode'
'Memutar otomatis dalam 10 detik...'
[ ▶ Putar Sekarang ] [ ✕ Batalkan ]
"""

import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QFont


def parse_episode_label(filename: str) -> str:
    """Extracts clean season & episode label from filename (e.g. S01E03, Ep 12)."""
    name = re.sub(r'\.[^.]+$', '', filename)
    # 1. Season X Episode Y (S01E02 or s1e2)
    m = re.search(r'(?i)(?:^|[\s_.-])S(\d+)\s*E(\d+)(?:[\s_.-]|$)', name)
    if m:
        return f"Season {int(m.group(1))}, Episode {int(m.group(2))}"
    # 2. 1x02 format
    m = re.search(r'(?:^|[\s_.-])(\d+)x(\d+)(?:[\s_.-]|$)', name)
    if m:
        return f"Season {int(m.group(1))}, Episode {int(m.group(2))}"
    # 3. Episode / Ep / Eps prefix
    m = re.search(r'(?i)(?:^|[\s_.-])(?:Ep|Episode|Eps|E)[.\s_-]*(\d+)(?:[\s_.-]|$)', name)
    if m:
        return f"Episode {int(m.group(1))}"
    # 4. Standalone numbers like ' - 02 - ' or '[02]'
    m = re.search(r'(?:[-_\[\s])(\d{1,4})(?:[-_\]\s]|$)', name)
    if m:
        v = int(m.group(1))
        # Exclude release years (1900-2099)
        if not (1900 <= v <= 2099):
            return f"Episode {v}"
    # Fallback: cleaned filename
    cleaned = re.sub(r'[\._]', ' ', name).strip()
    return cleaned[:36] + "..." if len(cleaned) > 38 else cleaned


class NextEpisodeBanner(QWidget):
    """
    Floating interactive Next Episode card for Binge-Watching.
    Appears near the end of video (last 15s) with a live countdown and Play Now action.
    """
    play_next_requested = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, main_win=None):
        parent = main_win
        if main_win and hasattr(main_win, "main_win"):
            parent = main_win.main_win
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.main_win = parent
        self.total_countdown_sec = 10
        self.remaining_sec = 10

        self.setObjectName("NextEpisodeBanner")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._setup_ui()
        self._setup_animation()

        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)
        self.countdown_timer.timeout.connect(self._on_countdown_tick)

        self.hide()

    def _setup_ui(self):
        self.setStyleSheet("""
            QWidget#NextEpContainer {
                background-color: rgba(18, 18, 22, 0.94);
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 8px;
            }
            QLabel#BadgeLabel {
                color: #38bdf8;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
            QLabel#TitleLabel {
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#CountdownLabel {
                color: #a1a1aa;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11px;
            }
            QProgressBar {
                border: none;
                background-color: rgba(255, 255, 255, 0.10);
                height: 3px;
                border-radius: 1px;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 1px;
            }
            QPushButton#PlayNowBtn {
                background-color: #0284c7;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton#PlayNowBtn:hover {
                background-color: #0ea5e9;
            }
            QPushButton#PlayNowBtn:pressed {
                background-color: #0369a1;
            }
            QPushButton#CancelBtn {
                background-color: rgba(255, 255, 255, 0.08);
                color: #d4d4d8;
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton#CancelBtn:hover {
                background-color: rgba(255, 255, 255, 0.16);
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget(self)
        self.container.setObjectName("NextEpContainer")
        c_layout = QVBoxLayout(self.container)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.setSpacing(6)

        # Header Badge
        self.badge_lbl = QLabel("🎬 EPISODE SELANJUTNYA")
        self.badge_lbl.setObjectName("BadgeLabel")
        c_layout.addWidget(self.badge_lbl)

        # Next Episode Title
        self.title_lbl = QLabel("Episode 02")
        self.title_lbl.setObjectName("TitleLabel")
        c_layout.addWidget(self.title_lbl)

        # Countdown Status
        self.countdown_lbl = QLabel("Memutar otomatis dalam 10 detik...")
        self.countdown_lbl.setObjectName("CountdownLabel")
        c_layout.addWidget(self.countdown_lbl)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        c_layout.addWidget(self.progress_bar)

        # Buttons row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.play_btn = QPushButton("▶ Putar Sekarang")
        self.play_btn.setObjectName("PlayNowBtn")
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.clicked.connect(self._on_play_now_clicked)
        btn_layout.addWidget(self.play_btn)

        self.cancel_btn = QPushButton("✕ Batalkan")
        self.cancel_btn.setObjectName("CancelBtn")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_layout.addWidget(self.cancel_btn)

        c_layout.addLayout(btn_layout)
        layout.addWidget(self.container)

        self.setFixedWidth(310)

    def _setup_animation(self):
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(240)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_anim.finished.connect(self._on_anim_finished)

    def show_prompt(self, raw_title: str, countdown_sec: int = 10):
        """Displays next episode prompt with countdown timer."""
        if not self.main_win or not self.main_win.isVisible() or self.main_win.isMinimized() or getattr(self.main_win, "pip_mode", False):
            return
        label = parse_episode_label(raw_title)
        # Format display: 'Episode 02' or 'Season 1, Episode 3: Title'
        clean_name = re.sub(r'\.[^.]+$', '', raw_title)
        if label != clean_name and len(clean_name) > len(label):
            display_title = f"{label} - {clean_name}"
        else:
            display_title = label

        if len(display_title) > 34:
            display_title = display_title[:32] + "..."

        self.title_lbl.setText(display_title)
        self.total_countdown_sec = max(3, countdown_sec)
        self.remaining_sec = self.total_countdown_sec
        self.countdown_lbl.setText(f"Memutar otomatis dalam {self.remaining_sec} detik...")
        self.progress_bar.setValue(100)

        self.reposition()
        self.show()
        self.raise_()

        # Fade in
        self.fade_anim.stop()
        self.fade_anim.setStartValue(self.opacity_effect.opacity())
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()

        self.countdown_timer.start()

    def _on_countdown_tick(self):
        self.remaining_sec -= 1
        if self.remaining_sec > 0:
            self.countdown_lbl.setText(f"Memutar otomatis dalam {self.remaining_sec} detik...")
            progress_val = int((self.remaining_sec / float(self.total_countdown_sec)) * 100)
            self.progress_bar.setValue(progress_val)
        else:
            self.countdown_timer.stop()
            self.progress_bar.setValue(0)
            self.countdown_lbl.setText("Memutar episode selanjutnya sekarang...")
            self.fade_out()
            self.play_next_requested.emit()

    def _on_play_now_clicked(self):
        self.countdown_timer.stop()
        self.fade_out()
        self.play_next_requested.emit()

    def _on_cancel_clicked(self):
        self.countdown_timer.stop()
        self.fade_out()
        self.cancelled.emit()

    def fade_out(self):
        self.countdown_timer.stop()
        if self.isVisible() and self.opacity_effect.opacity() > 0.05:
            self.fade_anim.stop()
            self.fade_anim.setStartValue(self.opacity_effect.opacity())
            self.fade_anim.setEndValue(0.0)
            self.fade_anim.start()
        else:
            self.hide()

    def hide_immediate(self):
        self.countdown_timer.stop()
        self.fade_anim.stop()
        self.opacity_effect.setOpacity(0.0)
        self.hide()

    def _on_anim_finished(self):
        if self.opacity_effect.opacity() <= 0.05:
            self.hide()

    def reposition(self):
        """Positions the banner at the bottom-right corner of the parent video canvas."""
        if not self.main_win or not self.main_win.isVisible() or self.main_win.isMinimized() or getattr(self.main_win, "pip_mode", False):
            self.hide_immediate()
            return
        vw = getattr(self.main_win, "video_widget", None)
        if not vw:
            return
        v_global = vw.mapToGlobal(QPoint(0, 0))
        pw = vw.width()
        ph = vw.height()
        bw = self.width()
        bh = self.sizeHint().height() or 140

        # Offset from bottom right (above floating control dock)
        x = v_global.x() + max(16, pw - bw - 24)
        y = v_global.y() + max(16, ph - bh - 85)
        self.move(x, y)
