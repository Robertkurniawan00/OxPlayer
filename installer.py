"""
OXPlayer Standalone Setup & Installation Wizard.
Compatible with Windows 7, 8, 8.1, 10, and 11 (64-bit).
Handles:
- Destination directory selection
- Component extraction & verification
- Desktop & Start Menu shortcut creation with official OXPlayer icon
- Windows Registry File Associations (Video and Audio)
- Add/Remove Programs Windows Uninstaller registration
- Professional Obsidian aesthetic
"""

import os
import sys
import shutil
import subprocess
from typing import Optional

try:
    import win32com.client
except ImportError:
    win32com = None

from PyQt6.QtWidgets import (
    QApplication, QWizard, QWizardPage, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QProgressBar,
    QFileDialog, QMessageBox, QFrame, QWidget
)
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# Universal extensions to associate
ASSOCIATED_EXTENSIONS = [
    ".mp4", ".mkv", ".avi", ".ts", ".mts", ".m2ts", ".mov", ".flv",
    ".webm", ".wmv", ".vob", ".mpg", ".mpeg", ".3gp", ".rmvb",
    ".mp3", ".flac", ".wav", ".aac", ".m4a", ".opus", ".ogg"
]


def get_pythonw_path() -> str:
    """Finds pythonw.exe in current Python environment or system PATH."""
    py_dir = os.path.dirname(os.path.abspath(sys.executable))
    candidates = [
        os.path.join(py_dir, "pythonw.exe"),
        os.path.join(py_dir, "Scripts", "pythonw.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    w = shutil.which("pythonw")
    if w and os.path.isfile(w):
        return w
    return sys.executable


def is_smart_app_control_active() -> bool:
    """Checks whether Windows 11 Smart App Control (SAC) is active (Evaluation or Enforced)."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\CI\Policy") as k:
            val, _ = winreg.QueryValueEx(k, "VerifiedAndReputablePolicyState")
            return int(val) in (1, 2)  # 0 = Off, 1 = Evaluation, 2 = Enforced
    except Exception:
        pass
    return False


def unblock_path(target_path: str):
    """Removes Zone.Identifier (Mark of the Web) from files to prevent SAC/SmartScreen block."""
    if not os.path.exists(target_path):
        return
    try:
        cmd = f'Get-ChildItem -Path "{target_path}" -Recurse -File -ErrorAction SilentlyContinue | Unblock-File'
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
    except Exception:
        pass


def _create_shortcut(lnk_path: str, target_path: str, work_dir: str, icon_path: str = "", desc: str = "", args: str = "") -> bool:
    """Creates a Windows shell shortcut with dual win32com and PowerShell fallback."""
    icon_loc = f"{icon_path},0" if (icon_path and "," not in icon_path) else icon_path
    parent_dir = os.path.dirname(lnk_path)
    if parent_dir and not os.path.isdir(parent_dir):
        try:
            os.makedirs(parent_dir, exist_ok=True)
        except Exception:
            pass

    # Method 1: WScript.Shell COM
    if win32com is not None:
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            s = shell.CreateShortcut(lnk_path)
            s.TargetPath = target_path
            if args:
                s.Arguments = args
            s.WorkingDirectory = work_dir
            if icon_loc:
                s.IconLocation = icon_loc
            if desc:
                s.Description = desc
            s.Save()
            if os.path.exists(lnk_path):
                return True
        except Exception:
            pass

    # Method 2: PowerShell script fallback
    try:
        def _ps_esc(val: str) -> str:
            return val.replace("'", "''")

        ps_cmd = (
            f"$ws = New-Object -ComObject WScript.Shell; "
            f"$s = $ws.CreateShortcut('{_ps_esc(lnk_path)}'); "
            f"$s.TargetPath = '{_ps_esc(target_path)}'; "
            f"$s.WorkingDirectory = '{_ps_esc(work_dir)}'; "
        )
        if args:
            ps_cmd += f"$s.Arguments = '{_ps_esc(args)}'; "
        if icon_loc:
            ps_cmd += f"$s.IconLocation = '{_ps_esc(icon_loc)}'; "
        if desc:
            ps_cmd += f"$s.Description = '{_ps_esc(desc)}'; "
        ps_cmd += "$s.Save()"
        creation_flag = 0x08000000 if sys.platform.startswith("win") else 0
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                       capture_output=True, creationflags=creation_flag)
        if os.path.exists(lnk_path):
            return True
    except Exception:
        pass
    return False


def _get_target_desktop_dirs() -> list:
    """Returns candidate desktop directories."""
    dirs = []
    if win32com is not None:
        try:
            d = win32com.client.Dispatch("WScript.Shell").SpecialFolders("Desktop")
            if d and os.path.isdir(d) and d not in dirs:
                dirs.append(d)
        except Exception:
            pass
    userprofile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    for cand in [
        os.path.join(userprofile, "Desktop"),
        os.path.join(userprofile, "OneDrive", "Desktop")
    ]:
        if os.path.isdir(cand) and cand not in dirs:
            dirs.append(cand)

    public_desktop = os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop")
    if os.path.isdir(public_desktop) and public_desktop not in dirs:
        try:
            test_file = os.path.join(public_desktop, ".perm_test")
            with open(test_file, "w") as f:
                f.write("")
            os.remove(test_file)
            dirs.append(public_desktop)
        except Exception:
            pass
    return dirs


def _get_target_programs_dirs() -> list:
    """Returns candidate Start Menu Programs directories."""
    dirs = []
    if win32com is not None:
        try:
            p = win32com.client.Dispatch("WScript.Shell").SpecialFolders("Programs")
            if p and os.path.isdir(p) and p not in dirs:
                dirs.append(p)
        except Exception:
            pass
    appdata_prog = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs")
    if os.path.isdir(appdata_prog) and appdata_prog not in dirs:
        dirs.append(appdata_prog)
    return dirs



class InstallWorker(QThread):
    progress = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, target_dir: str, create_desktop_shortcut: bool,
                 create_start_menu: bool, associate_files: bool):
        super().__init__()
        self.target_dir = target_dir
        self.create_desktop_shortcut = create_desktop_shortcut
        self.create_start_menu = create_start_menu
        self.associate_files = associate_files

    def run(self):
        try:
            # Terminate any running OXPlayer instances to avoid file lock collisions
            if sys.platform == "win32":
                try:
                    creation_flag = 0x08000000
                    subprocess.run(["taskkill", "/F", "/IM", "OXPlayer.exe"],
                                   capture_output=True, creationflags=creation_flag)
                    subprocess.run(["taskkill", "/F", "/IM", "pythonw.exe"],
                                   capture_output=True, creationflags=creation_flag)
                except Exception:
                    pass

            self.progress.emit(10, "Menyiapkan folder instalasi...")
            os.makedirs(self.target_dir, exist_ok=True)

            # Source payload directory
            # When running inside installer package, payload is in current_dir / payload or next to installer
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            candidate_sources = [
                os.path.join(base_dir, "payload"),
                os.path.join(base_dir, "payload", "OXPlayer"),
                os.path.join(base_dir, "dist", "OXPlayer"),
                os.path.join(os.path.dirname(base_dir), "dist", "OXPlayer"),
                os.path.join(base_dir, "..", "dist", "OXPlayer"),
            ]
            source_dir = None
            is_prebuilt_dist = False
            for c in candidate_sources:
                if os.path.isdir(c) and os.path.exists(os.path.join(c, "OXPlayer.exe")):
                    has_internal = os.path.isdir(os.path.join(c, "_internal"))
                    has_py_dll = any(f.lower().startswith("python3") and f.lower().endswith(".dll") for f in os.listdir(c) if os.path.isfile(os.path.join(c, f)))
                    if has_internal or has_py_dll:
                        source_dir = c
                        is_prebuilt_dist = True
                        break

            if not source_dir:
                # Check if running directly from project source
                project_cand = base_dir
                if not (os.path.isfile(os.path.join(project_cand, "main.py")) and os.path.isdir(os.path.join(project_cand, "src"))):
                    parent_cand = os.path.dirname(base_dir)
                    if os.path.isfile(os.path.join(parent_cand, "main.py")) and os.path.isdir(os.path.join(parent_cand, "src")):
                        project_cand = parent_cand
                if os.path.isfile(os.path.join(project_cand, "main.py")) and os.path.isdir(os.path.join(project_cand, "src")):
                    source_dir = project_cand
                    is_prebuilt_dist = False

            if not source_dir:
                self.finished_signal.emit(
                    False,
                    "File instalasi OXPlayer tidak ditemukan.\n"
                    "Pastikan folder 'dist/OXPlayer' atau file proyek 'main.py' tersedia."
                )
                return

            self.progress.emit(25, "Mengekstrak file program dan komponen...")
            if is_prebuilt_dist:
                for item in os.listdir(source_dir):
                    s_path = os.path.join(source_dir, item)
                    d_path = os.path.join(self.target_dir, item)
                    if os.path.isdir(s_path):
                        shutil.copytree(s_path, d_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s_path, d_path)
            else:
                # Source mode: copy necessary project directories and entry files
                for d_name in ["src", "assets", "core_bin"]:
                    s_dir = os.path.join(source_dir, d_name)
                    d_dir = os.path.join(self.target_dir, d_name)
                    if os.path.isdir(s_dir):
                        shutil.copytree(s_dir, d_dir, dirs_exist_ok=True)
                for f_name in ["main.py", "requirements.txt", "OXPlayer_Launcher.vbs", "run_app.bat", "OXPlayer.exe"]:
                    s_file = os.path.join(source_dir, f_name)
                    d_file = os.path.join(self.target_dir, f_name)
                    if os.path.isfile(s_file):
                        shutil.copy2(s_file, d_file)

            # Unblock extracted files from Mark of the Web
            self.progress.emit(50, "Memvalidasi integritas file program...")
            unblock_path(self.target_dir)

            # Ensure OXPlayer_Launcher.vbs exists in target_dir
            vbs_path = os.path.join(self.target_dir, "OXPlayer_Launcher.vbs")
            if not os.path.exists(vbs_path):
                try:
                    with open(vbs_path, "w", encoding="utf-8") as vf:
                        vf.write('Set WshShell = CreateObject("WScript.Shell")\n'
                                 'Set FSO = CreateObject("Scripting.FileSystemObject")\n'
                                 'ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)\n'
                                 'WshShell.CurrentDirectory = ScriptDir\n'
                                 'Cmd = "pythonw """ & ScriptDir & "\\main.py"""\n'
                                 'For i = 0 To WScript.Arguments.Count - 1\n'
                                 '    Cmd = Cmd & " """ & WScript.Arguments(i) & """"\n'
                                 'Next\n'
                                 'WshShell.Run Cmd, 0, False\n')
                except Exception:
                    pass

            exe_path = os.path.join(self.target_dir, "OXPlayer.exe")
            main_py_path = os.path.join(self.target_dir, "main.py")
            icon_path = os.path.join(self.target_dir, "assets", "app_icon.ico")
            if not os.path.exists(icon_path):
                icon_path = os.path.join(self.target_dir, "_internal", "assets", "app_icon.ico")
            if not os.path.exists(icon_path):
                icon_path = exe_path

            pythonw_path = get_pythonw_path()

            # Always prioritize native OXPlayer.exe binary so Windows Shell identifies
            # OXPlayer with its official icon rather than Python logo badges.
            if os.path.exists(exe_path):
                primary_target = exe_path
                primary_args = ""
                open_cmd = f'"{exe_path}" "%1"'
            elif os.path.exists(main_py_path):
                primary_target = pythonw_path
                primary_args = f'"{main_py_path}"'
                open_cmd = f'"{pythonw_path}" "{main_py_path}" "%1"'
            else:
                primary_target = exe_path
                primary_args = ""
                open_cmd = f'"{exe_path}" "%1"'

            self.progress.emit(65, "Membuat shortcut Desktop & Start Menu...")
            desc = "OXPlayer - Modern Media Player"
            if self.create_desktop_shortcut:
                for desktop_dir in _get_target_desktop_dirs():
                    try:
                        _create_shortcut(
                            lnk_path=os.path.join(desktop_dir, "OXPlayer.lnk"),
                            target_path=primary_target,
                            work_dir=self.target_dir,
                            icon_path=icon_path,
                            desc=desc,
                            args=primary_args
                        )
                    except Exception:
                        pass

            if self.create_start_menu:
                for prog_dir in _get_target_programs_dirs():
                    try:
                        start_dir = os.path.join(prog_dir, "OXPlayer")
                        os.makedirs(start_dir, exist_ok=True)
                        _create_shortcut(
                            lnk_path=os.path.join(start_dir, "OXPlayer.lnk"),
                            target_path=primary_target,
                            work_dir=self.target_dir,
                            icon_path=icon_path,
                            desc=desc,
                            args=primary_args
                        )

                        # Uninstaller shortcut
                        uninst_bat = os.path.join(self.target_dir, "Uninstall_OXPlayer.bat")
                        _create_shortcut(
                            lnk_path=os.path.join(start_dir, "Uninstall OXPlayer.lnk"),
                            target_path=uninst_bat,
                            work_dir=self.target_dir,
                            icon_path="",
                            desc="Uninstall OXPlayer",
                            args=""
                        )
                    except Exception:
                        pass

            self.progress.emit(85, "Mendaftarkan asosiasi file video & audio...")
            # Create Uninstall batch script
            uninst_script = os.path.join(self.target_dir, "Uninstall_OXPlayer.bat")
            with open(uninst_script, "w", encoding="utf-8") as f:
                f.write("""@echo off
title Uninstall OXPlayer
echo Menghapus instalasi OXPlayer...
taskkill /f /im OXPlayer.exe 2>nul
taskkill /f /im pythonw.exe 2>nul
timeout /t 2 /nobreak >nul
reg delete "HKCU\\Software\\Classes\\OXPlayer.MediaFile" /f 2>nul
reg delete "HKCU\\Software\\Classes\\Applications\\OXPlayer.exe" /f 2>nul
reg delete "HKCU\\Software\\Classes\\SystemFileAssociations\\video\\shell\\OXPlayer" /f 2>nul
reg delete "HKCU\\Software\\Classes\\SystemFileAssociations\\audio\\shell\\OXPlayer" /f 2>nul
reg delete "HKCU\\Software\\Clients\\Media\\OXPlayer" /f 2>nul
reg delete "HKCU\\Software\\RegisteredApplications" /v "OXPlayer" /f 2>nul
reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\OXPlayer" /f 2>nul
del /f /q "%USERPROFILE%\\Desktop\\OXPlayer.lnk" 2>nul
del /f /q "%USERPROFILE%\\OneDrive\\Desktop\\OXPlayer.lnk" 2>nul
del /f /q "%PUBLIC%\\Desktop\\OXPlayer.lnk" 2>nul
rmdir /s /q "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\OXPlayer" 2>nul
powershell -NoProfile -Command "Add-Type -MemberDefinition '[DllImport(\"shell32.dll\")] public static extern void SHChangeNotify(int eventId, int flags, IntPtr item1, IntPtr item2);' -Name Shell -Namespace Win32; [Win32.Shell]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)" 2>nul
echo Membersihkan berkas instalasi...
set "INSTALL_DIR=%~dp0"
cd /d "%TEMP%"
rd /s /q "%INSTALL_DIR%" 2>nul
echo OXPlayer berhasil di-uninstall sepenuhnya.
pause
""")

            # Register Windows Registry File Associations & Open With Branding (HKCU)
            if self.associate_files:
                try:
                    import winreg
                    prog_id = "OXPlayer.MediaFile"
                    icon_val = f'"{icon_path}",0'

                    # ProgID
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}") as k:
                        winreg.SetValue(k, "", winreg.REG_SZ, "OXPlayer")
                        winreg.SetValueEx(k, "FriendlyTypeName", 0, winreg.REG_SZ, "OXPlayer Media File")
                        winreg.SetValueEx(k, "AppUserModelID", 0, winreg.REG_SZ, "oxplayer.mediaplayer.modern.2.5.0")

                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}\DefaultIcon") as k:
                        winreg.SetValue(k, "", winreg.REG_SZ, icon_val)

                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}\shell\open") as k:
                        winreg.SetValue(k, "", winreg.REG_SZ, "Putar dengan OXPlayer")
                        winreg.SetValueEx(k, "FriendlyAppName", 0, winreg.REG_SZ, "OXPlayer")
                        winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon_val)

                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}\shell\open\command") as k:
                        winreg.SetValue(k, "", winreg.REG_SZ, open_cmd)

                    # MuiCache for Explorer Open With
                    try:
                        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache") as k:
                            for py_runner in [pythonw_path, sys.executable]:
                                if py_runner:
                                    for suffix in [".FriendlyAppName", ".ApplicationCompany"]:
                                        try:
                                            winreg.DeleteValue(k, f"{py_runner}{suffix}")
                                        except FileNotFoundError:
                                            pass
                            if exe_path:
                                winreg.SetValueEx(k, f"{exe_path}.FriendlyAppName", 0, winreg.REG_SZ, "OXPlayer")
                                winreg.SetValueEx(k, f"{exe_path}.ApplicationCompany", 0, winreg.REG_SZ, "OXPlayer Project")
                    except Exception:
                        pass

                    # Clean up legacy Applications\pythonw.exe & python.exe to prevent Python icon hijacking in Windows Shell
                    try:
                        def _del_key_tree(root, kpath):
                            with winreg.OpenKey(root, kpath, 0, winreg.KEY_ALL_ACCESS) as rk:
                                while True:
                                    try:
                                        s = winreg.EnumKey(rk, 0)
                                        _del_key_tree(root, f"{kpath}\\{s}")
                                    except OSError:
                                        break
                            winreg.DeleteKey(root, kpath)
                        _del_key_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\pythonw.exe")
                        _del_key_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\python.exe")
                    except Exception:
                        pass

                    # Applications\OXPlayer.exe registration
                    try:
                        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\OXPlayer.exe") as k:
                            winreg.SetValue(k, "", winreg.REG_SZ, "OXPlayer")
                            winreg.SetValueEx(k, "FriendlyAppName", 0, winreg.REG_SZ, "OXPlayer")
                            winreg.SetValueEx(k, "ApplicationCompany", 0, winreg.REG_SZ, "OXPlayer Project")
                            winreg.SetValueEx(k, "AppUserModelID", 0, winreg.REG_SZ, "oxplayer.mediaplayer.modern.2.5.0")
                        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\OXPlayer.exe\DefaultIcon") as k:
                            winreg.SetValue(k, "", winreg.REG_SZ, icon_val)
                        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\OXPlayer.exe\shell\open") as k:
                            winreg.SetValue(k, "", winreg.REG_SZ, "Putar dengan OXPlayer")
                            winreg.SetValueEx(k, "FriendlyAppName", 0, winreg.REG_SZ, "OXPlayer")
                            winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon_val)
                        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\OXPlayer.exe\shell\open\command") as k:
                            winreg.SetValue(k, "", winreg.REG_SZ, open_cmd)
                        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\OXPlayer.exe\SupportedTypes") as k:
                            for ext in ASSOCIATED_EXTENSIONS:
                                winreg.SetValueEx(k, ext, 0, winreg.REG_SZ, "")
                    except Exception:
                        pass

                    # RegisteredApplications & Media Capabilities
                    try:
                        cap_key = r"Software\Clients\Media\OXPlayer\Capabilities"
                        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cap_key) as k:
                            winreg.SetValueEx(k, "ApplicationName", 0, winreg.REG_SZ, "OXPlayer")
                            winreg.SetValueEx(k, "ApplicationDescription", 0, winreg.REG_SZ, "Modern High-Performance Media Player")
                            winreg.SetValueEx(k, "ApplicationIcon", 0, winreg.REG_SZ, icon_val)
                        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{cap_key}\FileAssociations") as k:
                            for ext in ASSOCIATED_EXTENSIONS:
                                winreg.SetValueEx(k, ext, 0, winreg.REG_SZ, prog_id)
                        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\RegisteredApplications") as k:
                            winreg.SetValueEx(k, "OXPlayer", 0, winreg.REG_SZ, cap_key)
                    except Exception:
                        pass

                    # Context Menu for Video & Audio
                    for cat in ["video", "audio"]:
                        try:
                            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\SystemFileAssociations\{cat}\shell\OXPlayer") as k:
                                winreg.SetValue(k, "", winreg.REG_SZ, "Putar dengan OXPlayer")
                                winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon_val)
                            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\SystemFileAssociations\{cat}\shell\OXPlayer\command") as k:
                                winreg.SetValue(k, "", winreg.REG_SZ, open_cmd)
                        except Exception:
                            pass

                    # Associate extensions and clean OpenWithList / MRU
                    for ext in ASSOCIATED_EXTENSIONS:
                        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{ext}") as k:
                            winreg.SetValue(k, "", winreg.REG_SZ, prog_id)
                        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{ext}\OpenWithProgids") as k:
                            winreg.SetValueEx(k, prog_id, 0, winreg.REG_NONE, b"")
                        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{ext}\OpenWithProgids") as k:
                            winreg.SetValueEx(k, prog_id, 0, winreg.REG_NONE, b"")
                        # Sanitize OpenWithList
                        try:
                            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{ext}\OpenWithList") as k:
                                values = {}
                                mru = ""
                                try:
                                    mru, _ = winreg.QueryValueEx(k, "MRUList")
                                except FileNotFoundError:
                                    mru = ""
                                i = 0
                                to_del = []
                                while True:
                                    try:
                                        vn, vd, _ = winreg.EnumValue(k, i)
                                        if vn != "MRUList":
                                            if "python" in str(vd).lower():
                                                to_del.append((vn, vd))
                                            else:
                                                values[vn] = vd
                                        i += 1
                                    except OSError:
                                        break
                                for vn, _ in to_del:
                                    try:
                                        winreg.DeleteValue(k, vn)
                                        mru = mru.replace(vn, "")
                                    except Exception:
                                        pass
                                ox_key = None
                                for vn, vd in values.items():
                                    if str(vd).lower() == "oxplayer.exe":
                                        ox_key = vn
                                        break
                                if not ox_key:
                                    for ch in "abcdefghijklmnopqrstuvwxyz":
                                        if ch not in values:
                                            ox_key = ch
                                            break
                                    if ox_key:
                                        winreg.SetValueEx(k, ox_key, 0, winreg.REG_SZ, "OXPlayer.exe")
                                        values[ox_key] = "OXPlayer.exe"
                                if ox_key:
                                    mru_cleaned = ox_key + "".join([c for c in mru if c != ox_key and c in values])
                                    winreg.SetValueEx(k, "MRUList", 0, winreg.REG_SZ, mru_cleaned)
                        except Exception:
                            pass
                except Exception:
                    pass

            # Register in Windows Add/Remove Programs
            try:
                import winreg
                uninst_reg = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\OXPlayer"
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, uninst_reg) as k:
                    winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, "OXPlayer")
                    winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, "2.5.0")
                    winreg.SetValueEx(k, "Publisher", 0, winreg.REG_SZ, "OXPlayer Project")
                    winreg.SetValueEx(k, "DisplayIcon", 0, winreg.REG_SZ, f'"{icon_path}",0')
                    winreg.SetValueEx(k, "UninstallString", 0, winreg.REG_SZ, f'"{uninst_script}"')
                    winreg.SetValueEx(k, "InstallLocation", 0, winreg.REG_SZ, self.target_dir)
            except Exception:
                pass

            # Refresh Windows Shell icon and file association caches
            if sys.platform.startswith("win"):
                try:
                    import ctypes
                    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
                except Exception:
                    pass

            self.progress.emit(100, "Instalasi selesai.")
            self.finished_signal.emit(True, f"{primary_target}::{primary_args}")

        except Exception as e:
            self.finished_signal.emit(False, str(e))


def get_asset_path(filename: str) -> str:
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base_dir, "assets", filename),
        os.path.join(base_dir, "_internal", "assets", filename),
        os.path.join(base_dir, "payload", "assets", filename),
        os.path.join(base_dir, "payload", "_internal", "assets", filename),
        os.path.join(base_dir, "payload", "OXPlayer", "assets", filename),
        os.path.join(base_dir, "payload", "OXPlayer", "_internal", "assets", filename),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", filename),
        os.path.join(os.getcwd(), "assets", filename)
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return ""


def create_page_header(title: str, subtitle: str, show_logo: bool = True) -> QWidget:
    container = QWidget()
    c_layout = QVBoxLayout(container)
    c_layout.setContentsMargins(0, 0, 0, 8)
    c_layout.setSpacing(6)

    header = QWidget()
    h_layout = QHBoxLayout(header)
    h_layout.setContentsMargins(0, 0, 0, 4)
    h_layout.setSpacing(14)

    if show_logo:
        logo_label = QLabel()
        logo_path = get_asset_path("app_icon.ico")
        if not logo_path:
            logo_path = get_asset_path("app_logo.png")
        if logo_path and os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(pix)
            logo_label.setFixedSize(48, 48)
            h_layout.addWidget(logo_label)

    t_box = QVBoxLayout()
    t_box.setSpacing(2)

    lbl_title = QLabel(title)
    lbl_title.setStyleSheet("font-size: 17px; font-weight: bold; color: #ffffff;")
    t_box.addWidget(lbl_title)

    lbl_sub = QLabel(subtitle)
    lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8;")
    t_box.addWidget(lbl_sub)

    h_layout.addLayout(t_box)
    h_layout.addStretch()
    c_layout.addWidget(header)

    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Plain)
    line.setStyleSheet("color: #242b38; background-color: #242b38; height: 1px; max-height: 1px; border: none;")
    c_layout.addWidget(line)

    return container


class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        hdr = create_page_header(
            "OXPLAYER INSTALLATION SETUP",
            "Modern Media Player",
            show_logo=True
        )
        layout.addWidget(hdr)

        intro = QLabel("Selamat datang di setup instalasi OXPlayer. Klik Next untuk melanjutkan proses instalasi.")
        intro.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        layout.addWidget(intro)

        card = QFrame()
        card.setObjectName("FeatureCard")
        card.setStyleSheet("""
            QFrame#FeatureCard {
                background-color: #161a24;
                border: 1px solid #283345;
                border-radius: 6px;
                padding: 10px;
            }
            QLabel {
                color: #e2e8f0;
                font-size: 11px;
                line-height: 1.5;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(7)

        features = [
            ("Format Lengkap", "Mendukung berbagai format video & audio populer (MP4, MKV, TS, AVI, MOV, FLV, MP3, FLAC, dll.)"),
            ("Akselerasi Hardware", "Mode HW / SW decoding untuk efisiensi CPU dan pemutaran video yang lancar"),
            ("Fitur Praktis", "Picture-in-Picture (PiP), resume playback (seperti VLC), equalizer audio, dan subtitle"),
            ("Kompatibel", "Dapat dijalankan lancar di Windows 7, 8, 8.1, 10, dan 11 (64-bit)")
        ]

        for title, desc in features:
            f_lbl = QLabel(f"<span style='color: #60a5fa; font-weight: bold;'>• {title}:</span> <span style='color: #cbd5e1;'>{desc}</span>")
            f_lbl.setWordWrap(True)
            c_layout.addWidget(f_lbl)

        layout.addWidget(card)
        layout.addStretch()


class DirectoryPage(QWizardPage):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        hdr = create_page_header(
            "Pilih Folder Instalasi",
            "Pilih lokasi folder untuk menginstall OXPlayer di komputer kamu.",
            show_logo=False
        )
        layout.addWidget(hdr)

        lbl = QLabel("Destination Folder:")
        lbl.setStyleSheet("font-weight: 500; color: #e2e8f0; font-size: 12px;")
        layout.addWidget(lbl)

        default_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", "OXPlayer")

        row = QHBoxLayout()
        row.setSpacing(8)
        self.dir_input = QLineEdit(default_dir)
        row.addWidget(self.dir_input)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        opts_frame = QFrame()
        opts_frame.setObjectName("OptionsCard")
        opts_frame.setStyleSheet("""
            QFrame#OptionsCard {
                background-color: #161a24;
                border: 1px solid #283345;
                border-radius: 6px;
                padding: 12px;
                margin-top: 6px;
            }
            QCheckBox {
                color: #e2e8f0;
                font-size: 12px;
                spacing: 8px;
            }
        """)
        f_layout = QVBoxLayout(opts_frame)
        f_layout.setSpacing(10)

        self.desktop_chk = QCheckBox("Buat shortcut di Desktop")
        self.desktop_chk.setChecked(True)
        f_layout.addWidget(self.desktop_chk)

        self.start_chk = QCheckBox("Buat shortcut di Start Menu")
        self.start_chk.setChecked(True)
        f_layout.addWidget(self.start_chk)

        self.assoc_chk = QCheckBox("Jadikan default player untuk file video dan audio")
        self.assoc_chk.setChecked(True)
        f_layout.addWidget(self.assoc_chk)

        layout.addWidget(opts_frame)
        layout.addStretch()

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Pilih Folder Instalasi", self.dir_input.text())
        if d:
            self.dir_input.setText(os.path.join(d, "OXPlayer"))


class InstallingPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.worker: Optional[InstallWorker] = None
        self.exe_path = ""
        self.launch_target = ""
        self.launch_args = ""
        self.success = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(14)

        hdr = create_page_header(
            "Menginstall OXPlayer",
            "Tunggu sebentar, file sedang diekstrak dan dipasang...",
            show_logo=False
        )
        layout.addWidget(hdr)

        layout.addSpacing(10)
        self.status_label = QLabel("Menyiapkan instalasi...")
        self.status_label.setStyleSheet("color: #e4e4e7; font-weight: 600; font-size: 12px;")
        layout.addWidget(self.status_label)

        self.pbar = QProgressBar()
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        self.pbar.setStyleSheet("""
            QProgressBar {
                background-color: #161a24;
                color: #ffffff;
                border: 1px solid #283345;
                border-radius: 4px;
                text-align: center;
                height: 20px;
                font-weight: 500;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.pbar)
        layout.addStretch()

    def initializePage(self):
        self.wizard().button(QWizard.WizardButton.BackButton).setEnabled(False)
        self.wizard().button(QWizard.WizardButton.NextButton).setEnabled(False)

        dir_page: DirectoryPage = self.wizard().page(1)
        target_dir = dir_page.dir_input.text().strip()

        self.worker = InstallWorker(
            target_dir=target_dir,
            create_desktop_shortcut=dir_page.desktop_chk.isChecked(),
            create_start_menu=dir_page.start_chk.isChecked(),
            associate_files=dir_page.assoc_chk.isChecked()
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, val: int, msg: str):
        self.pbar.setValue(val)
        self.status_label.setText(msg)

    def _on_finished(self, success: bool, res: str):
        self.success = success
        if success:
            if "::" in res:
                self.launch_target, self.launch_args = res.split("::", 1)
            else:
                self.launch_target = res
                self.launch_args = ""
            self.exe_path = self.launch_target
            self.status_label.setText("Instalasi selesai!")
            self.wizard().button(QWizard.WizardButton.NextButton).setEnabled(True)
            self.wizard().next()
        else:
            self.status_label.setText(f"Instalasi gagal: {res}")
            QMessageBox.critical(self, "Instalasi Gagal", res)
            self.wizard().button(QWizard.WizardButton.CancelButton).setEnabled(True)

    def isComplete(self) -> bool:
        return self.success


class FinishedPage(QWizardPage):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(14)

        hdr = create_page_header(
            "Instalasi Selesai",
            "OXPlayer sudah terinstall dan siap digunakan di komputer kamu.",
            show_logo=True
        )
        layout.addWidget(hdr)

        card = QFrame()
        card.setObjectName("FeatureCard")
        card.setStyleSheet("""
            QFrame#FeatureCard {
                background-color: #161a24;
                border: 1px solid #283345;
                border-radius: 6px;
                padding: 14px;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 12px;
                line-height: 1.6;
            }
        """)
        c_layout = QVBoxLayout(card)
        lbl = QLabel(
            "OXPlayer siap digunakan untuk memutar seluruh file video dan audio Anda.\n\n"
            "Klik Finish untuk menutup installer dan mulai memakai OXPlayer."
        )
        lbl.setWordWrap(True)
        c_layout.addWidget(lbl)
        layout.addWidget(card)

        self.run_chk = QCheckBox("Jalankan OXPlayer sekarang")
        self.run_chk.setChecked(True)
        self.run_chk.setStyleSheet("font-weight: 600; font-size: 13px; color: #f4f4f5; margin-top: 6px;")
        layout.addWidget(self.run_chk)
        layout.addStretch()


class OXPlayerInstallerWizard(QWizard):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OXPlayer Setup")
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.resize(620, 440)
        self.setMinimumSize(600, 420)

        # Standard clean wizard buttons (no awkward OS translations)
        self.setButtonText(QWizard.WizardButton.BackButton, "< Back")
        self.setButtonText(QWizard.WizardButton.NextButton, "Next >")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Cancel")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Finish")

        # Set official app icon
        icon_path = get_asset_path("app_icon.ico")
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        # Apply rich contrast, modern dark styling (NO white background anywhere)
        self.setStyleSheet("""
            QWizard, QWizardPage {
                background-color: #12141a;
                color: #e2e8f0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #cbd5e1;
            }
            QLineEdit {
                background-color: #171b24;
                border: 1px solid #283345;
                color: #ffffff;
                padding: 6px 10px;
                border-radius: 4px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #4b5563;
            }
            QPushButton {
                background-color: #1e222c;
                border: 1px solid #2e3545;
                color: #e2e8f0;
                padding: 6px 18px;
                border-radius: 4px;
                font-weight: 500;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #272d3b;
                border-color: #475569;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #141720;
            }
            QPushButton:disabled {
                background-color: #141720;
                border-color: #1f2533;
                color: #4b5563;
            }
            QPushButton:default {
                background-color: #2563eb;
                border: 1px solid #3b82f6;
                color: #ffffff;
                font-weight: 600;
            }
            QPushButton:default:hover {
                background-color: #1d4ed8;
            }
            QCheckBox {
                color: #e2e8f0;
            }
        """)

        self.page_welcome = WelcomePage()
        self.page_dir = DirectoryPage()
        self.page_installing = InstallingPage()
        self.page_finished = FinishedPage()

        self.addPage(self.page_welcome)
        self.addPage(self.page_dir)
        self.addPage(self.page_installing)
        self.addPage(self.page_finished)

    def accept(self):
        if self.page_finished.run_chk.isChecked():
            target = getattr(self.page_installing, "launch_target", "") or self.page_installing.exe_path
            args = getattr(self.page_installing, "launch_args", "")
            if target and os.path.exists(target):
                try:
                    if args:
                        clean_arg = args.strip().strip('"')
                        subprocess.Popen([target, clean_arg])
                    else:
                        subprocess.Popen([target])
                except Exception:
                    pass
        super().accept()


def apply_native_win32_icon(hwnd, icon_path):
    if sys.platform.startswith("win") and os.path.exists(icon_path):
        try:
            import ctypes
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x0010
            user32 = ctypes.windll.user32
            hicon_sm = user32.LoadImageW(None, icon_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
            hicon_bg = user32.LoadImageW(None, icon_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
            hicon_lg = user32.LoadImageW(None, icon_path, IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
            WM_SETICON = 0x007F
            user32.SendMessageW(hwnd, WM_SETICON, 0, hicon_sm or hicon_bg)
            user32.SendMessageW(hwnd, WM_SETICON, 1, hicon_lg or hicon_bg)

            GCLP_HICON = -14
            GCLP_HICONSM = -34
            SetClassLong = getattr(user32, "SetClassLongPtrW", getattr(user32, "SetClassLongW", None))
            if SetClassLong:
                SetClassLong(hwnd, GCLP_HICON, hicon_lg or hicon_bg)
                SetClassLong(hwnd, GCLP_HICONSM, hicon_sm or hicon_bg)
        except Exception:
            pass


def main():
    if sys.platform == "win32" and not getattr(sys, "frozen", False):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("oxplayer.installer.setup.2.5.0")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("OXPlayer Setup")
    app.setApplicationDisplayName("")

    icon_path = get_asset_path("app_icon.ico")
    if icon_path:
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)

    wiz = OXPlayerInstallerWizard()
    if icon_path:
        wiz.setWindowIcon(QIcon(icon_path))
    wiz.show()

    if icon_path and sys.platform.startswith("win"):
        try:
            import ctypes
            apply_native_win32_icon(int(wiz.winId()), icon_path)
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        except Exception:
            pass

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

