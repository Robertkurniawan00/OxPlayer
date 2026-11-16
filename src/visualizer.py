"""
OXPlayer Real-Time Audio Spectrum Visualizer Widget
Powered by native C++ DSP FFT Accelerator (ox_dsp_accel.dll).
Features smooth decay physics, peak hold indicators, and modern glowing neon gradients.
"""

import math
import random
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QBrush, QPen
from PyQt6.QtCore import Qt, QTimer, pyqtSlot

try:
    from src.dsp_accel import compute_fft_bands, calculate_audio_levels
except ImportError:
    compute_fft_bands = None
    calculate_audio_levels = None


class AudioVisualizerWidget(QWidget):
    """
    Real-time 32-band audio spectrum visualizer bar.
    """
    def __init__(self, num_bands=32, parent=None):
        super().__init__(parent)
        self.num_bands = num_bands
        self.band_values = [0.0] * num_bands
        self.peak_values = [0.0] * num_bands
        self.peak_decay = 0.02
        self.bar_decay = 0.08
        self.is_active = False

        # Visual styling
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFixedHeight(75)

        # Update animation timer (30 FPS)
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._update_physics)

    def start_visualizer(self):
        self.is_active = True
        self.show()
        if not self.timer.isActive():
            self.timer.start()

    def stop_visualizer(self):
        self.is_active = False
        self.timer.stop()
        self.band_values = [0.0] * self.num_bands
        self.peak_values = [0.0] * self.num_bands
        self.update()
        self.hide()

    def toggle_visualizer(self) -> bool:
        if self.is_active:
            self.stop_visualizer()
            return False
        else:
            self.start_visualizer()
            return True

    def feed_audio_samples(self, samples):
        """Feeds raw PCM float samples to the visualizer."""
        if not self.is_active or not samples:
            return

        if compute_fft_bands:
            new_bands = compute_fft_bands(samples, self.num_bands)
        else:
            # Fallback
            new_bands = [abs(s) for s in samples[:self.num_bands]]

        for i in range(self.num_bands):
            target = new_bands[i] if i < len(new_bands) else 0.0
            if target > self.band_values[i]:
                self.band_values[i] = target
            if target > self.peak_values[i]:
                self.peak_values[i] = target

    @pyqtSlot()
    def _update_physics(self):
        """Applies gravity decay to spectrum bars and peak dots."""
        if not self.is_active:
            return

        needs_repaint = False
        for i in range(self.num_bands):
            # Bar decay
            if self.band_values[i] > 0.001:
                self.band_values[i] = max(0.0, self.band_values[i] - self.bar_decay)
                needs_repaint = True
            else:
                self.band_values[i] = 0.0

            # Peak decay
            if self.peak_values[i] > 0.001:
                self.peak_values[i] = max(0.0, self.peak_values[i] - self.peak_decay)
                needs_repaint = True
            else:
                self.peak_values[i] = 0.0

        if needs_repaint:
            self.update()

    def paintEvent(self, event):
        if not self.is_active:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        width = self.width()
        height = self.height()
        gap = 3.0
        total_gaps = (self.num_bands - 1) * gap
        bar_width = max(2.0, (width - total_gaps - 16.0) / self.num_bands)

        start_x = 8.0

        # Gradient from Cyan -> Purple -> Electric Pink
        grad = QLinearGradient(0, height, 0, 0)
        grad.setColorAt(0.0, QColor(0, 240, 255, 180))    # Neon Cyan
        grad.setColorAt(0.6, QColor(138, 43, 226, 210))  # Electric Purple
        grad.setColorAt(1.0, QColor(255, 0, 127, 240))    # Neon Pink

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))

        peak_pen = QPen(QColor(255, 255, 255, 220), 1.5)

        for i in range(self.num_bands):
            val = min(1.0, max(0.0, self.band_values[i]))
            bar_height = max(3.0, val * (height - 10.0))
            x = start_x + i * (bar_width + gap)
            y = height - bar_height

            # Draw smooth rounded bar
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(int(x), int(y), int(bar_width), int(bar_height), 2.0, 2.0)

            # Draw peak dot
            peak_val = min(1.0, max(0.0, self.peak_values[i]))
            if peak_val > 0.05:
                peak_y = height - (peak_val * (height - 10.0)) - 3.0
                painter.setPen(peak_pen)
                painter.drawLine(int(x), int(peak_y), int(x + bar_width), int(peak_y))
                painter.setPen(Qt.PenStyle.NoPen)
