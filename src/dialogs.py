"""
Dialog windows for OXPlayer:
- JumpToTimeDialog (Ctrl+G)
- BookmarkManagerDialog (B)
- ShortcutsCheatSheetDialog (F1)
- AudioEffectsDialog (Ctrl+A)
- VideoAdjustDialog
- SubtitleStyleDialog
- MediaInfoDialog (Ctrl+J)
- OpenStreamDialog (Ctrl+U)
- ContinueWatchingDialog (Ctrl+Y)
"""

import os
import re
import datetime
import urllib.parse
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QLineEdit, QFormLayout, QGroupBox,
    QCheckBox, QSpinBox, QListWidget, QListWidgetItem, QProgressBar,
    QMessageBox, QTabWidget, QScrollArea, QWidget, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices

from .engine import parse_timestamp_to_ms


class JumpToTimeDialog(QDialog):
    """Jump to Time Dialog (Ctrl+G)."""
    def __init__(self, engine, osd_callback=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.osd_callback = osd_callback
        self.setWindowTitle("Lompat ke Waktu (Ctrl+G)")
        self.setFixedSize(360, 190)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        cur_ms = self.engine.get_time()
        tot_ms = self.engine.get_length()
        cur_str = self._format_time(cur_ms)
        tot_str = self._format_time(tot_ms)

        info_lbl = QLabel(f"Posisi Saat Ini: {cur_str} / Total: {tot_str}")
        info_lbl.setStyleSheet(
            "color: #e4e4e7; font-family: 'Consolas', monospace; font-size: 12px; "
            "background: #202025; border: 1px solid #32323a; "
            "border-radius: 4px; padding: 6px 10px;"
        )
        layout.addWidget(info_lbl)

        form = QFormLayout()
        self.time_input = QLineEdit()
        self.time_input.setPlaceholderText("Contoh: 01:23:45 atau 14:30")
        self.time_input.setText(cur_str)
        self.time_input.returnPressed.connect(self._jump_now)
        form.addRow("Waktu Tujuan:", self.time_input)
        layout.addLayout(form)

        self.set_default_start_chk = QCheckBox("Ingat sebagai waktu mulai untuk file ini")
        has_custom = bool(self.engine.get_custom_start_time(self.engine.current_mrl))
        self.set_default_start_chk.setChecked(has_custom)
        layout.addWidget(self.set_default_start_chk)

        btn_row = QHBoxLayout()
        jump_btn = QPushButton("Lompat")
        jump_btn.setStyleSheet("background-color: #32323a; color: #ffffff; font-weight: 600; padding: 6px 16px; border: 1px solid #52525b; border-radius: 4px;")
        jump_btn.clicked.connect(self._jump_now)

        cancel_btn = QPushButton("Batal")
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(jump_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _format_time(self, ms: int) -> str:
        sec = ms // 1000
        mins, secs = divmod(sec, 60)
        hrs, mins = divmod(mins, 60)
        if hrs > 0:
            return f"{hrs:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    def _jump_now(self):
        text = self.time_input.text().strip()
        ms = parse_timestamp_to_ms(text)
        if ms is None:
            QMessageBox.warning(self, "Format Salah", "Format waktu tidak valid.\nGunakan format HH:MM:SS, MM:SS, atau detik.")
            return

        tot_ms = self.engine.get_length()
        if tot_ms > 0 and ms > tot_ms:
            ms = tot_ms

        self.engine.set_time(ms)

        if self.engine.current_mrl:
            if self.set_default_start_chk.isChecked():
                self.engine.set_custom_start_time(self.engine.current_mrl, ms)
            else:
                self.engine.clear_custom_start_time(self.engine.current_mrl)

        if self.osd_callback:
            self.osd_callback(f"Lompat ke: {self._format_time(ms)}")
        self.accept()


class BookmarkManagerDialog(QDialog):
    """Dialog to manage bookmarks for the current file."""
    def __init__(self, engine, osd_callback=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.osd_callback = osd_callback
        self.setWindowTitle("Bookmark")
        self.setFixedSize(440, 340)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Daftar Bookmark")
        title.setStyleSheet("font-weight: 600; font-size: 13px; color: #ffffff;")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._jump_selected)
        layout.addWidget(self.list_widget)

        self._refresh_list()

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Tambah")
        add_btn.clicked.connect(self._add_current)

        jump_btn = QPushButton("Lompat")
        jump_btn.setStyleSheet("background-color: #32323a; color: #ffffff; font-weight: 600; padding: 5px 14px; border: 1px solid #52525b; border-radius: 4px;")
        jump_btn.clicked.connect(self._jump_selected)

        del_btn = QPushButton("Hapus")
        del_btn.clicked.connect(self._delete_selected)

        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.close)

        btn_row.addWidget(add_btn)
        btn_row.addWidget(jump_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _refresh_list(self):
        self.list_widget.clear()
        bms = self.engine.get_bookmarks_for_current_media()
        if not bms:
            item = QListWidgetItem("Belum ada bookmark untuk file ini.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            return
        for idx, bm in enumerate(bms):
            item = QListWidgetItem(f"{bm.get('label', '')} ({bm.get('ms', 0) // 1000}s)")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.list_widget.addItem(item)

    def _add_current(self):
        self.engine.add_bookmark()
        self._refresh_list()
        if self.osd_callback:
            self.osd_callback("Bookmark ditambahkan")

    def _jump_selected(self):
        cur = self.list_widget.currentItem()
        if not cur:
            return
        idx = cur.data(Qt.ItemDataRole.UserRole)
        bms = self.engine.get_bookmarks_for_current_media()
        if idx is not None and 0 <= idx < len(bms):
            ms = bms[idx]["ms"]
            self.engine.set_time(ms)
            if self.osd_callback:
                self.osd_callback(f"Bookmark: {bms[idx].get('label')}")
            self.accept()

    def _delete_selected(self):
        cur = self.list_widget.currentItem()
        if not cur:
            return
        idx = cur.data(Qt.ItemDataRole.UserRole)
        if idx is not None:
            self.engine.delete_bookmark(idx)
            self._refresh_list()


class ShortcutsCheatSheetDialog(QDialog):
    """Shortcuts & mouse controls reference (F1)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pintasan Keyboard & Mouse (F1)")
        self.setFixedSize(560, 460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Daftar Pintasan Keyboard & Mouse")
        title.setStyleSheet("font-weight: 600; font-size: 14px; color: #ffffff;")
        layout.addWidget(title)

        tab_widget = QTabWidget()

        # Tab 1: Pemutaran
        tab_nav = QWidget()
        l_nav = QFormLayout(tab_nav)
        nav_keys = [
            ("Space", "Putar / Jeda"),
            ("Ctrl + O", "Buka File Media"),
            ("Ctrl + U", "Buka URL / Stream Online (yt-dlp)"),
            ("Ctrl + Y", "Riwayat Tontonan"),
            ("Left / Right", "Mundur / Maju 10 detik"),
            ("Shift + Left / Right", "Mundur / Maju 5 detik"),
            ("Ctrl + Left / Right", "Mundur / Maju 30 detik"),
            ("Scroll Seekbar", "Maju / Mundur 5 detik"),
            ("F", "Langkah Frame (Frame Step)"),
            ("Ctrl + G", "Lompat ke Waktu"),
            ("X / C / Z", "Perlambat (-0.1x) / Percepat (+0.1x) / Reset (1.0x)"),
            ("[ / ] / \\", "Set Titik A / Titik B / Reset Loop A-B"),
            ("Page Up / Page Down", "File Sebelumnya / Berikutnya"),
            ("B / Shift + B", "Tambah Bookmark / Lompat ke Bookmark")
        ]
        for k, d in nav_keys:
            l_nav.addRow(QLabel(f"<b>{k}</b>"), QLabel(d))
        tab_widget.addTab(tab_nav, "Pemutaran")

        # Tab 2: Audio & Subtitle
        tab_aud = QWidget()
        l_aud = QFormLayout(tab_aud)
        aud_keys = [
            ("Up / Down", "Volume +/- 5%"),
            ("Scroll Area Video", "Ubah Volume (+/- 5%)"),
            ("Klik Tengah Mouse", "Bisu / Bunyikan Suara (Mute)"),
            ("M", "Bisu (Mute / Unmute)"),
            ("Shift + N", "Normalisasi Volume (Night Mode)"),
            ("A", "Ganti Track Audio"),
            ("Ctrl + A", "Equalizer & Pengaturan Audio"),
            ("+ / -", "Sinkronisasi Delay Audio (+/- 50ms)"),
            ("V", "Ganti Track Subtitle"),
            ("Ctrl + Shift + S", "Cari Subtitle Online"),
            ("Shift + [ / ]", "Sinkronisasi Delay Subtitle (+/- 50ms)")
        ]
        for k, d in aud_keys:
            l_aud.addRow(QLabel(f"<b>{k}</b>"), QLabel(d))
        tab_widget.addTab(tab_aud, "Audio & Subtitle")

        # Tab 3: Video & Jendela
        tab_vid = QWidget()
        l_vid = QFormLayout(tab_vid)
        vid_keys = [
            ("F11 / Alt + Enter", "Layar Penuh (Fullscreen)"),
            ("Double Click", "Layar Penuh / Jendela Normal"),
            ("Esc", "Keluar dari Layar Penuh / PiP"),
            ("Ctrl + M", "Mode Picture-in-Picture (PiP)"),
            ("Ctrl + T", "Selalu di Atas (Always on Top)"),
            ("F8", "Tampilkan / Sembunyikan Daftar Putar"),
            ("R", "Putar Video 90°"),
            ("Ctrl + H", "Ganti Decoding Hardware / Software"),
            ("Ctrl + E", "Simpan Tangkapan Layar (Snapshot PNG)"),
            ("Tab", "Tampilkan / Sembunyikan Informasi Stream"),
            ("Ctrl + J", "Properti Media & Codec"),
            ("1 / 2 / 3 / 4", "Ukuran Jendela 50% / 100% / 150% / 200%")
        ]
        for k, d in vid_keys:
            l_vid.addRow(QLabel(f"<b>{k}</b>"), QLabel(d))
        tab_widget.addTab(tab_vid, "Video & Jendela")

        layout.addWidget(tab_widget)

        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)


class AudioEffectsDialog(QDialog):
    def __init__(self, engine, osd_callback=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.osd_callback = osd_callback
        self.setWindowTitle("Pengaturan Audio & Equalizer")
        self.setFixedSize(420, 340)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        surround_grp = QGroupBox("Mode Output Audio")
        s_layout = QFormLayout(surround_grp)

        self.surround_combo = QComboBox()
        self.surround_combo.addItem("Stereo (Default)", "Original")
        self.surround_combo.addItem("Virtual Surround", "Dolby")
        self.surround_combo.addItem("Pelebar Stereo", "DTS")
        self.surround_combo.addItem("Stereo Downmix", "Stereo")

        for i in range(self.surround_combo.count()):
            if self.surround_combo.itemData(i) == self.engine.surround_mode:
                self.surround_combo.setCurrentIndex(i)
                break

        self.surround_combo.currentIndexChanged.connect(self._on_surround_changed)
        s_layout.addRow("Output:", self.surround_combo)
        layout.addWidget(surround_grp)

        enh_grp = QGroupBox("Filter Audio")
        e_layout = QVBoxLayout(enh_grp)
        e_layout.setSpacing(8)

        self.crystal_chk = QCheckBox("Penguat Vokal (Vocal Boost)")
        self.crystal_chk.setChecked(self.engine.crystal_clear_enabled)
        self.crystal_chk.toggled.connect(self._toggle_crystal_clear)
        e_layout.addWidget(self.crystal_chk)

        self.norm_chk = QCheckBox("Normalisasi Volume")
        self.norm_chk.setChecked(self.engine.normalizer_enabled)
        self.norm_chk.toggled.connect(self._toggle_normalizer)
        e_layout.addWidget(self.norm_chk)

        layout.addWidget(enh_grp)

        eq_grp = QGroupBox("Equalizer")
        eq_layout = QHBoxLayout(eq_grp)

        self.preset_combo = QComboBox()
        presets = self.engine.get_equalizer_presets()
        if not presets:
            presets = ["Flat", "Classical", "Club", "Dance", "Full bass", "Full bass and treble",
                       "Full treble", "Headphones", "Large Hall", "Live", "Party", "Pop", "Reggae",
                       "Rock", "Ska", "Soft", "Soft rock", "Techno"]
        for p in presets:
            self.preset_combo.addItem(p)

        self.apply_preset_btn = QPushButton("Terapkan")
        self.apply_preset_btn.clicked.connect(self._apply_preset)

        self.reset_eq_btn = QPushButton("Nonaktifkan")
        self.reset_eq_btn.clicked.connect(self._disable_eq)

        eq_layout.addWidget(self.preset_combo)
        eq_layout.addWidget(self.apply_preset_btn)
        eq_layout.addWidget(self.reset_eq_btn)
        layout.addWidget(eq_grp)

        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def _on_surround_changed(self):
        mode = self.surround_combo.currentData()
        self.engine.set_surround_mode(mode)
        if self.osd_callback:
            self.osd_callback(f"Output Audio: {self.surround_combo.currentText()}")

    def _toggle_crystal_clear(self, checked: bool):
        if checked:
            self.norm_chk.setChecked(False)
        self.engine.set_crystal_clear_audio(checked)
        if self.osd_callback:
            self.osd_callback(f"Penguat Vokal: {'Aktif' if checked else 'Nonaktif'}")

    def _toggle_normalizer(self, checked: bool):
        if checked:
            self.crystal_chk.setChecked(False)
        self.engine.set_audio_normalizer(checked)
        if self.osd_callback:
            self.osd_callback(f"Normalisasi Volume: {'Aktif' if checked else 'Nonaktif'}")

    def _apply_preset(self):
        self.crystal_chk.setChecked(False)
        self.norm_chk.setChecked(False)
        idx = self.preset_combo.currentIndex()
        name = self.preset_combo.currentText()
        self.engine.apply_equalizer_preset(idx)
        if self.osd_callback:
            self.osd_callback(f"Equalizer: {name}")

    def _disable_eq(self):
        self.crystal_chk.setChecked(False)
        self.norm_chk.setChecked(False)
        self.engine.disable_equalizer()
        if self.osd_callback:
            self.osd_callback("Equalizer: Nonaktif")


class VideoAdjustDialog(QDialog):
    def __init__(self, engine, osd_callback=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.osd_callback = osd_callback
        self.setWindowTitle("Pengaturan Gambar & Warna")
        self.setFixedSize(400, 320)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self.bright_slider = QSlider(Qt.Orientation.Horizontal)
        self.bright_slider.setRange(0, 200)
        self.bright_slider.setValue(int(self.engine.brightness * 100))
        self.bright_val = QLabel(f"{int(self.engine.brightness * 100)}%")
        self.bright_val.setFixedWidth(44)
        self.bright_slider.valueChanged.connect(self._update_values)
        b_box = QHBoxLayout()
        b_box.addWidget(self.bright_slider)
        b_box.addWidget(self.bright_val)
        form.addRow("Kecerahan:", b_box)

        self.contrast_slider = QSlider(Qt.Orientation.Horizontal)
        self.contrast_slider.setRange(0, 200)
        self.contrast_slider.setValue(int(self.engine.contrast * 100))
        self.contrast_val = QLabel(f"{int(self.engine.contrast * 100)}%")
        self.contrast_val.setFixedWidth(44)
        self.contrast_slider.valueChanged.connect(self._update_values)
        c_box = QHBoxLayout()
        c_box.addWidget(self.contrast_slider)
        c_box.addWidget(self.contrast_val)
        form.addRow("Kontras:", c_box)

        self.sat_slider = QSlider(Qt.Orientation.Horizontal)
        self.sat_slider.setRange(0, 300)
        self.sat_slider.setValue(int(self.engine.saturation * 100))
        self.sat_val = QLabel(f"{int(self.engine.saturation * 100)}%")
        self.sat_val.setFixedWidth(44)
        self.sat_slider.valueChanged.connect(self._update_values)
        s_box = QHBoxLayout()
        s_box.addWidget(self.sat_slider)
        s_box.addWidget(self.sat_val)
        form.addRow("Saturasi:", s_box)

        self.hue_slider = QSlider(Qt.Orientation.Horizontal)
        self.hue_slider.setRange(-180, 180)
        self.hue_slider.setValue(int(self.engine.hue))
        self.hue_val = QLabel(f"{int(self.engine.hue)}°")
        self.hue_val.setFixedWidth(44)
        self.hue_slider.valueChanged.connect(self._update_values)
        h_box = QHBoxLayout()
        h_box.addWidget(self.hue_slider)
        h_box.addWidget(self.hue_val)
        form.addRow("Rona (Hue):", h_box)

        self.gamma_slider = QSlider(Qt.Orientation.Horizontal)
        self.gamma_slider.setRange(10, 300)
        self.gamma_slider.setValue(int(self.engine.gamma * 100))
        self.gamma_val = QLabel(f"{int(self.engine.gamma * 100)}%")
        self.gamma_val.setFixedWidth(44)
        self.gamma_slider.valueChanged.connect(self._update_values)
        g_box = QHBoxLayout()
        g_box.addWidget(self.gamma_slider)
        g_box.addWidget(self.gamma_val)
        form.addRow("Gamma:", g_box)

        layout.addLayout(form)
        layout.addStretch()

        btn_row = QHBoxLayout()
        self.reset_btn = QPushButton("Reset Default")
        self.reset_btn.clicked.connect(self._reset_defaults)
        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(self.reset_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _update_values(self):
        b = self.bright_slider.value() / 100.0
        c = self.contrast_slider.value() / 100.0
        s = self.sat_slider.value() / 100.0
        h = float(self.hue_slider.value())
        g = self.gamma_slider.value() / 100.0

        self.bright_val.setText(f"{int(b * 100)}%")
        self.contrast_val.setText(f"{int(c * 100)}%")
        self.sat_val.setText(f"{int(s * 100)}%")
        self.hue_val.setText(f"{int(h)}°")
        self.gamma_val.setText(f"{int(g * 100)}%")

        self.engine.set_video_adjustments(brightness=b, contrast=c, saturation=s, hue=h, gamma=g)

    def _reset_defaults(self):
        self.bright_slider.setValue(100)
        self.contrast_slider.setValue(100)
        self.sat_slider.setValue(100)
        self.hue_slider.setValue(0)
        self.gamma_slider.setValue(100)
        self._update_values()
        if self.osd_callback:
            self.osd_callback("Warna Video: Default")


class SubtitleStyleDialog(QDialog):
    def __init__(self, engine=None, osd_callback=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.osd_callback = osd_callback
        self.setWindowTitle("Pengaturan Subtitle")
        self.setFixedSize(380, 220)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        self.size_spin = QSpinBox()
        self.size_spin.setRange(12, 60)
        default_size = 24
        if self.engine and "sub_size" in getattr(self.engine, "config_data", {}):
            default_size = int(self.engine.config_data["sub_size"])
        self.size_spin.setValue(default_size)
        form.addRow("Ukuran Huruf:", self.size_spin)

        self.color_combo = QComboBox()
        self.color_combo.addItem("Putih (Default)", "#FFFFFF")
        self.color_combo.addItem("Kuning", "#FACC15")
        self.color_combo.addItem("Abu-abu Terang", "#D4D4D8")
        self.color_combo.addItem("Biru Muda", "#93C5FD")

        if self.engine and "sub_color" in getattr(self.engine, "config_data", {}):
            saved_col = self.engine.config_data["sub_color"]
            for i in range(self.color_combo.count()):
                if self.color_combo.itemText(i) == saved_col or self.color_combo.itemData(i) == saved_col:
                    self.color_combo.setCurrentIndex(i)
                    break
        form.addRow("Warna Teks:", self.color_combo)

        self.outline_chk = QCheckBox("Gunakan Outline Hitam")
        default_outline = True
        if self.engine and "sub_outline" in getattr(self.engine, "config_data", {}):
            default_outline = bool(self.engine.config_data["sub_outline"])
        self.outline_chk.setChecked(default_outline)
        form.addRow("Outline:", self.outline_chk)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        apply_btn = QPushButton("Simpan")
        apply_btn.setStyleSheet("background-color: #32323a; color: #ffffff; font-weight: 600; padding: 6px 16px; border: 1px solid #52525b; border-radius: 4px;")
        apply_btn.clicked.connect(self._apply)
        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.close)
        btn_box.addWidget(apply_btn)
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)

    def _apply(self):
        sz = self.size_spin.value()
        col = self.color_combo.currentText()
        outl = self.outline_chk.isChecked()
        if self.engine and hasattr(self.engine, "apply_subtitle_style"):
            self.engine.apply_subtitle_style(size=sz, color_name=col, outline=outl)
        if self.osd_callback:
            self.osd_callback(f"Subtitle: {col}, {sz}pt")
        self.accept()


class MediaInfoDialog(QDialog):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("Informasi Media & Codec")
        self.resize(520, 460)
        self.setMinimumSize(480, 400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._setup_ui()

    @staticmethod
    def format_file_size(b: int) -> str:
        if b >= 1024 * 1024 * 1024:
            return f"{b / (1024 * 1024 * 1024):.2f} GB ({b:,} bytes)"
        elif b >= 1024 * 1024:
            return f"{b / (1024 * 1024):.2f} MB ({b:,} bytes)"
        elif b >= 1024:
            return f"{b / 1024:.2f} KB ({b:,} bytes)"
        else:
            return f"{b} B"

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info = self.engine.get_media_info()
        dur_sec = info["duration"] // 1000
        mins, secs = divmod(dur_sec, 60)
        hrs, mins = divmod(mins, 60)
        dur_str = f"{hrs:02d}:{mins:02d}:{secs:02d}" if hrs > 0 else f"{mins:02d}:{secs:02d}"

        grp = QGroupBox("Properti File & Stream")
        grp_layout = QFormLayout(grp)
        grp_layout.setSpacing(8)

        src_path = str(info.get("source", "-"))
        source_label = QLabel(src_path)
        source_label.setWordWrap(True)
        grp_layout.addRow("Lokasi File:", source_label)

        file_size_str = "-"
        if src_path and os.path.isfile(src_path):
            try:
                b = os.path.getsize(src_path)
                file_size_str = self.format_file_size(b)
            except Exception:
                pass
        grp_layout.addRow("Ukuran File:", QLabel(file_size_str))
        grp_layout.addRow("Durasi:", QLabel(dur_str))

        w = info.get("video_width", 0)
        h = info.get("video_height", 0)
        res_str = f"{w} x {h}" if (w > 0 and h > 0) else "-"
        fps = self.engine.get_fps()
        fps_str = f"{fps:.2f} fps" if fps > 0 else "-"

        grp_layout.addRow("Resolusi Video:", QLabel(res_str))
        grp_layout.addRow("Frame Rate:", QLabel(fps_str))
        grp_layout.addRow("Codec Video:", QLabel(str(info.get("video_codec", "-"))))
        grp_layout.addRow("Format Warna:", QLabel(f"{info.get('bit_depth', '8-bit')} / {info.get('hdr_status', 'SDR')}"))
        grp_layout.addRow("Decoder:", QLabel(str(info.get("decoding_engine", "-"))))
        grp_layout.addRow("Codec Audio:", QLabel(str(info.get("audio_codec", "-"))))
        grp_layout.addRow("Saluran Audio:", QLabel(f"{info.get('channels', '-')} @ {info.get('sample_rate', '-')}"))

        audio_tracks = self.engine.get_audio_tracks()
        a_names = [f"Track {tid}: {name}" for tid, name in audio_tracks]
        grp_layout.addRow("Track Audio:", QLabel("\n".join(a_names) if a_names else "-"))

        sub_tracks = self.engine.get_subtitle_tracks()
        s_names = [f"Sub {sid}: {name}" for sid, name in sub_tracks]
        grp_layout.addRow("Track Subtitle:", QLabel("\n".join(s_names) if s_names else "-"))

        layout.addWidget(grp)

        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)


class YtDlpExtractWorker(QThread):
    extracted = pyqtSignal(str, str)  # stream_url, title
    failed = pyqtSignal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            import yt_dlp
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'socket_timeout': 10,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                if not info:
                    self.failed.emit("Tidak dapat menemukan stream yang valid.")
                    return
                stream_url = info.get('url')
                title = info.get('title') or self.url
                if not stream_url and 'formats' in info:
                    for f in reversed(info['formats']):
                        if f.get('url'):
                            stream_url = f.get('url')
                            break
                if stream_url:
                    self.extracted.emit(stream_url, title)
                else:
                    self.failed.emit("URL stream langsung tidak ditemukan.")
        except Exception as e:
            self.failed.emit(str(e))


class OpenStreamDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Buka Network Stream / URL")
        self.setFixedSize(500, 190)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.url = ""
        self.media_title = ""
        self.worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        lbl = QLabel("Masukkan URL Video / Stream (YouTube, Twitch, HTTP, RTSP, HLS/M3U8):")
        layout.addWidget(lbl)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://youtube.com/watch?v=... atau https://... atau rtsp://...")
        self.url_input.returnPressed.connect(self._accept_url)
        layout.addWidget(self.url_input)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        layout.addWidget(self.status_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate pulse
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        btn_row = QHBoxLayout()
        self.play_btn = QPushButton("Putar")
        self.play_btn.setStyleSheet("background-color: #32323a; color: #ffffff; font-weight: 600; padding: 6px 16px; border: 1px solid #52525b; border-radius: 4px;")
        self.play_btn.clicked.connect(self._accept_url)

        self.cancel_btn = QPushButton("Batal")
        self.cancel_btn.clicked.connect(self._on_cancel)

        btn_row.addWidget(self.play_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

    def _on_cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
        self.reject()

    def _accept_url(self):
        text = self.url_input.text().strip()
        if not text:
            return

        allowed_schemes = ("http://", "https://", "rtsp://", "rtp://", "mms://", "udp://")
        if not any(text.lower().startswith(s) for s in allowed_schemes):
            QMessageBox.warning(
                self,
                "URL Tidak Valid",
                "Gunakan URL dengan protokol: http://, https://, rtsp://, rtp://, mms://, atau udp://"
            )
            return

        # Check if URL looks like a web portal (YouTube, Twitch, Vimeo, TikTok, etc.)
        web_indicators = (
            "youtube.com", "youtu.be", "vimeo.com", "twitch.tv", "twitter.com",
            "x.com", "tiktok.com", "facebook.com", "dailymotion.com", "bilibili.tv"
        )
        is_web_video = any(ind in text.lower() for ind in web_indicators)
        is_direct_ext = any(text.lower().endswith(ext) for ext in (".mp4", ".mkv", ".m3u8", ".ts", ".mp3", ".webm", ".avi", ".mov"))

        if is_web_video or not is_direct_ext:
            self._start_yt_dlp_extraction(text)
        else:
            self.url = text
            self.media_title = ""
            self.accept()

    def _start_yt_dlp_extraction(self, raw_url: str):
        self.play_btn.setEnabled(False)
        self.url_input.setEnabled(False)
        self.status_lbl.setText("Mengekstrak stream online dengan yt-dlp... Mohon tunggu.")
        self.status_lbl.setStyleSheet("color: #38bdf8; font-size: 11px;")
        self.progress_bar.show()

        self.worker = YtDlpExtractWorker(raw_url, self)
        self.worker.extracted.connect(self._on_extracted)
        self.worker.failed.connect(lambda err: self._on_extract_failed(err, raw_url))
        self.worker.start()

    def _on_extracted(self, stream_url: str, title: str):
        self.url = stream_url
        self.media_title = title
        self.accept()

    def _on_extract_failed(self, error_msg: str, original_url: str):
        self.progress_bar.hide()
        self.play_btn.setEnabled(True)
        self.url_input.setEnabled(True)
        # Ask to fallback to raw URL
        ret = QMessageBox.question(
            self,
            "Ekstraksi yt-dlp Gagal",
            f"Tidak dapat mengekstrak stream online secara otomatis:\n{error_msg[:160]}\n\n"
            f"Apakah Anda ingin tetap mencoba memutar URL asli secara langsung dengan VLC core?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret == QMessageBox.StandardButton.Yes:
            self.url = original_url
            self.media_title = ""
            self.accept()
        else:
            self.status_lbl.setText("Ekstraksi dibatalkan.")
            self.status_lbl.setStyleSheet("color: #f87171; font-size: 11px;")


class OnlineSubtitlesDialog(QDialog):
    """Pencarian Subtitle Online & Drag-and-Drop Loader."""
    def __init__(self, engine, current_path: str = "", on_sub_loaded=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.current_path = current_path
        self.on_sub_loaded = on_sub_loaded
        self.setWindowTitle("Cari Subtitle Online")
        self.setFixedSize(500, 340)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setAcceptDrops(True)
        self._setup_ui()

    def _clean_movie_name(self, filename: str) -> str:
        base = os.path.splitext(os.path.basename(filename))[0]
        pattern = r"(?i)(\b(1080p|720p|2160p|4k|bluray|web-?dl|webrip|brrip|hdrip|x264|x265|hevc|aac|dts|yts|yify|rarbg|psa|eztv)\b.*)"
        cleaned = re.sub(pattern, "", base)
        cleaned = re.sub(r"[._\-+]+", " ", cleaned).strip()
        return cleaned or base

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        title_lbl = QLabel("<b>Pencarian & Pemasangan Subtitle</b>")
        title_lbl.setStyleSheet("font-size: 13px; color: #ffffff;")
        layout.addWidget(title_lbl)

        form = QFormLayout()
        default_query = self._clean_movie_name(self.current_path) if self.current_path else ""
        self.query_input = QLineEdit(default_query)
        self.query_input.setPlaceholderText("Nama Film atau Serial TV...")
        form.addRow("Judul Media:", self.query_input)
        layout.addLayout(form)

        # Provider Buttons
        prov_box = QGroupBox("Buka Pencarian di Portal Subtitle")
        prov_layout = QHBoxLayout(prov_box)
        prov_layout.setSpacing(8)

        btn_subdl = QPushButton("SubDL (ID/EN)")
        btn_subdl.setToolTip("Cari subtitle di SubDL.com")
        btn_subdl.clicked.connect(self._open_subdl)
        prov_layout.addWidget(btn_subdl)

        btn_subsource = QPushButton("SubSource")
        btn_subsource.setToolTip("Cari subtitle di SubSource.net")
        btn_subsource.clicked.connect(self._open_subsource)
        prov_layout.addWidget(btn_subsource)

        btn_opensub = QPushButton("OpenSubtitles")
        btn_opensub.setToolTip("Cari subtitle di OpenSubtitles.org")
        btn_opensub.clicked.connect(self._open_opensubtitles)
        prov_layout.addWidget(btn_opensub)

        layout.addWidget(prov_box)

        # Drop Zone / Instructions
        self.drop_label = QLabel(
            "📁 <b>Tarik & Lepas (Drag & Drop)</b> file <code>.srt</code> atau <code>.ass</code> ke sini<br>"
            "atau klik tombol di bawah untuk langsung memasang ke video."
        )
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setStyleSheet(
            "border: 2px dashed #40404a; border-radius: 6px; padding: 16px; "
            "color: #a1a1aa; background-color: #1a1a20; font-size: 11px;"
        )
        layout.addWidget(self.drop_label)

        btn_row = QHBoxLayout()
        browse_btn = QPushButton("Pilih File Subtitle Manual...")
        browse_btn.clicked.connect(self._browse_manual)
        btn_row.addWidget(browse_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _open_subdl(self):
        q = urllib.parse.quote(self.query_input.text().strip())
        if q:
            QDesktopServices.openUrl(QUrl(f"https://subdl.com/search/{q}"))

    def _open_subsource(self):
        q = urllib.parse.quote(self.query_input.text().strip())
        if q:
            QDesktopServices.openUrl(QUrl(f"https://subsource.net/search?query={q}"))

    def _open_opensubtitles(self):
        q = urllib.parse.quote(self.query_input.text().strip())
        if q:
            QDesktopServices.openUrl(QUrl(f"https://www.opensubtitles.org/id/search2/sublanguageid-all/moviename-{q}"))

    def _browse_manual(self):
        sub_path, _ = QFileDialog.getOpenFileName(
            self, "Pilih Subtitle", "", "Subtitles (*.srt *.ass *.vtt *.sub);;All Files (*.*)"
        )
        if sub_path:
            self._apply_subtitle(sub_path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            fp = url.toLocalFile()
            if os.path.isfile(fp) and fp.lower().endswith((".srt", ".ass", ".vtt", ".sub")):
                self._apply_subtitle(fp)
                event.acceptProposedAction()
                return

    def _apply_subtitle(self, sub_path: str):
        if self.engine:
            ok = self.engine.add_subtitle_file(sub_path)
            if self.on_sub_loaded:
                self.on_sub_loaded(sub_path, ok)
            self.accept()


class ContinueWatchingDialog(QDialog):
    """Playback History & Resume Dialog (Ctrl+Y)."""
    def __init__(self, engine, on_play_callback=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.on_play_callback = on_play_callback
        self.setWindowTitle("Riwayat Tontonan (Ctrl+Y)")
        self.resize(640, 460)
        self.setMinimumSize(520, 360)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._setup_ui()
        self._load_items()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        header_layout = QHBoxLayout()
        header_title = QLabel("<b>Riwayat Tontonan</b>")
        header_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #ffffff;")
        header_layout.addWidget(header_title)

        header_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Cari riwayat...")
        self.search_input.setFixedWidth(200)
        self.search_input.textChanged.connect(self._filter_items)
        header_layout.addWidget(self.search_input)
        layout.addLayout(header_layout)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: 1px solid #2e2e36; border-radius: 4px; background-color: #141417; }")

        self.card_container = QWidget()
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setSpacing(8)
        self.card_layout.setContentsMargins(8, 8, 8, 8)
        self.card_layout.addStretch()
        self.scroll.setWidget(self.card_container)
        layout.addWidget(self.scroll)

        btn_layout = QHBoxLayout()

        clear_btn = QPushButton("Hapus Semua Riwayat")
        clear_btn.clicked.connect(self._clear_all)
        btn_layout.addWidget(clear_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _format_ms(self, ms: int) -> str:
        sec = max(0, ms // 1000)
        m, s = divmod(sec, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _load_items(self):
        while self.card_layout.count() > 1:
            item = self.card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        items = self.engine.get_rich_history()
        query = self.search_input.text().strip().lower()

        matched = 0
        for data in items:
            title = data.get("title") or os.path.basename(data.get("mrl", ""))
            mrl = data.get("mrl", "")
            if query and query not in title.lower() and query not in mrl.lower():
                continue

            card = self._create_card(data)
            self.card_layout.insertWidget(self.card_layout.count() - 1, card)
            matched += 1

        if matched == 0:
            empty_lbl = QLabel("Belum ada riwayat tontonan." if not query else "Tidak ada hasil yang cocok.")
            empty_lbl.setStyleSheet("color: #71717a; padding: 30px; font-size: 12px;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.card_layout.insertWidget(0, empty_lbl)

    def _filter_items(self):
        self._load_items()

    def _create_card(self, data: dict) -> QWidget:
        mrl = data.get("mrl", "")
        title = data.get("title") or os.path.basename(mrl)
        pos_ms = data.get("position_ms", 0)
        dur_ms = data.get("duration_ms", 0)
        pct = data.get("percentage", 0.0)
        ts = data.get("timestamp", 0)

        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: #1c1c21;
                border: 1px solid #2e2e36;
                border-radius: 4px;
            }
            QWidget:hover {
                border-color: #464652;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(12, 8, 12, 8)
        c_layout.setSpacing(6)

        top_row = QHBoxLayout()
        t_label = QLabel(f"<b>{title}</b>")
        t_label.setWordWrap(True)
        t_label.setStyleSheet("color: #ffffff; font-size: 12px; border: none; background: transparent;")
        top_row.addWidget(t_label, stretch=1)

        if ts > 0:
            dt_str = datetime.datetime.fromtimestamp(ts).strftime("%d %b %Y, %H:%M")
            d_label = QLabel(dt_str)
            d_label.setStyleSheet("color: #71717a; font-size: 11px; border: none; background: transparent;")
            top_row.addWidget(d_label)
        c_layout.addLayout(top_row)

        p_label = QLabel(mrl)
        p_label.setWordWrap(True)
        p_label.setStyleSheet("color: #71717a; font-size: 10px; border: none; background: transparent;")
        c_layout.addWidget(p_label)

        prog_row = QHBoxLayout()
        prog_bar = QProgressBar()
        prog_bar.setRange(0, 100)
        prog_bar.setValue(int(pct))
        prog_bar.setTextVisible(False)
        prog_bar.setFixedHeight(6)
        prog_bar.setStyleSheet("""
            QProgressBar {
                background-color: #27272e;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #d4d4d8;
                border-radius: 3px;
            }
        """)
        prog_row.addWidget(prog_bar, stretch=1)

        time_str = self._format_ms(pos_ms)
        if dur_ms > 0:
            time_info = f"{time_str} / {self._format_ms(dur_ms)}"
        else:
            time_info = time_str
        time_lbl = QLabel(time_info)
        time_lbl.setStyleSheet("color: #a1a1aa; font-size: 11px; border: none; background: transparent;")
        prog_row.addWidget(time_lbl)
        c_layout.addLayout(prog_row)

        act_row = QHBoxLayout()
        act_row.addStretch()

        resume_btn = QPushButton("Lanjutkan")
        resume_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        resume_btn.setStyleSheet("""
            QPushButton {
                background-color: #32323a;
                color: #ffffff;
                font-weight: 600;
                border: 1px solid #52525b;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #3f3f48;
            }
        """)
        resume_btn.clicked.connect(lambda chk, m=mrl, p=pos_ms: self._on_resume(m, p))
        act_row.addWidget(resume_btn)

        restart_btn = QPushButton("Mulai dari Awal")
        restart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        restart_btn.setStyleSheet("""
            QPushButton {
                background-color: #242429;
                color: #d4d4d8;
                border: 1px solid #32323a;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #2f2f36;
                color: #ffffff;
            }
        """)
        restart_btn.clicked.connect(lambda chk, m=mrl: self._on_resume(m, 0))
        act_row.addWidget(restart_btn)

        del_btn = QPushButton("Hapus")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #9ca3af;
                border: 1px solid #32323a;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #2f2f36;
                color: #ffffff;
            }
        """)
        del_btn.clicked.connect(lambda chk, m=mrl: self._on_delete(m))
        act_row.addWidget(del_btn)

        c_layout.addLayout(act_row)
        return card

    def _on_resume(self, mrl: str, pos_ms: int):
        self.close()
        if self.on_play_callback:
            self.on_play_callback(mrl, pos_ms)

    def _on_delete(self, mrl: str):
        self.engine.clear_history_for_media(mrl)
        self._load_items()

    def _clear_all(self):
        reply = QMessageBox.question(
            self,
            "Konfirmasi",
            "Hapus seluruh riwayat tontonan?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.engine.clear_all_history()
            self._load_items()
