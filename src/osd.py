"""
On-Screen Display (OSD) and Stream Info overlay widgets.
"""

import os
from PyQt6.QtWidgets import QWidget, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPoint, QRectF, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QFontMetrics


class OSDOverlay(QWidget):
    """
    On-Screen Display status notification over the video canvas.
    """
    def __init__(self, parent=None):
        main_win = parent
        if parent and hasattr(parent, "main_win"):
            main_win = parent.main_win
        super().__init__(main_win, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.main_win = main_win
        self.video_widget_ref = parent if hasattr(parent, "mapToGlobal") else getattr(main_win, "video_widget", None)

        self.setObjectName("OSDOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.text = ""
        self.font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(200)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim.finished.connect(self._on_anim_finished)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._fade_out)

        self.hide()

    def position_on_player(self):
        if not self.main_win or not self.main_win.isVisible() or self.main_win.isMinimized() or getattr(self.main_win, "pip_mode", False):
            self.hide()
            return
        if not self.main_win.isActiveWindow() and not getattr(self.main_win, "always_on_top", False):
            self.hide()
            return
        vw = getattr(self.main_win, "video_widget", self.video_widget_ref)
        if not vw:
            return
        v_global = vw.mapToGlobal(QPoint(0, 0))
        y_offset = 20
        if hasattr(self.main_win, "resume_banner") and self.main_win.resume_banner.isVisible():
            y_offset = 72
        self.move(v_global.x() + 20, v_global.y() + y_offset)

    def paintEvent(self, event):
        if not self.text:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)

        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        painter.setPen(QPen(QColor(255, 255, 255, 32), 1.0))
        painter.setBrush(QBrush(QColor(20, 20, 24, 220)))
        painter.drawRoundedRect(rect, 5.0, 5.0)

        painter.setFont(self.font)
        painter.setPen(QColor(244, 244, 245))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text)

    def show_message(self, text: str, duration_ms: int = 1400):
        if not self.main_win or not self.main_win.isVisible() or self.main_win.isMinimized() or getattr(self.main_win, "pip_mode", False):
            return
        if not self.main_win.isActiveWindow() and not getattr(self.main_win, "always_on_top", False):
            return

        self.text = text
        fm = QFontMetrics(self.font)
        lines = self.text.split("\n")
        tw = max((fm.horizontalAdvance(line) for line in lines), default=0)
        th = fm.lineSpacing() * len(lines)
        self.setFixedSize(tw + 32, th + 16)
        self.position_on_player()

        if not self.isVisible():
            self.show()

        self.anim.stop()
        self.hide_timer.stop()

        self.opacity_effect.setOpacity(1.0)
        self.update()
        self.hide_timer.start(duration_ms)

    def setText(self, text: str):
        self.show_message(text)

    def _fade_out(self):
        cur_op = self.opacity_effect.opacity()
        if cur_op > 0.05:
            self.anim.stop()
            self.anim.setDuration(220)
            self.anim.setStartValue(cur_op)
            self.anim.setEndValue(0.0)
            self.anim.start()
        else:
            self.hide()

    def _on_anim_finished(self):
        if self.opacity_effect.opacity() <= 0.05:
            self.hide()


class LiveStatsHUD(QWidget):
    """
    Minimalist technical stream info overlay toggled via 'Tab'.
    """
    def __init__(self, main_win=None):
        super().__init__(main_win, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.main_win = main_win
        self.setObjectName("LiveStatsHUD")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.header_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        self.label_font = QFont("Consolas", 9, QFont.Weight.Normal)
        self.val_font = QFont("Consolas", 9, QFont.Weight.Normal)

        self.rows = []
        self.hud_active = False
        self.setFixedSize(410, 195)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1000)
        self.refresh_timer.timeout.connect(self.refresh_stats)

        self.hide()

    def toggle_hud(self) -> bool:
        if self.hud_active:
            self.hide_hud()
            return False
        else:
            self.show_hud()
            return True

    def show_hud(self):
        self.hud_active = True
        self.refresh_stats()
        if not self.main_win or not self.main_win.isVisible() or self.main_win.isMinimized() or getattr(self.main_win, "pip_mode", False):
            return
        if not self.main_win.isActiveWindow() and not getattr(self.main_win, "always_on_top", False):
            return
        self.position_on_player()
        self.show()
        self.refresh_timer.start()

    def hide_hud(self):
        self.hud_active = False
        self.refresh_timer.stop()
        self.hide()

    def position_on_player(self):
        if not self.main_win or not self.main_win.isVisible() or self.main_win.isMinimized() or getattr(self.main_win, "pip_mode", False):
            self.hide()
            return
        if not self.main_win.isActiveWindow() and not getattr(self.main_win, "always_on_top", False):
            self.hide()
            return
        vw = getattr(self.main_win, "video_widget", None)
        if not vw:
            return
        v_global = vw.mapToGlobal(QPoint(0, 0))
        self.move(v_global.x() + 20, v_global.y() + 68)

    def refresh_stats(self):
        if not self.main_win or not hasattr(self.main_win, "engine"):
            return
        eng = self.main_win.engine
        from .engine import get_process_ram_mb
        info = eng.get_codec_details()
        vsz = eng.get_video_size()
        w, h = vsz[0], vsz[1]
        if w <= 0 or h <= 0:
            w = info.get("video_width", 0) or eng.player.video_get_width()
            h = info.get("video_height", 0) or eng.player.video_get_height()
        res_str = f"{w} x {h}" if (w > 0 and h > 0) else "-"

        fps = eng.get_fps()
        fps_str = f"{fps:.2f} fps" if fps > 0 else "-"
        ram_mb = get_process_ram_mb()

        fname = os.path.basename(eng.current_mrl or "-")
        if len(fname) > 38:
            fname = fname[:35] + "..."

        self.rows = [
            ("File", fname),
            ("Resolusi", res_str),
            ("Frame Rate", fps_str),
            ("Video Codec", str(info.get("video_codec", "-"))[:38]),
            ("Format Warna", f"{info.get('bit_depth', '8-bit')} / {info.get('hdr_status', 'SDR')}"),
            ("Decoder", str(info.get("decoding_engine", "-"))[:38]),
            ("Audio Codec", f"{str(info.get('audio_codec', '-'))[:24]} ({info.get('sample_rate', '-')})"),
            ("Memori", f"{ram_mb:.1f} MB")
        ]
        self.position_on_player()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)

        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        painter.setPen(QPen(QColor(255, 255, 255, 32), 1.0))
        painter.setBrush(QBrush(QColor(20, 20, 24, 228)))
        painter.drawRoundedRect(rect, 6.0, 6.0)

        painter.setFont(self.header_font)
        painter.setPen(QColor(228, 228, 231))
        painter.drawText(
            QRectF(14, 8, self.width() - 28, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Informasi Stream (Tab)"
        )

        painter.setPen(QPen(QColor(255, 255, 255, 25), 1.0))
        painter.drawLine(14, 30, self.width() - 14, 30)

        y_offset = 36
        for label, val in self.rows:
            painter.setFont(self.label_font)
            painter.setPen(QColor(156, 163, 175))
            painter.drawText(
                QRectF(14, y_offset, 96, 18),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"{label}:"
            )

            painter.setFont(self.val_font)
            painter.setPen(QColor(244, 244, 245))
            painter.drawText(
                QRectF(114, y_offset, self.width() - 126, 18),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                val
            )
            y_offset += 19
