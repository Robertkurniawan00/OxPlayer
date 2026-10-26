"""
OXPlayer Comprehensive Build & Packaging Automation Script.
Produces:
1. Standalone OXPlayer Application (dist/OXPlayer/OXPlayer.exe) with
   native hardware decoding runtime.
2. Windows 7 - 11 Single-File Installation Executable (dist/OXPlayer_Setup.exe).
"""

import os
import sys
import shutil
import subprocess

def build():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    icon_path = os.path.join(project_dir, "assets", "app_icon.ico")
    manifest_path = os.path.join(project_dir, "assets", "oxplayer_compatibility.manifest")
    version_info_path = os.path.join(project_dir, "assets", "version_info.txt")
    setup_version_info_path = os.path.join(project_dir, "assets", "setup_version_info.txt")
    main_py = os.path.join(project_dir, "main.py")
    installer_py = os.path.join(project_dir, "installer.py")

    print("=" * 68)
    print("      OXPLAYER BUILD AUTOMATION (WINDOWS 7 - 11 COMPATIBILITY)")
    print("=" * 68)
    print(f"[*] Project Directory : {project_dir}")
    print(f"[*] Main entry        : {main_py}")
    print(f"[*] App Icon          : {icon_path}")
    print(f"[*] Manifest          : {manifest_path}")

    # --- Step 0: Ensure no existing processes lock files ---
    try:
        subprocess.run(["taskkill", "/F", "/IM", "OXPlayer.exe"], capture_output=True)
        subprocess.run(["taskkill", "/F", "/IM", "OXPlayer_Setup.exe"], capture_output=True)
    except Exception:
        pass

    # --- Step 1: Build Standalone OXPlayer App ---
    print("\n[1/3] Compiling OXPlayer.exe with PyInstaller...")
    cmd_app = [
        sys.executable, "-m", "PyInstaller",
        "--name=OXPlayer",
        "--windowed",
        "--noconfirm",
        "--clean",
        f"--icon={icon_path}",
        f"--manifest={manifest_path}",
        f"--version-file={version_info_path}",
        f"--add-data=assets{os.pathsep}assets",
        "--hidden-import=PyQt6.QtWidgets",
        "--hidden-import=PyQt6.QtCore",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=PyQt6.QtNetwork",
        "--hidden-import=vlc",
        "--hidden-import=urllib.request",
        "--hidden-import=urllib.parse",
        "--hidden-import=json",
        "--hidden-import=src",
        "--hidden-import=src.engine",
        "--hidden-import=src.main_window",
        "--hidden-import=src.pip_window",
        "--hidden-import=src.resume_banner",
        "--hidden-import=src.next_episode_banner",
        "--hidden-import=src.dialogs",
        "--hidden-import=src.playlist",
        "--hidden-import=src.osd",
        "--hidden-import=src.styles",
        "--hidden-import=ctypes",
        "--hidden-import=ctypes.wintypes",
        "--hidden-import=PIL",
        "--exclude-module=PyQt6.QtQml",
        "--exclude-module=PyQt6.QtQuick",
        "--exclude-module=PyQt6.QtWebEngineCore",
        "--exclude-module=PyQt6.QtPdf",
        "--exclude-module=PyQt6.QtPdfWidgets",
        "--exclude-module=matplotlib",
        "--exclude-module=scipy",
        "--exclude-module=pandas",
        "--exclude-module=torch",
        main_py
    ]

    res_app = subprocess.run(cmd_app)
    if res_app.returncode != 0:
        print("[!] Building OXPlayer.exe failed!")
        sys.exit(res_app.returncode)

    dist_dir = os.path.join(project_dir, "dist", "OXPlayer")
    exe_path = os.path.join(dist_dir, "OXPlayer.exe")

    # Clean legacy folders if present
    vlc_bin_old = os.path.join(dist_dir, "vlc_bin")
    if os.path.exists(vlc_bin_old):
        shutil.rmtree(vlc_bin_old, ignore_errors=True)
    for old_bin in [
        os.path.join(dist_dir, "assets", "bin"),
        os.path.join(dist_dir, "_internal", "assets", "bin")
    ]:
        if os.path.exists(old_bin):
            shutil.rmtree(old_bin, ignore_errors=True)

    # --- Step 2: Bundle Standalone Core Decoding Engine ---
    print("\n[2/3] Bundling Standalone Multimedia Core Decoding Engine...")
    candidate_sources = [
        os.path.join(project_dir, "core_bin"),
        os.path.join(dist_dir, "core_bin"),
        r"C:\Program Files\VideoLAN\VLC",
        r"C:\Program Files (x86)\VideoLAN\VLC"
    ]
    vlc_source = None
    for cand in candidate_sources:
        if cand and os.path.isdir(cand) and os.path.exists(os.path.join(cand, "libvlc.dll")):
            vlc_source = cand
            break

    dest_dir = os.path.join(dist_dir, "core_bin")
    os.makedirs(dest_dir, exist_ok=True)
    if vlc_source:
        print(f"[*] Copying core media runtime libraries from: {vlc_source}")
        for dll in ["libvlc.dll", "libvlccore.dll"]:
            src_dll = os.path.join(vlc_source, dll)
            if os.path.exists(src_dll):
                shutil.copy2(src_dll, dest_dir)

        plugins_src = os.path.join(vlc_source, "plugins")
        plugins_dest = os.path.join(dest_dir, "plugins")
        if os.path.exists(plugins_src) and not os.path.exists(plugins_dest):
            print("[*] Copying multimedia codec plugins to core_bin...")
            shutil.copytree(plugins_src, plugins_dest)
    else:
        print("[!] Warning: No core VLC runtime found to bundle into core_bin!")

    # Copy official assets (icon & logo) to dist_dir
    dist_assets = os.path.join(dist_dir, "assets")
    os.makedirs(dist_assets, exist_ok=True)
    for asset_file in ["app_icon.ico", "app_logo.png", "oxplayer_compatibility.manifest"]:
        src_a = os.path.join(project_dir, "assets", asset_file)
        if os.path.exists(src_a):
            shutil.copy2(src_a, dist_assets)
            internal_assets = os.path.join(dist_dir, "_internal", "assets")
            if os.path.isdir(internal_assets):
                shutil.copy2(src_a, internal_assets)

    # Copy src package to dist_dir for full dynamic fallback
    dist_src = os.path.join(dist_dir, "src")
    if os.path.exists(dist_src):
        shutil.rmtree(dist_src, ignore_errors=True)
    shutil.copytree(os.path.join(project_dir, "src"), dist_src)

    # --- Step 3: Build Windows 7 - 11 Single-File Setup Executable ---
    print("\n[3/3] Compiling OXPlayer_Setup.exe Installer Wizard...")
    assets_dir = os.path.join(project_dir, "assets")
    cmd_inst = [
        sys.executable, "-m", "PyInstaller",
        "--name=OXPlayer_Setup",
        "--onefile",
        "--windowed",
        "--noconfirm",
        f"--icon={icon_path}",
        f"--manifest={manifest_path}",
        f"--version-file={setup_version_info_path}",
        f"--add-data={assets_dir}{os.pathsep}assets",
        f"--add-data={dist_dir}{os.pathsep}payload",
        "--hidden-import=PyQt6.QtWidgets",
        "--hidden-import=PyQt6.QtCore",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=win32com.client",
        "--exclude-module=matplotlib",
        "--exclude-module=torch",
        "--exclude-module=pandas",
        installer_py
    ]

    res_inst = subprocess.run(cmd_inst)
    if res_inst.returncode != 0:
        print("[!] Building OXPlayer_Setup.exe failed!")
        sys.exit(res_inst.returncode)

    installer_exe = os.path.join(project_dir, "dist", "OXPlayer_Setup.exe")
    root_installer = os.path.join(project_dir, "OXPlayer_Setup.exe")
    if os.path.exists(installer_exe):
        try:
            shutil.copy2(installer_exe, root_installer)
            print(f"[*] Primary Setup Executable copied to root: {root_installer}")
        except Exception as e:
            print(f"[!] Warning: Could not copy to root: {e}")

    # Remove any stray .bat, .lnk, .spec, or orphaned .exe in root folder to ensure only the installer exe remains
    for stray in ["OXPlayer.exe", "Run_OXPlayer.bat", "OXPlayer.lnk", "Run_MediaPlayer.bat", "MediaPlayer.lnk", "OXPlayer.spec", "OXPlayer_Setup.spec"]:
        p = os.path.join(project_dir, stray)
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    print("\n" + "=" * 68)
    print("                    BUILD COMPLETED SUCCESSFULLY!")
    print("=" * 68)
    print(f"1. Windows Setup Package  : {root_installer}")
    print(f"2. Distribution Setup     : {installer_exe}")
    print(f"3. Standalone Core App    : {exe_path}")
    print("=" * 68)

if __name__ == "__main__":
    build()
