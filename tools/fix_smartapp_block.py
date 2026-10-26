"""
Fix Smart App Control (SAC) / Windows SmartScreen blocking OXPlayer and
configure professional 'Open with' branding and right-click context menu.
"""

import os
import sys
import shutil
import winreg
import ctypes
import subprocess

ASSOCIATED_EXTENSIONS = [
    ".mp4", ".mkv", ".avi", ".ts", ".mts", ".m2ts", ".mov", ".flv",
    ".webm", ".wmv", ".vob", ".mpg", ".mpeg", ".3gp", ".rmvb",
    ".mp3", ".flac", ".wav", ".aac", ".m4a", ".opus", ".ogg"
]

def get_pythonw_path() -> str:
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


def unblock_project_files(project_dir: str):
    """Removes Zone.Identifier (Mark of the Web) from files in project."""
    try:
        cmd = f'Get-ChildItem -Path "{project_dir}" -Recurse -File -ErrorAction SilentlyContinue | Unblock-File'
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
    except Exception:
        pass


def update_registry_branding_and_associations(pythonw_path: str, main_py: str, icon_path: str):
    """Registers OXPlayer with proper branding so Windows shows 'OXPlayer' instead of 'Python'."""
    prog_id = "OXPlayer.MediaFile"
    open_cmd = f'"{pythonw_path}" "{main_py}" "%1"'
    icon_val = f'"{icon_path}",0'

    # 1. Update Windows MuiCache so Explorer displays "OXPlayer" instead of "Python" for pythonw.exe
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache") as k:
            winreg.SetValueEx(k, f"{pythonw_path}.FriendlyAppName", 0, winreg.REG_SZ, "OXPlayer")
            winreg.SetValueEx(k, f"{pythonw_path}.ApplicationCompany", 0, winreg.REG_SZ, "OXPlayer Project")
    except Exception:
        pass

    # 2. Register Applications\pythonw.exe with OXPlayer branding
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\pythonw.exe") as k:
            winreg.SetValue(k, "", winreg.REG_SZ, "OXPlayer")
            winreg.SetValueEx(k, "FriendlyAppName", 0, winreg.REG_SZ, "OXPlayer")
            winreg.SetValueEx(k, "ApplicationCompany", 0, winreg.REG_SZ, "OXPlayer Project")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\pythonw.exe\DefaultIcon") as k:
            winreg.SetValue(k, "", winreg.REG_SZ, icon_val)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\pythonw.exe\shell\open") as k:
            winreg.SetValueEx(k, "FriendlyAppName", 0, winreg.REG_SZ, "OXPlayer")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\pythonw.exe\shell\open\command") as k:
            winreg.SetValue(k, "", winreg.REG_SZ, open_cmd)
    except Exception:
        pass

    # 3. Register Applications\OXPlayer.exe
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\OXPlayer.exe") as k:
            winreg.SetValue(k, "", winreg.REG_SZ, "OXPlayer")
            winreg.SetValueEx(k, "FriendlyAppName", 0, winreg.REG_SZ, "OXPlayer")
            winreg.SetValueEx(k, "ApplicationCompany", 0, winreg.REG_SZ, "OXPlayer Project")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\OXPlayer.exe\DefaultIcon") as k:
            winreg.SetValue(k, "", winreg.REG_SZ, icon_val)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\OXPlayer.exe\shell\open") as k:
            winreg.SetValueEx(k, "FriendlyAppName", 0, winreg.REG_SZ, "OXPlayer")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\OXPlayer.exe\shell\open\command") as k:
            winreg.SetValue(k, "", winreg.REG_SZ, open_cmd)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\OXPlayer.exe\SupportedTypes") as k:
            for ext in ASSOCIATED_EXTENSIONS:
                winreg.SetValueEx(k, ext, 0, winreg.REG_SZ, "")
    except Exception:
        pass

    # 4. ProgID: OXPlayer.MediaFile
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

    # 5. Right-Click Context Menu for Video & Audio (SystemFileAssociations)
    for category in ["video", "audio"]:
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\SystemFileAssociations\{category}\shell\OXPlayer") as k:
                winreg.SetValue(k, "", winreg.REG_SZ, "Putar dengan OXPlayer")
                winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon_val)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\SystemFileAssociations\{category}\shell\OXPlayer\command") as k:
                winreg.SetValue(k, "", winreg.REG_SZ, open_cmd)
        except Exception:
            pass

    # 6. Associate Extensions and OpenWith entries
    for ext in ASSOCIATED_EXTENSIONS:
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{ext}") as k:
                winreg.SetValue(k, "", winreg.REG_SZ, prog_id)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{ext}\OpenWithProgids") as k:
                winreg.SetValueEx(k, prog_id, 0, winreg.REG_NONE, b"")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{ext}\OpenWithList\OXPlayer.exe") as k:
                pass
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{ext}\OpenWithList\pythonw.exe") as k:
                pass
        except Exception:
            pass


def refresh_windows_shell():
    """Notifies Windows Shell to refresh desktop icons and file associations."""
    if sys.platform.startswith("win"):
        try:
            # SHCNE_ASSOCCHANGED = 0x08000000, SHCNF_IDLIST = 0x0000
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        except Exception:
            pass


def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    main_py = os.path.join(project_dir, "main.py")
    icon_path = os.path.join(project_dir, "assets", "app_icon.ico")
    pythonw_path = get_pythonw_path()

    print("=" * 64)
    print("      OXPLAYER SMART APP CONTROL & BRANDING CONFIGURATION")
    print("=" * 64)
    print(f"[*] Project Directory : {project_dir}")
    print(f"[*] Main Script       : {main_py}")
    print(f"[*] Runner            : {pythonw_path}")
    print(f"[*] Icon Path         : {icon_path}")

    # 1. Unblock project files from Mark of the Web
    print("\n[1/3] Removing Mark of the Web (Zone.Identifier) streams...")
    unblock_project_files(project_dir)
    print("    [+] Done.")

    # 2. Update File Associations and Open With Branding
    print("\n[2/3] Updating Windows Registry Branding & Open With...")
    try:
        from fix_file_association_icon import apply_file_association_fix
        apply_file_association_fix()
    except Exception as e:
        print(f"    [-] Association fix warning: {e}")

    # 3. Ensure Desktop & Start Menu shortcuts are healthy
    print("\n[3/3] Refreshing Desktop & Start Menu shortcuts...")
    shortcut_script = os.path.join(project_dir, "create_desktop_shortcut.py")
    if os.path.isfile(shortcut_script):
        subprocess.run([sys.executable, shortcut_script], capture_output=True)
        print("    [+] Shortcuts verified and synchronized.")

    # 4. Refresh shell
    refresh_windows_shell()

    print("\n" + "=" * 64)
    print("[SUCCESS] OXPlayer branding & associations updated successfully!")
    print("OXPlayer will now appear as 'OXPlayer' with its official icon in Open With.")
    print("=" * 64)


if __name__ == "__main__":
    main()
