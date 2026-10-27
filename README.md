<div align="center">

# OXPlayer

**Modern, Ultra-Fast, Hardware-Accelerated Multimedia Player for Windows**

[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python)](https://python.org)
[![Framework](https://img.shields.io/badge/GUI-PyQt6-green?logo=qt)](https://riverbankcomputing.com/software/pyqt/)
[![Engine](https://img.shields.io/badge/Engine-LibVLC%20Direct3D-orange?logo=vlc)](https://www.videolan.org/vlc/libvlc.html)
[![Platform](https://img.shields.io/badge/Platform-Windows%207%20%7C%208%20%7C%2010%20%7C%2011-0078D6?logo=windows)](https://microsoft.com/windows)
[![License](https://img.shields.io/badge/License-GPLv3-red.svg)](LICENSE)

<br/>

<img src="assets/app_logo.png" alt="OXPlayer Logo" width="180"/>

<p align="center">
  <b>OXPlayer</b> is a standalone, lightweight, and modern media player built on <b>PyQt6</b> and powered by the <b>LibVLC</b> engine. Engineered with native Direct3D rendering, responsive floating controls, automatic episode discovery, and true aspect ratio preservation.
</p>

[Fitur Utama](#-fitur-utama) • [Instalasi](#-instalasi) • [Jalankan dari Source](#-menjalankan-dari-source-code) • [Shortcut Keyboard](#-shortcut-keyboard) • [Kompilasi Executable](#-kompilasi-executable--installer) • [Lisensi](#-lisensi)

</div>

---

## 🌟 Fitur Utama (Key Features)

### 1. Hardware Accelerated Rendering & Native Aspect Ratio
- **LibVLC Direct3D Backend**: Akselerasi hardware GPU penuh untuk pemutaran video beresolusi hingga 4K/8K tanpa stuttering.
- **True Aspect Ratio Preservation**: Rasio aspek video (16:9, 4:3, 21:9, maupun video vertikal 9:16) dipertahankan secara akurat dengan teknik letterboxing / pillarboxing otomatis tanpa stretching (distorsi gambar).
- **Rasio Fleksibel & Rotasi**: Pilihan aspek kustom (*Original, 16:9, 4:3, 21:9, 1:1, Fill*), rotasi layar (0°, 90°, 180°, 270°), dan horizontal/vertical flip.

### 2. Modern & Responsive Floating UI
- **Edge-to-Edge Floating Dock**: Dock kontrol pemutaran modern transparan yang otomatis menyesuaikan ukuran jendela pemutar.
- **Adaptive Responsive Layout**: Tombol sekunder (slider volume, kecepatan putar, track buttons) otomatis tersusun rapi atau disembunyikan saat jendela dipersempit atau saat memutar video berformat portrait/vertikal, mencegah tabrakan antarelemen UI.
- **Zero-Occlusion Overlays**: Banner resume tontonan (*Resume Watching*) dan notifikasi episode berikutnya (*Next Episode*) dibangun dengan arsitektur top-level frameless window sehingga tidak pernah tertutup oleh hardware canvas Direct3D.

### 3. Picture-in-Picture (PiP) Mode
- Jendela PiP mengambang (*Always on Top*) dengan kontrol minimalis berikon modern (Play/Pause, Seek ±5s, Mute, Restore, Close) dan handle resize di pojok kanan bawah.

### 4. Auto Playlist & Next-Episode Discovery
- **Folder Siblings Auto-Discovery**: Saat membuka 1 episode file video, OXPlayer otomatis mendeteksi dan mengurutkan seluruh episode serial dalam folder yang sama secara *natural sorting*.
- **Playlist Drawer**: Fitur pencarian cepat, drag & drop, mode Repeat (Mati, Semua, 1 File), dan Shuffle (Acak).
- **Next Episode Notification**: Banner notifikasi interaktif yang muncul 30 detik sebelum video selesai untuk berpindah ke episode berikutnya dengan satu klik atau tombol `N`.

### 5. Audio & Video Enhancements
- **10-Band Graphic Equalizer**: Dilengkapi preset audio populer (Rock, Pop, Bass Boost, Vocal, Classical, dll.).
- **Spatial Audio & Volume Boost**: Dukungan audio spasial dan penguatan volume audio hingga 125% - 200%.
- **Live Video Adjustments**: Pengaturan real-time untuk Brightness, Contrast, Saturation, Gamma, dan Hue.
- **Audio & Subtitle Track Selection**: Mendukung multi-audio track, file subtitle eksternal (.srt, .ass, .vtt), serta sinkronisasi delay audio/subtitle.

### 6. Bookmark, History & Network Streaming
- **Bookmark Manager (B)**: Simpan timestamp penting dalam video dengan catatan kustom.
- **Continue Watching (Ctrl+Y)**: Riwayat tontonan kaya dengan kartu visual, progress bar, dan fitur pencarian.
- **Network Stream (Ctrl+U)**: Putar streaming langsung dari URL (HTTP, HTTPS, RTSP, HLS, UDP).

---

## 📥 Instalasi (Windows Installer)

Bagi pengguna akhir di Windows 7, 8, 8.1, 10, dan 11 (64-bit):

1. Unduh **`OXPlayer_Setup.exe`** dari tab [Releases](../../releases).
2. Jalankan file `OXPlayer_Setup.exe`.
3. Wizard instalasi akan memandu Anda untuk:
   - Memilih lokasi instalasi.
   - Membuat shortcut di Desktop dan Start Menu.
   - Mengasosiasikan file video & audio dengan ikon resmi OXPlayer.
4. Selesai! Buka OXPlayer dari shortcut Desktop atau menu Start.

---

## 🛠 Menjalankan dari Source Code

### Prasyarat:
- Python 3.10, 3.11, atau 3.12 (64-bit)
- Sistem Operasi Windows 7 / 8 / 10 / 11
- VLC Media Player 64-bit terpasang di sistem (atau sediakan runtime `libvlc.dll` di folder `core_bin/`)

### Langkah-langkah:

1. **Clone Repositori**:
   ```bash
   git clone https://github.com/Robertkurniawan00/OxPlayer.git
   cd OxPlayer
   ```

2. **Buat & Aktifkan Virtual Environment (Opsional tapi disarankan)**:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. **Install Dependensi**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Jalankan OXPlayer**:
   ```bash
   python main.py
   ```

---

## ⌨️ Shortcut Keyboard (Cheat Sheet)

| Shortcut | Fungsi |
|---|---|
| `Spasi` / `K` | Putar / Jeda (Play / Pause) |
| `F` / `Alt + Enter` | Layar Penuh (Toggle Fullscreen) |
| `Esc` | Keluar dari Layar Penuh / Mode PiP |
| `P` | Mode Picture-in-Picture (PiP) |
| `F8` | Buka / Tutup Daftar Putar (Playlist) |
| `M` | Bisu / Bunyikan Suara (Mute / Unmute) |
| `Panah Atas` / `Panah Bawah` | Tambah / Kurangi Volume (±5%) |
| `Panah Kiri` / `Panah Kanan` | Mundur / Maju 5 Detik |
| `Ctrl + Panah Kiri` / `Kanan` | Mundur / Maju 1 Menit |
| `Shift + Panah Kiri` / `Kanan`| Mundur / Maju 10 Detik |
| `[` / `]` | Perlambat / Percepat Playback Speed (±0.1x) |
| `Backspace` | Reset Playback Speed ke Normal (1.0x) |
| `N` / `Shift + P` | Episode Selanjutnya / Sebelumnya |
| `A` | Ganti Rasio Aspek (Original, 16:9, 4:3, dll.) |
| `R` | Rotasi Video (0° → 90° → 180° → 270°) |
| `S` | Siklus Track Subtitle |
| `B` | Buka Manajer Bookmark |
| `Ctrl + G` | Lompat ke Waktu (*Jump to Time*) |
| `Ctrl + A` | Efek Audio & Equalizer 10-Band |
| `Ctrl + J` | Informasi Media & Codec |
| `Ctrl + Y` | Riwayat Tontonan (*Continue Watching*) |
| `Ctrl + U` | Buka Network Stream URL |
| `Ctrl + O` | Buka File Media |
| `Ctrl + Shift + O` | Buka Folder Media |
| `F1` | Bantuan Pintasan Keyboard |

---

## 📦 Kompilasi Executable & Installer

OXPlayer menyertakan skrip otomatisasi build lengkap dengan PyInstaller:

```bash
# Menghasilkan Standalone App dan Setup Installer:
python build_exe.py
```

Skrip ini akan memproduksi:
1. **Standalone Core Application**: `dist/OXPlayer/OXPlayer.exe` (lengkap dengan decoding runtime).
2. **Single-File Setup Installer**: `dist/OXPlayer_Setup.exe` (dan `OXPlayer_Setup.exe` di root).

---

## 📂 Struktur Repositori

```text
OXPlayer/
├── .github/workflows/     # GitHub Actions CI Workflow
├── assets/                # Icon aplikasi, logo, manifest kompatibilitas Windows
├── src/                   # Source code utama modul OXPlayer
│   ├── __init__.py
│   ├── dialogs.py         # Dialog pengaturan audio, video, bookmark, riwayat
│   ├── engine.py          # Wrapper inti LibVLC & sinkronisasi playback
│   ├── main_window.py     # GUI jendela utama, menu bar, floating dock
│   ├── next_episode_banner.py  # Banner frameless notifikasi episode lanjutan
│   ├── osd.py             # On-Screen Display (OSD) feedback overlay
│   ├── pip_window.py      # Jendela mengambang Picture-in-Picture
│   ├── playlist.py        # Widget drawer daftar putar & auto-discovery
│   ├── resume_banner.py   # Banner interaktif pemulihan posisi terakhir
│   └── styles.py          # Modern dark stylesheet (QSS)
├── tools/                 # Skrip utilitas perbaikan shortcut & Smart App Control
├── build_exe.py           # Skrip otomatisasi packaging PyInstaller
├── installer.py           # Wizard installer GUI Windows
├── main.py                # Entry point aplikasi
├── requirements.txt       # Daftar dependensi Python
├── LICENSE                # Lisensi GNU General Public License v3.0
├── README.md              # Dokumentasi proyek
└── RELEASE_GUIDE.md       # Panduan upload ke GitHub & GitHub Releases
```

---

## 📄 Lisensi

OXPlayer didistribusikan di bawah lisensi **GNU General Public License v3.0 (GPLv3)**. Lihat file [LICENSE](LICENSE) untuk informasi lebih lanjut.

---

<div align="center">
  <sub>Dibangun dengan ❤️ menggunakan Python, PyQt6, dan LibVLC.</sub>
</div>
