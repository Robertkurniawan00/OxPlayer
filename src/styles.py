"""
Clean, neutral dark stylesheet for OXPlayer.
"""

PALETTE = {
    "bg_main": "#141417",
    "bg_surface": "#1a1a1e",
    "bg_card": "#202025",
    "bg_hover": "#2a2a30",
    "bg_btn": "#242429",
    "bg_btn_hover": "#2f2f36",
    "bg_selected": "#2e2e36",
    "text_main": "#e4e4e7",
    "text_light": "#ffffff",
    "text_muted": "#9ca3af",
    "border_subtle": "#242429",
    "border_normal": "#32323a",
    "border_active": "#52525b",
    "accent_color": "#52525b",
    "slider_subpage": "#e4e4e7",
    "slider_groove": "rgba(255, 255, 255, 0.20)",
    "slider_handle": "#ffffff",
}


def get_theme_stylesheet(theme_name: str = "Obsidian Dark") -> str:
    p = PALETTE
    return f"""
QMainWindow, QDialog {{
    background-color: {p["bg_main"]};
    color: {p["text_main"]};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
}}

QWidget {{
    background-color: transparent;
    color: {p["text_main"]};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
}}

/* MenuBar */
QMenuBar {{
    background-color: {p["bg_surface"]};
    color: {p["text_main"]};
    border-bottom: 1px solid {p["border_subtle"]};
    padding: 2px 4px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 4px 10px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background: {p["bg_hover"]};
    color: {p["text_light"]};
}}

/* Context & Dropdown Menus */
QMenu {{
    background-color: {p["bg_card"]};
    color: {p["text_main"]};
    border: 1px solid {p["border_normal"]};
    border-radius: 4px;
    padding: 4px;
}}
QMenu::item {{
    padding: 5px 24px 5px 20px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background-color: {p["bg_hover"]};
    color: {p["text_light"]};
}}
QMenu::separator {{
    height: 1px;
    background-color: {p["border_subtle"]};
    margin: 4px 0px;
}}

/* Bottom Control Dock */
#ModernFloatingDock {{
    background-color: transparent;
    border: none;
}}

QLabel#DockVolText {{
    color: {p["text_muted"]};
    font-size: 11px;
    font-weight: 500;
    min-width: 36px;
    padding-left: 2px;
}}

/* Seekbar */
QSlider#DockSeekSlider {{
    min-height: 20px;
    max-height: 20px;
}}
QSlider#DockSeekSlider::groove:horizontal {{
    height: 4px;
    background: {p["slider_groove"]};
    border-radius: 2px;
}}
QSlider#DockSeekSlider::sub-page:horizontal {{
    background: {p["slider_subpage"]};
    border-radius: 2px;
}}
QSlider#DockSeekSlider::handle:horizontal {{
    background: {p["slider_handle"]};
    border: 1px solid rgba(0, 0, 0, 0.30);
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
}}
QSlider#DockSeekSlider::handle:horizontal:hover {{
    background: {p["slider_handle"]};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}

/* Dock Buttons */
QToolButton#DockTileBtn, QPushButton#DockTileBtn {{
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    color: #ffffff;
    font-size: 13px;
    min-width: 34px;
    max-width: 34px;
    min-height: 32px;
    max-height: 32px;
    padding: 0px;
}}
QToolButton#DockTileBtn:hover, QPushButton#DockTileBtn:hover {{
    background-color: rgba(255, 255, 255, 0.18);
    border-color: rgba(255, 255, 255, 0.22);
    color: #ffffff;
}}
QToolButton#DockTileBtn:pressed, QPushButton#DockTileBtn:pressed {{
    background-color: rgba(255, 255, 255, 0.05);
}}

/* Speed Button */
QPushButton#DockSpeedPillBtn {{
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    color: #ffffff;
    font-size: 12px;
    font-weight: 500;
    padding: 3px 10px;
    min-height: 24px;
    max-height: 28px;
}}
QPushButton#DockSpeedPillBtn:hover {{
    background-color: rgba(255, 255, 255, 0.18);
    border-color: rgba(255, 255, 255, 0.22);
}}

/* Dock Time Label */
QLabel#DockTimeLabel {{
    color: {p["text_light"]};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
    font-weight: 500;
    padding: 0 4px;
}}

/* Dock Volume Slider */
QSlider#DockVolumeSlider {{
    min-height: 18px;
    max-height: 18px;
}}
QSlider#DockVolumeSlider::groove:horizontal {{
    height: 3px;
    background: {p["slider_groove"]};
    border-radius: 1.5px;
}}
QSlider#DockVolumeSlider::sub-page:horizontal {{
    background: {p["slider_subpage"]};
    border-radius: 1.5px;
}}
QSlider#DockVolumeSlider::handle:horizontal {{
    background: {p["slider_handle"]};
    border: 1px solid rgba(0, 0, 0, 0.25);
    width: 10px;
    height: 10px;
    margin: -3.5px 0;
    border-radius: 5px;
}}

/* Standard Push Buttons */
QPushButton {{
    background-color: {p["bg_btn"]};
    border: 1px solid {p["border_normal"]};
    color: {p["text_main"]};
    border-radius: 4px;
    padding: 5px 12px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {p["bg_btn_hover"]};
    border-color: {p["border_active"]};
    color: {p["text_light"]};
}}
QPushButton:pressed {{
    background-color: {p["bg_main"]};
}}
QPushButton:disabled {{
    background-color: {p["bg_surface"]};
    border-color: {p["border_subtle"]};
    color: {p["text_muted"]};
}}

/* Tool Buttons */
QToolButton {{
    background-color: {p["bg_btn"]};
    border: 1px solid {p["border_normal"]};
    border-radius: 4px;
    padding: 5px 9px;
    color: {p["text_main"]};
    font-size: 12px;
}}
QToolButton:hover {{
    background-color: {p["bg_btn_hover"]};
    border-color: {p["border_active"]};
    color: {p["text_light"]};
}}
QToolButton:pressed {{
    background-color: {p["bg_main"]};
}}

/* Generic Sliders */
QSlider::groove:horizontal {{
    height: 4px;
    background: {p["border_normal"]};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {p["slider_subpage"]};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {p["slider_handle"]};
    border: 1px solid {p["border_active"]};
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
}}

/* Labels */
QLabel {{
    color: {p["text_main"]};
    font-size: 12px;
}}

/* Playlist Panel */
#PlaylistWidget {{
    background-color: {p["bg_surface"]};
    border-left: 1px solid {p["border_subtle"]};
}}
QListWidget {{
    background-color: {p["bg_surface"]};
    border: 1px solid {p["border_subtle"]};
    border-radius: 4px;
    color: {p["text_main"]};
    outline: none;
}}
QListWidget::item {{
    padding: 6px 10px;
    border-bottom: 1px solid {p["border_subtle"]};
}}
QListWidget::item:hover {{
    background-color: {p["bg_hover"]};
    color: {p["text_light"]};
}}
QListWidget::item:selected {{
    background-color: {p["bg_selected"]};
    color: {p["text_light"]};
}}

/* LineEdit */
QLineEdit {{
    background-color: {p["bg_card"]};
    border: 1px solid {p["border_normal"]};
    border-radius: 4px;
    color: {p["text_light"]};
    padding: 5px 10px;
}}
QLineEdit:focus {{
    border: 1px solid {p["border_active"]};
}}

/* ComboBox */
QComboBox {{
    background-color: {p["bg_btn"]};
    border: 1px solid {p["border_normal"]};
    border-radius: 4px;
    padding: 4px 10px;
    color: {p["text_main"]};
}}
QComboBox::drop-down {{
    border: none;
}}
QComboBox QAbstractItemView {{
    background-color: {p["bg_card"]};
    border: 1px solid {p["border_normal"]};
    color: {p["text_main"]};
    selection-background-color: {p["bg_hover"]};
}}

/* ScrollBars */
QScrollBar:vertical {{
    border: none;
    background: {p["bg_surface"]};
    width: 8px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {p["border_normal"]};
    min-height: 20px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p["border_active"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* Message Boxes */
QMessageBox {{
    background-color: {p["bg_surface"]};
    color: {p["text_main"]};
}}
QMessageBox QLabel {{
    color: {p["text_main"]};
    font-size: 12px;
}}
QMessageBox QPushButton {{
    background-color: {p["bg_btn"]};
    border: 1px solid {p["border_normal"]};
    border-radius: 4px;
    padding: 5px 16px;
    min-width: 65px;
    color: {p["text_main"]};
}}
QMessageBox QPushButton:hover {{
    background-color: {p["bg_btn_hover"]};
    border-color: {p["border_active"]};
    color: {p["text_light"]};
}}

/* Tab Widgets */
QTabWidget::pane {{
    border: 1px solid {p["border_normal"]};
    border-radius: 4px;
    background-color: {p["bg_surface"]};
    top: -1px;
}}
QTabBar::tab {{
    background-color: {p["bg_main"]};
    color: {p["text_muted"]};
    border: 1px solid {p["border_subtle"]};
    border-bottom: none;
    padding: 6px 14px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:hover {{
    background-color: {p["bg_hover"]};
    color: {p["text_light"]};
}}
QTabBar::tab:selected {{
    background-color: {p["bg_surface"]};
    color: {p["text_light"]};
    border: 1px solid {p["border_normal"]};
    border-bottom: 1px solid {p["bg_surface"]};
    font-weight: 600;
}}

/* Group Boxes */
QGroupBox {{
    border: 1px solid {p["border_normal"]};
    border-radius: 4px;
    margin-top: 12px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
    color: {p["text_main"]};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    background-color: {p["bg_main"]};
    color: {p["text_light"]};
}}

/* CheckBoxes & RadioButtons */
QCheckBox, QRadioButton {{
    spacing: 8px;
    color: {p["text_main"]};
    font-size: 12px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 15px;
    height: 15px;
    background-color: {p["bg_card"]};
    border: 1px solid {p["border_normal"]};
    border-radius: 3px;
}}
QRadioButton::indicator {{
    border-radius: 8px;
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {p["border_active"]};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {p["text_main"]};
    border-color: {p["text_light"]};
}}

/* SpinBoxes */
QSpinBox, QDoubleSpinBox {{
    background-color: {p["bg_card"]};
    border: 1px solid {p["border_normal"]};
    border-radius: 4px;
    color: {p["text_light"]};
    padding: 4px 8px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {p["border_active"]};
}}

/* Progress Bars */
QProgressBar {{
    background-color: {p["bg_surface"]};
    border: 1px solid {p["border_subtle"]};
    border-radius: 4px;
    text-align: center;
    color: {p["text_light"]};
    font-size: 10px;
}}
QProgressBar::chunk {{
    background-color: {p["text_muted"]};
    border-radius: 3px;
}}
"""
