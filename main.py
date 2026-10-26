"""
Hybrid Media Player
Main entrypoint for the application.
Supports:
- CLI argument file playback: MediaPlayer.exe "video.mp4"
- Start From Timestamp: MediaPlayer.exe "video.mp4" --time=01:23:45 or --start-at=90s
"""

import sys
import os

# Ensure UTF-8 encoding on Windows console streams for CJK / Korean / special filenames
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# Ensure proper DPI scaling and visual styles
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

# Ensure current directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from src.main_window import MainWindow
from src.engine import setup_engine_environment

def parse_cli_arguments():
    file_to_play = None
    start_time_str = ""

    for arg in sys.argv[1:]:
        if arg.startswith(("--time=", "--start-at=", "--start-time=")):
            start_time_str = arg.split("=", 1)[1].strip().strip('"\'')
        elif arg.startswith("-t="):
            start_time_str = arg.split("=", 1)[1].strip().strip('"\'')
        elif not arg.startswith("-") and not file_to_play:
            # Check for URL fragment #t=120s
            if "#t=" in arg:
                parts = arg.split("#t=", 1)
                file_to_play = parts[0].strip().strip('"\'')
                start_time_str = parts[1].strip().strip('"\'')
            else:
                file_to_play = arg.strip().strip('"\'')

    return file_to_play, start_time_str


def excepthook(exc_type, exc_value, exc_tb):
    import traceback
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        log_dir = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        crash_log = os.path.join(log_dir, "OXPlayer_crash.log")
        with open(crash_log, "a", encoding="utf-8") as f:
            f.write(tb + "\n")
    except Exception:
        pass
    try:
        if sys.stderr is not None:
            print(tb, file=sys.stderr)
    except Exception:
        pass

sys.excepthook = excepthook

def get_app_icon_path():
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "assets", "app_icon.ico"))
        candidates.append(os.path.join(sys._MEIPASS, "_internal", "assets", "app_icon.ico"))
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    candidates.append(os.path.join(exe_dir, "assets", "app_icon.ico"))
    candidates.append(os.path.join(exe_dir, "_internal", "assets", "app_icon.ico"))
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(script_dir, "assets", "app_icon.ico"))
    candidates.append(os.path.join(os.getcwd(), "assets", "app_icon.ico"))

    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


def apply_native_win32_icon(hwnd, icon_path):
    """Sets WM_SETICON and window class icons directly via Win32 API for taskbar."""
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


def restore_and_activate_window(window):
    """Brings window to front and restores from minimized state reliably."""
    try:
        if window.isMinimized():
            window.showNormal()
        window.show()
        window.raise_()
        window.activateWindow()

        if sys.platform.startswith("win"):
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = int(window.winId())
            
            # 9 = SW_RESTORE
            user32.ShowWindow(hwnd, 9)
            user32.AllowSetForegroundWindow(-1)

            fore_hwnd = user32.GetForegroundWindow()
            fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, None)
            app_thread = user32.GetCurrentThreadId()

            if fore_thread != app_thread:
                user32.AttachThreadInput(fore_thread, app_thread, True)
                user32.SetForegroundWindow(hwnd)
                user32.SetFocus(hwnd)
                user32.AttachThreadInput(fore_thread, app_thread, False)
            else:
                user32.SetForegroundWindow(hwnd)
                user32.SetFocus(hwnd)
    except Exception:
        pass


def main():
    file_arg, start_time_str = parse_cli_arguments()

    # Only use explicit AppUserModelID in Python development mode so python.exe doesn't show the snake icon.
    # In frozen/compiled mode (OXPlayer.exe), Windows native shell uses OXPlayer.exe's embedded icon directly.
    if sys.platform == "win32" and not getattr(sys, "frozen", False):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("oxplayer.mediaplayer.modern.2.5.0")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("OXPlayer")
    app.setApplicationDisplayName("")

    # --- Single Instance IPC Check (VLC / PotPlayer style) ---
    ipc_server_name = f"OXPlayer_SingleInstance_{os.environ.get('USERNAME', 'Default')}"
    probe_socket = QLocalSocket()
    probe_socket.connectToServer(ipc_server_name)
    if probe_socket.waitForConnected(400):
        # Existing instance is running! Send payload and transfer focus.
        if sys.platform.startswith("win"):
            try:
                import ctypes
                ctypes.windll.user32.AllowSetForegroundWindow(-1)
            except Exception:
                pass

        payload = json.dumps({
            "file": file_arg or "",
            "start_time": start_time_str or "",
            "action": "open" if file_arg else "activate"
        }).encode("utf-8")
        probe_socket.write(payload)
        probe_socket.flush()
        probe_socket.waitForBytesWritten(1000)
        probe_socket.disconnectFromServer()
        sys.exit(0)

    # We are the primary instance.
    # Set app and window icon for title bar and Windows taskbar
    icon_path = get_app_icon_path()
    if icon_path:
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)

    # Start IPC Server for subsequent instances
    ipc_server = QLocalServer()
    QLocalServer.removeServer(ipc_server_name)
    ipc_server.listen(ipc_server_name)
    app._ipc_server = ipc_server  # Keep reference alive

    # Verify core multimedia environment
    engine_dir = setup_engine_environment()
    if not engine_dir:
        QMessageBox.warning(
            None,
            "Peringatan Komponen Multimedia",
            "Pustaka pemrosesan multimedia mandiri tidak ditemukan secara otomatis.\n"
            "Pastikan folder 'core_bin' atau pustaka inti tersedia."
        )

    window = MainWindow()
    if icon_path:
        window.setWindowIcon(QIcon(icon_path))

    # Connect IPC server handler to primary window
    def handle_ipc_connection():
        client = ipc_server.nextPendingConnection()
        if not client:
            return

        buffer = bytearray()

        def process_data():
            if not buffer:
                return
            try:
                msg = json.loads(buffer.decode("utf-8", errors="ignore"))
                f_path = msg.get("file", "")
                t_start = msg.get("start_time", "")

                restore_and_activate_window(window)

                if f_path:
                    allowed_schemes = ("http://", "https://", "rtsp://", "rtp://", "mms://", "udp://")
                    is_safe_url = any(f_path.lower().startswith(s) for s in allowed_schemes)
                    if os.path.exists(f_path) or is_safe_url:
                        window.playlist.add_paths([f_path], auto_play=False)
                        window.play_file(f_path, start_time_str=t_start)
                buffer.clear()
            except Exception:
                pass

        def on_ready_read():
            buffer.extend(bytes(client.readAll()))
            process_data()

        client.readyRead.connect(on_ready_read)
        client.disconnected.connect(process_data)

    ipc_server.newConnection.connect(handle_ipc_connection)

    window.show()

    # Apply native Win32 icons directly to the top-level HWND and notify Windows Shell
    if icon_path and sys.platform.startswith("win"):
        try:
            import ctypes
            apply_native_win32_icon(int(window.winId()), icon_path)
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        except Exception:
            pass

    # Handle initial command-line arguments (file + optional start timestamp)
    if file_arg:
        allowed_schemes = ("http://", "https://", "rtsp://", "rtp://", "mms://", "udp://")
        is_safe_url = any(file_arg.lower().startswith(s) for s in allowed_schemes)
        if os.path.exists(file_arg) or is_safe_url:
            window.playlist.add_paths([file_arg], auto_play=False)
            window.play_file(file_arg, start_time_str=start_time_str)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
