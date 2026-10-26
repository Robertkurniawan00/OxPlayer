# Panduan Lengkap Upload ke GitHub (OXPlayer)

Panduan ini menjelaskan cara mengunggah seluruh kode sumber dan aset OXPlayer ke GitHub serta mempublikasikan installer `OXPlayer_Setup.exe` pada halaman **Releases**.

---

## Langkah 1: Buat Repositori Baru di GitHub

1. Buka browser dan kunjungi [GitHub New Repository](https://github.com/new).
2. Isi nama repositori: `OXPlayer` (atau sesuai keinginan Anda).
3. Pilih opsi **Public** (atau Private).
4. **PENTING**: Jangan centang *"Add a README file"*, *"Add .gitignore"*, atau *"Choose a license"*, karena file-file tersebut sudah lengkap disediakan di folder ini.
5. Klik **Create repository**.

---

## Langkah 2: Inisialisasi Git dan Push Kode Sumber

Buka terminal (PowerShell atau Command Prompt) di dalam folder `github_upload`:

```powershell
# 1. Pindah ke folder github_upload
cd "D:\Project FIX\media player\github_upload"

# 2. Inisialisasi repositori Git lokal
git init

# 3. Ubah branch default menjadi main
git branch -M main

# 4. Tambahkan seluruh file ke staging area
git add .

# 5. Buat commit pertama
git commit -m "feat: initial commit of OXPlayer with modern UI/UX, Direct3D HWND fix, and LibVLC engine"

# 6. Hubungkan ke repositori GitHub Anda (ganti <username> dan <repo> dengan milik Anda)
git remote add origin https://github.com/<username>/OXPlayer.git

# 7. Unggah kode ke GitHub
git push -u origin main
```

> [!NOTE]
> File `OXPlayer_Setup.exe` yang berada di dalam folder `RELEASE_ASSETS/` secara otomatis diabaikan oleh `.gitignore` agar `git push` tidak gagal karena batasan ukuran file 100 MB di GitHub.

---

## Langkah 3: Publikasikan Installer di GitHub Releases

Agar pengguna dapat langsung mengunduh file `.exe` yang siap pakai:

1. Buka halaman repositori Anda di GitHub melalui browser.
2. Pada panel sebelah kanan, klik **Releases** -> **Draft a new release** (atau buat release baru).
3. Di kolom **Choose a tag**, ketik `v1.0.0` lalu klik **Create new tag: v1.0.0 on publish**.
4. Isi judul rilis (*Release title*): `OXPlayer v1.0.0 - Modern Multimedia Player for Windows`.
5. Tulis deskripsi rilis (contoh deskripsi ada di bawah).
6. Di bagian bawah kotak teks (*Attach binaries by dropping them here...*), seret (*drag-and-drop*) file:
   `D:\Project FIX\media player\github_upload\RELEASE_ASSETS\OXPlayer_Setup.exe`
7. Tunggu hingga proses upload selesai (165 MB, progress bar 100%).
8. Centang kotak **Set as the latest release**.
9. Klik tombol hijau **Publish release**.

---

### Contoh Deskripsi Rilis untuk Halaman GitHub Releases

```markdown
## OXPlayer v1.0.0 — Modern Multimedia Player for Windows

### What's New:
- **Direct3D Hardware Accelerated Video Rendering**: Native LibVLC Direct3D output with letterbox/pillarbox aspect ratio preservation.
- **Top-Level Frameless Overlays**: Eliminates HWND occlusion bugs on Windows Direct3D canvas; interactive Resume and Next Episode banners float flawlessly.
- **Responsive Floating Dock**: Modern edge-to-edge floating playback dock that automatically adapts to compact, widescreen, and vertical (9:16) videos without UI clipping.
- **Picture-in-Picture (PiP) Window**: Compact floating PiP mode with Unicode glyph controls.
- **Rich Playlist Drawer**: Natural sort ordering, episode auto-discovery, search filtering, and repeat/shuffle modes.
- **Comprehensive Audio & Video Controls**: 10-band graphic equalizer, spatial audio presets, hardware deinterlacing, and real-time color adjustments.
- **Full Offline Installer**: Standalone setup wizard compatible with Windows 7, 8, 8.1, 10, and 11.

### Downloads:
- **`OXPlayer_Setup.exe`**: Offline installer for Windows 7 - 11 (64-bit).
```
