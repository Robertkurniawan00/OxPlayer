"""
Fix and repair Windows File Association & Open With Icon for OXPlayer.
Ensures Windows File Properties ("Opens with:"), Open With context menus,
and file icons display the official OXPlayer icon instead of the Python icon.
"""

import os
import sys
import shutil
import winreg
import ctypes
import subprocess
from typing import List

EXTENSIONS = [
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
    """Checks whether Windows 11 Smart App Control (SAC) is active."""
    if sys.platform != "win32":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\CI\Policy") as k:
            val, _ = winreg.QueryValueEx(k, "VerifiedAndReputablePolicyState")
            return int(val) in (1, 2)  # 1 = Evaluation, 2 = Enforced
    except Exception:
        pass
    return False


def unblock_path(target_path: str):
    """Removes Zone.Identifier (Mark of the Web) from files."""
    if not os.path.exists(target_path):
        return
    try:
        cmd = f'Get-ChildItem -Path "{target_path}" -Recurse -File -ErrorAction SilentlyContinue | Unblock-File'
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
    except Exception:
        pass


def delete_registry_tree(root, key_path: str):
    """Recursively deletes a registry key and all its subkeys."""
    try:
        with winreg.OpenKey(root, key_path, 0, winreg.KEY_ALL_ACCESS) as k:
            while True:
                try:
                    sub = winreg.EnumKey(k, 0)
                    delete_registry_tree(root, f"{key_path}\\{sub}")
                except OSError:
                    break
        winreg.DeleteKey(root, key_path)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[-] Could not delete {key_path}: {e}")


def get_best_oxplayer_exe() -> str:
    """Finds the best available OXPlayer.exe binary."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "OXPlayer", "OXPlayer.exe"),
        os.path.join(project_dir, "dist", "OXPlayer", "OXPlayer.exe"),
        os.path.join(project_dir, "OXPlayer.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)
    return ""


def get_best_icon_path(exe_path: str) -> str:
    """Finds the best available app_icon.ico file."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if exe_path:
        candidates.append(os.path.join(os.path.dirname(exe_path), "assets", "app_icon.ico"))
        candidates.append(os.path.join(os.path.dirname(exe_path), "_internal", "assets", "app_icon.ico"))
    candidates.append(os.path.join(project_dir, "assets", "app_icon.ico"))

    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)
    return exe_path


def apply_file_association_fix() -> bool:
    print("=" * 65)
    print("      OXPLAYER WINDOWS FILE ASSOCIATION & ICON REPAIR")
    print("=" * 65)

    project_dir = os.path.dirname(os.path.abspath(__file__))
    main_py = os.path.join(project_dir, "main.py")
    pythonw_path = get_pythonw_path()
    exe_path = get_best_oxplayer_exe()
    icon_path = get_best_icon_path(exe_path)
    icon_val = f'"{icon_path}",0' if icon_path.endswith(".ico") else f'"{exe_path}",0'

    # Unblock files to remove Mark of the Web
    unblock_path(project_dir)
    if exe_path:
        unblock_path(os.path.dirname(exe_path))

    # Determine command runner:
    # Always prioritize compiled OXPlayer.exe binary when available so Windows recognizes
    # OXPlayer as the native media application, displays its official icon, and never
    # displays the Python snake icon overlay on video/audio thumbnails.
    if exe_path and os.path.isfile(exe_path):
        open_cmd = f'"{exe_path}" "%1"'
        primary_runner = exe_path
        print(f"[*] Primary Executable : {exe_path}")
    elif os.path.isfile(main_py):
        open_cmd = f'"{pythonw_path}" "{main_py}" "%1"'
        primary_runner = pythonw_path
        print(f"[*] Python Runner (Fallback) : {pythonw_path}")
    else:
        open_cmd = f'"{exe_path}" "%1"'
        primary_runner = exe_path
        print(f"[*] Executable Path: {exe_path}")

    print(f"[*] Open Command      : {open_cmd}")
    print(f"[*] Application Icon  : {icon_path}")
    prog_id = "OXPlayer.MediaFile"

    # 1. Purge any pythonw.exe or python.exe media application registrations
    # Registering pythonw.exe as a media handler causes Windows Shell to badge media files with Python icons!
    print("[1/7] Purging Python media association registrations from Windows Shell...")
    for py_app in ["pythonw.exe", "python.exe"]:
        delete_registry_tree(winreg.HKEY_CURRENT_USER, rf"Software\Classes\Applications\{py_app}")

    # Clean MuiCache for Python
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache", 0, winreg.KEY_ALL_ACCESS) as k:
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
    except Exception as e:
        print(f"[-] MuiCache note: {e}")

    # 2. Register OXPlayer.MediaFile ProgID
    print(f"[2/7] Registering ProgID: {prog_id}...")
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

    # 3. Register Applications\OXPlayer.exe
    print("[3/7] Registering Applications\\OXPlayer.exe...")
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
        for ext in EXTENSIONS:
            winreg.SetValueEx(k, ext, 0, winreg.REG_SZ, "")

    # 4. SystemFileAssociations (video & audio)
    print("[4/7] Updating SystemFileAssociations for Video and Audio...")
    for cat in ["video", "audio"]:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\SystemFileAssociations\{cat}\shell\OXPlayer") as k:
            winreg.SetValue(k, "", winreg.REG_SZ, "Putar dengan OXPlayer")
            winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon_val)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\SystemFileAssociations\{cat}\shell\OXPlayer\command") as k:
            winreg.SetValue(k, "", winreg.REG_SZ, open_cmd)

    # 5. RegisteredApplications & Media Capabilities (Windows Settings & Open With)
    print("[5/7] Registering Windows Media Capabilities...")
    cap_key = r"Software\Clients\Media\OXPlayer\Capabilities"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cap_key) as k:
        winreg.SetValueEx(k, "ApplicationName", 0, winreg.REG_SZ, "OXPlayer")
        winreg.SetValueEx(k, "ApplicationDescription", 0, winreg.REG_SZ, "Modern High-Performance Media Player")
        winreg.SetValueEx(k, "ApplicationIcon", 0, winreg.REG_SZ, icon_val)

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{cap_key}\FileAssociations") as k:
        for ext in EXTENSIONS:
            winreg.SetValueEx(k, ext, 0, winreg.REG_SZ, prog_id)

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\RegisteredApplications") as k:
        winreg.SetValueEx(k, "OXPlayer", 0, winreg.REG_SZ, cap_key)

    # 6. Map file extensions and sanitize OpenWithList
    print("[6/7] Associating file extensions and sanitizing OpenWithList / MRU...")
    for ext in EXTENSIONS:
        try:
            # Set default ProgID for extension in HKCU
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{ext}") as k:
                winreg.SetValue(k, "", winreg.REG_SZ, prog_id)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{ext}\OpenWithProgids") as k:
                winreg.SetValueEx(k, prog_id, 0, winreg.REG_NONE, b"")

            # Clean FileExts\{ext}\OpenWithProgids
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{ext}\OpenWithProgids") as k:
                winreg.SetValueEx(k, prog_id, 0, winreg.REG_NONE, b"")

            # Sanitize FileExts\{ext}\OpenWithList
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{ext}\OpenWithList") as k:
                values = {}
                mru = ""
                try:
                    mru, _ = winreg.QueryValueEx(k, "MRUList")
                except FileNotFoundError:
                    mru = ""

                i = 0
                to_delete = []
                while True:
                    try:
                        vname, vdata, _ = winreg.EnumValue(k, i)
                        if vname != "MRUList":
                            if "python" in str(vdata).lower():
                                to_delete.append((vname, vdata))
                            else:
                                values[vname] = vdata
                        i += 1
                    except OSError:
                        break

                for vn, _ in to_delete:
                    try:
                        winreg.DeleteValue(k, vn)
                        mru = mru.replace(vn, "")
                    except Exception:
                        pass

                # Check if OXPlayer.exe is already listed in values
                ox_key = None
                for vn, vdata in values.items():
                    if str(vdata).lower() == "oxplayer.exe":
                        ox_key = vn
                        break

                if not ox_key:
                    # Find first free letter from 'a' to 'z'
                    used_letters = set(values.keys())
                    for ch in "abcdefghijklmnopqrstuvwxyz":
                        if ch not in used_letters:
                            ox_key = ch
                            break
                    if ox_key:
                        winreg.SetValueEx(k, ox_key, 0, winreg.REG_SZ, "OXPlayer.exe")
                        values[ox_key] = "OXPlayer.exe"

                # Put ox_key at the top of MRUList
                if ox_key:
                    mru_cleaned = ox_key + "".join([c for c in mru if c != ox_key and c in values])
                    winreg.SetValueEx(k, "MRUList", 0, winreg.REG_SZ, mru_cleaned)
        except Exception as e:
            print(f"[-] Extension association warning for {ext}: {e}")

    # 7. Notify Windows Shell & Refresh Explorer Cache
    print("[7/7] Notifying Windows Shell to refresh association & icon cache...")
    try:
        # SHCNE_ASSOCCHANGED = 0x08000000, SHCNF_IDLIST = 0x0000
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:
        pass

    print("=" * 65)
    print("[OK] Registry file association & icon configuration repaired!")
    print("=" * 65)
    return True


if __name__ == "__main__":
    apply_file_association_fix()
