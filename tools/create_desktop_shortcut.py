"""
Utility script to create or repair OXPlayer Desktop and Start Menu shortcuts.
Ensures shortcuts point to the active project directory (e.g. 'D:\\Project FIX\\media player')
using pythonw.exe without a console window, official application icon, and full CLI argument forwarding.
"""

import os
import sys
import shutil
import subprocess
from typing import List

try:
    import win32com.client
except ImportError:
    win32com = None


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


def get_desktop_directories() -> List[str]:
    """Retrieves all valid Desktop folder paths on Windows."""
    dirs: List[str] = []
    # Method 1: WScript.Shell COM
    if win32com is not None:
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            d = shell.SpecialFolders("Desktop")
            if d and os.path.isdir(d) and d not in dirs:
                dirs.append(d)
        except Exception:
            pass

    # Method 2: Standard user profile and OneDrive locations
    userprofile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    std_desktop = os.path.join(userprofile, "Desktop")
    if os.path.isdir(std_desktop) and std_desktop not in dirs:
        dirs.append(std_desktop)

    onedrive_desktop = os.path.join(userprofile, "OneDrive", "Desktop")
    if os.path.isdir(onedrive_desktop) and onedrive_desktop not in dirs:
        dirs.append(onedrive_desktop)

    # Public desktop (if writable)
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


def get_start_menu_programs_dir() -> str:
    """Retrieves the current user's Start Menu Programs folder."""
    if win32com is not None:
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            p = shell.SpecialFolders("Programs")
            if p and os.path.isdir(p):
                return p
        except Exception:
            pass

    appdata = os.environ.get("APPDATA", "")
    p = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs")
    if os.path.isdir(p):
        return p
    return os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "AppData", "Roaming", "Microsoft", "Windows", "Start Menu", "Programs")


def create_shortcut(lnk_path: str, target_path: str, args: str, work_dir: str, icon_path: str = "", desc: str = "") -> bool:
    """Creates a Windows shell shortcut (.lnk) using COM with PowerShell fallback."""
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

    # Method 2: PowerShell fallback
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
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            creationflags=creation_flag
        )
        if os.path.exists(lnk_path):
            return True
    except Exception:
        pass

    return False


def refresh_windows_shell():
    """Notifies Windows Shell to refresh desktop icons and file associations."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            # SHCNE_ASSOCCHANGED = 0x08000000, SHCNF_IDLIST = 0x0000
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        except Exception:
            pass


def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    main_py = os.path.join(project_dir, "main.py")
    icon_path = os.path.join(project_dir, "assets", "app_icon.ico")
    pythonw_path = get_pythonw_path()

    if not os.path.isfile(main_py):
        print(f"[!] Error: main.py not found at {main_py}")
        sys.exit(1)

    print("=" * 60)
    print("      OXPLAYER SHORTCUT REPAIR & CONFIGURATION")
    print("=" * 60)
    print(f"[*] Project Path   : {project_dir}")
    print(f"[*] Main Script    : {main_py}")
    print(f"[*] Python Runner  : {pythonw_path}")
    print(f"[*] App Icon       : {icon_path}")

    # 0. Unblock files from Mark of the Web
    print("[*] Unblocking project and installation files...")
    unblock_path(project_dir)
    installed_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "OXPlayer")
    unblock_path(installed_dir)

    use_exe = "--use-exe" in sys.argv
    sac_active = is_smart_app_control_active()
    installed_exe = os.path.join(installed_dir, "OXPlayer.exe")
    dist_exe = os.path.join(project_dir, "dist", "OXPlayer", "OXPlayer.exe")

    # Prioritize native OXPlayer.exe binary whenever available so Windows Shell and shortcuts
    # use the official OXPlayer application directly.
    if os.path.isfile(installed_exe):
        target_bin = installed_exe
        work_dir = os.path.dirname(installed_exe)
        icon_path = os.path.join(work_dir, "assets", "app_icon.ico")
        args = ""
        print(f"[*] Target Executable: {installed_exe}")
    elif os.path.isfile(dist_exe):
        target_bin = dist_exe
        work_dir = os.path.dirname(dist_exe)
        icon_path = os.path.join(work_dir, "assets", "app_icon.ico")
        args = ""
        print(f"[*] Target Executable: {dist_exe}")
    elif os.path.isfile(main_py):
        target_bin = pythonw_path
        work_dir = project_dir
        args = f'"{main_py}"'
        print(f"[*] Target Runner (Fallback) : {pythonw_path}")
    else:
        target_bin = installed_exe
        work_dir = os.path.dirname(installed_exe)
        icon_path = os.path.join(work_dir, "assets", "app_icon.ico")
        args = ""
        print(f"[*] Target Executable: {installed_exe}")

    desc = "OXPlayer - Modern Media Player"

    # 1. Desktop Shortcuts
    desktops = get_desktop_directories()
    desktop_success_count = 0
    for d in desktops:
        lnk_path = os.path.join(d, "OXPlayer.lnk")
        print(f"[*] Creating/Updating Desktop shortcut: {lnk_path}")
        if create_shortcut(lnk_path, target_bin, args, work_dir, icon_path, desc):
            print(f"    [+] Successfully updated: {lnk_path}")
            desktop_success_count += 1
        else:
            print(f"    [-] Failed to create: {lnk_path}")

    # 2. Start Menu Shortcut
    programs_dir = get_start_menu_programs_dir()
    sm_oxplayer_dir = os.path.join(programs_dir, "OXPlayer")
    os.makedirs(sm_oxplayer_dir, exist_ok=True)
    sm_lnk_path = os.path.join(sm_oxplayer_dir, "OXPlayer.lnk")
    print(f"[*] Creating/Updating Start Menu shortcut: {sm_lnk_path}")
    if create_shortcut(sm_lnk_path, target_bin, args, work_dir, icon_path, desc):
        print(f"    [+] Successfully updated: {sm_lnk_path}")
    else:
        print("    [-] Failed to update Start Menu shortcut.")

    # 3. Repair File Association & Open With Icon in Windows Registry
    try:
        from fix_file_association_icon import apply_file_association_fix
        apply_file_association_fix()
    except Exception as e:
        print(f"[-] File association repair warning: {e}")

    # 4. Refresh Windows Shell Cache
    refresh_windows_shell()
    print("=" * 60)
    if desktop_success_count > 0:
        print("[OK] Desktop shortcut & File Association Icon fixed successfully!")
    else:
        print("[!] Warning: Could not create desktop shortcut in standard folders.")
    print("=" * 60)


if __name__ == "__main__":
    main()
