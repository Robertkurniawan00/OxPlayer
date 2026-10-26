"""
OXPlayer side drawer playlist panel.
Features Drag & Drop, quick search, item ordering, shuffle, and repeat modes.
Supports comprehensive media file extensions.
"""

import os
import random
from typing import List, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLineEdit, QLabel, QFileDialog, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent


# Comprehensive Video & Audio Codec Extensions supported by OXPlayer
SUPPORTED_MEDIA_EXTENSIONS = {
    # Video - Modern High-Efficiency (AV1, HEVC/H.265, VP9, H.264, WebM)
    ".mp4", ".mkv", ".webm", ".m4v",
    # Video - Broadcast & Transport Streams (MPEG-2, AVC, HEVC)
    ".ts", ".mts", ".m2ts", ".tp", ".trp", ".vob", ".mpg", ".mpeg", ".m1v", ".m2v", ".wtv", ".dvr-ms", ".evo",
    # Video - Professional Production (ProRes, DNxHD, QuickTime, MXF)
    ".mov", ".qt", ".mxf",
    # Video - Traditional & Legacy (DivX, Xvid, WMV, VC-1, RealVideo, Flash, Bink)
    ".avi", ".divx", ".xvid", ".wmv", ".asf", ".flv", ".f4v", ".rm", ".rmvb", ".3gp", ".3g2", ".ogv", ".bik", ".smk",
    # Audio - Surround & Spatial (Dolby TrueHD, Dolby Digital AC-3, E-AC-3, DTS, DTS-HD, DTS:X)
    ".ac3", ".eac3", ".dts", ".dtshd", ".thd",
    # Audio - High-Resolution Lossless (FLAC, ALAC, WAV, APE, WavPack, TTA, AIFF)
    ".flac", ".alac", ".wav", ".ape", ".wv", ".tta", ".aiff", ".aif",
    # Audio - Streaming & Music (MP3, AAC, Opus, Ogg Vorbis, WMA, MPC)
    ".mp3", ".aac", ".m4a", ".opus", ".ogg", ".oga", ".wma", ".mpc", ".amr", ".mid", ".midi",
    # Playlists
    ".m3u", ".m3u8", ".pls", ".xspf"
}


import re


def natural_sort_key(text: str):
    """Natural alphanumeric sorting key (e.g. Ep 1, Ep 2, Ep 10 instead of Ep 1, Ep 10, Ep 2)."""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]


class PlaylistItem:
    def __init__(self, path: str, title: str = ""):
        self.path = path
        self.title = title or os.path.basename(path)


class PlaylistWidget(QWidget):
    """
    Side-drawer playlist panel.
    Emits track_selected(str) when an item is chosen to play.
    """
    track_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_win = parent
        self.setObjectName("PlaylistWidget")
        self.setFixedWidth(290)
        self.setAcceptDrops(True)

        self.items: List[PlaylistItem] = []
        self.current_index = -1
        self.repeat_mode = 0  # 0: Off, 1: Repeat All, 2: Repeat One
        self.shuffle_mode = False
        self._needs_ui_refresh = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header with Title and item count
        header = QHBoxLayout()
        self.header_title = QLabel("Daftar Putar")
        self.header_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #ffffff;")
        self.count_label = QLabel("(0)")
        self.count_label.setStyleSheet("color: #8f95a3; font-size: 11px;")
        header.addWidget(self.header_title)
        header.addWidget(self.count_label)
        header.addStretch()

        # Close Drawer Button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setStyleSheet("border: none; background: transparent; font-size: 13px; color: #a1a1aa; border-radius: 4px;")
        close_btn.setToolTip("Tutup Playlist (F8)")
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Search bar
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Cari judul file...")
        self.search_box.textChanged.connect(self._filter_items)
        layout.addWidget(self.search_box)

        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.list_widget)

        # Controls rows (Row 1: Add File, Add Folder, Clear; Row 2: Repeat, Shuffle)
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(6)

        add_file_btn = QPushButton("+ File")
        add_file_btn.setToolTip("Tambah File Media ke Daftar Putar")
        add_file_btn.clicked.connect(self._open_add_files_dialog)
        row1_layout.addWidget(add_file_btn)

        add_dir_btn = QPushButton("+ Folder")
        add_dir_btn.setToolTip("Tambah Folder Media ke Daftar Putar")
        add_dir_btn.clicked.connect(self._open_add_folder_dialog)
        row1_layout.addWidget(add_dir_btn)

        clear_btn = QPushButton("🗑 Hapus")
        clear_btn.setToolTip("Bersihkan Seluruh Isi Daftar Putar")
        clear_btn.clicked.connect(self.clear_playlist)
        row1_layout.addWidget(clear_btn)
        layout.addLayout(row1_layout)

        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(6)

        self.repeat_btn = QPushButton("🔁 Ulang: Mati")
        self.repeat_btn.setToolTip("Mode Pengulangan: Mati")
        self.repeat_btn.clicked.connect(self._toggle_repeat)
        row2_layout.addWidget(self.repeat_btn)

        self.shuffle_btn = QPushButton("🔀 Acak: Mati")
        self.shuffle_btn.setToolTip("Mode Acak: Mati")
        self.shuffle_btn.clicked.connect(self._toggle_shuffle)
        row2_layout.addWidget(self.shuffle_btn)
        layout.addLayout(row2_layout)

    # --- Drag & Drop ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        paths = []
        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if os.path.exists(local_path):
                paths.append(local_path)
        if paths:
            self.add_paths(paths)
        event.acceptProposedAction()

    # --- Item Management ---
    def add_paths(self, paths: List[str], auto_play: bool = True):
        """Adds files, streaming URLs, or scans directories recursively for supported media formats."""
        added_count = 0
        allowed_schemes = ("http://", "https://", "rtsp://", "rtp://", "mms://", "udp://")
        for p in paths:
            if not p:
                continue
            p_str = str(p).strip()
            if any(p_str.lower().startswith(s) for s in allowed_schemes):
                title = os.path.basename(p_str.split("?")[0]) or p_str
                self.items.append(PlaylistItem(p_str, title))
                added_count += 1
            elif os.path.isdir(p_str):
                for root, _, files in os.walk(p_str):
                    for f in sorted(files, key=natural_sort_key):
                        ext = os.path.splitext(f)[1].lower()
                        if ext in SUPPORTED_MEDIA_EXTENSIONS and ext not in {".srt", ".ass", ".vtt", ".sub"}:
                            full = os.path.join(root, f)
                            self.items.append(PlaylistItem(full))
                            added_count += 1
            elif os.path.isfile(p_str):
                ext = os.path.splitext(p_str)[1].lower()
                # Skip standalone subtitle files
                if ext in {".srt", ".ass", ".vtt", ".sub"}:
                    continue
                # Parse M3U playlist if added
                if ext in {".m3u", ".m3u8"}:
                    self._parse_m3u(p_str)
                else:
                    self.items.append(PlaylistItem(p_str))
                    added_count += 1

        self._refresh_list_view()
        if auto_play and self.current_index == -1 and self.items:
            self.play_index(0)

    def sync_playing_path(self, path: str):
        """Synchronizes current_index with the actively playing media path and highlights it."""
        if not path:
            return
        is_url = path.lower().startswith(("http://", "https://", "rtsp://", "rtp://", "mms://", "udp://"))
        norm_target = path if is_url else os.path.normcase(os.path.abspath(path))
        found_idx = -1
        for i, item in enumerate(self.items):
            item_is_url = item.path.lower().startswith(("http://", "https://", "rtsp://", "rtp://", "mms://", "udp://"))
            item_norm = item.path if item_is_url else os.path.normcase(os.path.abspath(item.path))
            if item_norm == norm_target:
                found_idx = i
                break
        if found_idx != -1:
            self.current_index = found_idx
            self._refresh_list_view()

    def queue_folder_siblings(self, file_path: str) -> int:
        """
        Automatically discovers all supported media files in the same folder as file_path,
        sorts them in natural episode order, and queues them in the playlist.
        Returns the total number of sibling files queued.
        """
        if not file_path or not os.path.isfile(file_path):
            return 0
        folder = os.path.dirname(os.path.abspath(file_path))
        media_exts = SUPPORTED_MEDIA_EXTENSIONS - {".srt", ".ass", ".vtt", ".sub", ".m3u", ".m3u8", ".pls", ".xspf"}
        sibling_paths = []
        try:
            with os.scandir(folder) as it:
                for entry in it:
                    if entry.is_file():
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in media_exts:
                            sibling_paths.append(entry.path)
        except Exception:
            return 0

        if not sibling_paths:
            return 0

        sibling_paths.sort(key=lambda p: natural_sort_key(os.path.basename(p)))

        existing_norms = {
            os.path.normcase(os.path.abspath(it.path))
            for it in self.items
            if not it.path.lower().startswith(("http://", "https://", "rtsp://"))
        }
        target_norm = os.path.normcase(os.path.abspath(file_path))

        # Populate playlist with folder episodes if playlist has <=1 item or doesn't contain this folder
        if len(self.items) <= 1 or target_norm not in existing_norms:
            self.items = [PlaylistItem(p) for p in sibling_paths]
            self.sync_playing_path(file_path)
            return len(sibling_paths)
        else:
            self.sync_playing_path(file_path)
            return len(self.items)

    def _parse_m3u(self, m3u_path: str):
        try:
            with open(m3u_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if os.path.exists(line):
                            self.items.append(PlaylistItem(line))
                        elif line.startswith(("http://", "https://", "rtsp://")):
                            self.items.append(PlaylistItem(line, os.path.basename(line) or line))
        except Exception:
            pass

    def _refresh_list_view(self):
        self.count_label.setText(f"({len(self.items)})")
        if not self.isVisible():
            self._needs_ui_refresh = True
            return
        self._needs_ui_refresh = False
        query = self.search_box.text().lower()
        self.list_widget.clear()

        for idx, item in enumerate(self.items):
            if query and query not in item.title.lower():
                continue
            prefix = "▶ " if idx == self.current_index else f"{idx + 1}. "
            list_item = QListWidgetItem(f"{prefix}{item.title}")
            list_item.setData(Qt.ItemDataRole.UserRole, idx)
            list_item.setToolTip(f"{item.title}\n{item.path}")
            if idx == self.current_index:
                list_item.setForeground(Qt.GlobalColor.white)
                font = list_item.font()
                font.setBold(True)
                list_item.setFont(font)
            self.list_widget.addItem(list_item)

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, "_needs_ui_refresh", False):
            self._needs_ui_refresh = False
            self._refresh_list_view()

    def _filter_items(self):
        self._refresh_list_view()

    def _on_item_double_clicked(self, list_item: QListWidgetItem):
        idx = list_item.data(Qt.ItemDataRole.UserRole)
        if idx is not None and 0 <= idx < len(self.items):
            self.play_index(idx)

    def play_index(self, index: int):
        if 0 <= index < len(self.items):
            self.current_index = index
            self._refresh_list_view()
            self.track_selected.emit(self.items[index].path)

    def get_next_item(self) -> Optional[PlaylistItem]:
        """Returns the next PlaylistItem, or None if at the end of queue without repeat."""
        if not self.items or self.current_index < 0:
            return None
        if self.repeat_mode == 2:  # Repeat One
            return self.items[self.current_index]
        next_idx = self.current_index + 1
        if next_idx < len(self.items):
            return self.items[next_idx]
        if self.repeat_mode == 1 and len(self.items) > 1:  # Repeat All
            return self.items[0]
        return None

    def play_next(self):
        if not self.items:
            return
        if self.repeat_mode == 2:  # Repeat One
            self.play_index(self.current_index)
            return

        if self.shuffle_mode:
            next_idx = random.randint(0, len(self.items) - 1)
        else:
            next_idx = self.current_index + 1

        if next_idx >= len(self.items):
            if self.repeat_mode == 1:  # Repeat All
                next_idx = 0
            else:
                return  # End of playlist

        self.play_index(next_idx)

    def play_previous(self):
        if not self.items:
            return
        prev_idx = self.current_index - 1
        if prev_idx < 0:
            prev_idx = len(self.items) - 1 if self.repeat_mode == 1 else 0
        self.play_index(prev_idx)

    def clear_playlist(self):
        self.items.clear()
        self.current_index = -1
        self._refresh_list_view()

    def _toggle_repeat(self):
        self.repeat_mode = (self.repeat_mode + 1) % 3
        modes = ["Pengulangan: Mati", "Pengulangan: Semua File", "Pengulangan: Satu File"]
        labels = ["🔁 Ulang: Mati", "🔁 Ulang: Semua", "🔂 Ulang: 1"]
        self.repeat_btn.setText(labels[self.repeat_mode])
        self.repeat_btn.setToolTip(modes[self.repeat_mode])
        if self.main_win and hasattr(self.main_win, "osd"):
            self.main_win.osd.show_message(modes[self.repeat_mode])

    def _toggle_shuffle(self):
        self.shuffle_mode = not self.shuffle_mode
        self.shuffle_btn.setText("🔀 Acak: Aktif" if self.shuffle_mode else "🔀 Acak: Mati")
        self.shuffle_btn.setToolTip(f"Mode Acak: {'Aktif' if self.shuffle_mode else 'Mati'}")
        if self.main_win and hasattr(self.main_win, "osd"):
            self.main_win.osd.show_message(f"Acak: {'Aktif' if self.shuffle_mode else 'Mati'}")

    def _open_add_files_dialog(self):
        main_win = getattr(self, "main_win", None)
        if main_win:
            if hasattr(main_win, "_hide_overlays_for_dialog"):
                main_win._hide_overlays_for_dialog()
            elif hasattr(main_win, "floating_dock"):
                main_win.floating_dock.hide()
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
        files, _ = QFileDialog.getOpenFileNames(self, "Pilih File Media", "", filter_str)
        if files:
            self.add_paths(files)

    def _open_add_folder_dialog(self):
        main_win = getattr(self, "main_win", None)
        if main_win:
            if hasattr(main_win, "_hide_overlays_for_dialog"):
                main_win._hide_overlays_for_dialog()
            elif hasattr(main_win, "floating_dock"):
                main_win.floating_dock.hide()
        folder = QFileDialog.getExistingDirectory(self, "Pilih Folder Media")
        if folder:
            self.add_paths([folder])

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        play_act = menu.addAction("Putar")
        remove_act = menu.addAction("Hapus dari Daftar")
        
        act = menu.exec(self.list_widget.mapToGlobal(pos))
        if act == play_act:
            self.play_index(idx)
        elif act == remove_act:
            if idx == self.current_index:
                del self.items[idx]
                if self.current_index >= len(self.items):
                    self.current_index = len(self.items) - 1
            elif idx < self.current_index:
                del self.items[idx]
                self.current_index -= 1
            else:
                del self.items[idx]
            self._refresh_list_view()
