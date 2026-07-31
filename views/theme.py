"""Styling, palette, icon, and display-config constants for the View layer."""
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFontDatabase,
    QIcon,
    QLinearGradient,
    QPainter,
    QPalette,
    QPixmap,
    QPolygonF,
)

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONT_MONO = "JetBrains Mono"


def load_custom_fonts() -> None:
    """Register the bundled JetBrains Mono font files with Qt."""
    for font_file in FONTS_DIR.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(font_file))

CPU_LIMIT_OPTIONS = [
    ("Low (20%)", 20),
    ("Medium (50%) - recommended", 50),
    ("High (70%)", 70),
    ("Unlimited (100%)", 100),
]

DETAIL_SECTIONS = [
    ("Video", [
        ("Resolution", "resolution"),
        ("Megapixels", "megapixels"),
        ("FPS", "fps"),
        ("Video Codec", "video_codec"),
        ("Profile", "profile"),
        ("Bit Depth", "bit_depth"),
        ("Pixel Format", "pix_fmt"),
        ("Color Space", "color_space"),
        ("Video Bitrate (Mbps)", "video_bitrate_mbps"),
        ("Bits / Pixel", "bits_per_pixel"),
        ("Quality Density", "quality_density"),
    ]),
    ("Audio", [
        ("Audio Codec", "audio_codec"),
        ("Audio Bitrate (kbps)", "audio_bitrate_kbps"),
    ]),
    ("File", [
        ("File", "file"),
        ("Overall Bitrate (Mbps)", "overall_bitrate_mbps"),
        ("Size (MB)", "size_mb"),
        ("Duration (s)", "duration_s"),
    ]),
]

TABLE_COLUMNS = [
    ("File", "file"),
    ("Resolution", "resolution"),
    ("FPS", "fps"),
    ("Codec", "video_codec"),
    ("Bit Depth", "bit_depth"),
    ("Video Bitrate (Mbps)", "video_bitrate_mbps"),
    ("Bits/Pixel", "bits_per_pixel"),
    ("Quality", "quality_density"),
    ("Size (MB)", "size_mb"),
]

# Nord ("Nordic Dark") palette — https://www.nordtheme.com/
NORD0 = "#2e3440"
NORD1 = "#3b4252"
NORD2 = "#434c5e"
NORD3 = "#4c566a"
NORD4 = "#d8dee9"
NORD6 = "#eceff4"
NORD7 = "#8fbcbb"
NORD8 = "#88c0d0"
NORD11 = "#bf616a"
NORD12 = "#d08770"
NORD13 = "#ebcb8b"
NORD14 = "#a3be8c"

STATUS_COLORS = {
    "idle": NORD3,
    "running": NORD13,
    "done": NORD14,
    "error": NORD11,
    "cancelled": NORD12,
}

QUALITY_BADGE_COLORS = {
    "Excellent": (NORD1, NORD14),
    "Good": (NORD1, NORD8),
    "Fair": (NORD1, NORD13),
    "Heavily compressed": (NORD1, NORD11),
}

ACCENT = NORD8
ACCENT_HOVER = NORD7

ICON_COLOR = NORD4
ICON_COLOR_DISABLED = NORD3
ICON_COLOR_DANGER = NORD11

STYLE_SHEET = f"""
QWidget {{
    font-family: "{FONT_MONO}";
    font-size: 9pt;
}}
QGroupBox {{
    font-weight: 600;
    border: 1px solid palette(mid);
    border-radius: 0px;
    margin-top: 14px;
    padding-top: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
}}
QFrame#sidebarPanel {{
    border: none;
    border-right: 1px solid palette(mid);
}}
QFrame#optionsSection, QFrame#folderSection {{
    border: none;
    border-bottom: 1px solid palette(mid);
}}
QLineEdit, QComboBox, QDoubleSpinBox {{
    padding: 5px 8px;
    border: 1px solid palette(mid);
    border-radius: 0px;
    background-color: palette(base);
    min-height: 20px;
}}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QPushButton {{
    padding: 7px 16px;
    border-radius: 0px;
    border: 1px solid palette(mid);
    background-color: palette(button);
}}
QPushButton:hover {{
    background-color: palette(light);
}}
QPushButton#startButton {{
    background-color: {ACCENT};
    color: {NORD0};
    border: none;
    font-weight: 600;
    padding: 8px 22px;
}}
QPushButton#startButton:hover:enabled {{
    background-color: {ACCENT_HOVER};
}}
QPushButton#startButton:disabled {{
    background-color: {NORD3};
    color: {NORD4};
}}
QPushButton#cancelButton:enabled {{
    border: 1px solid {NORD11};
    color: {NORD11};
    font-weight: 600;
}}
QPushButton#cancelButton:hover:enabled {{
    background-color: {NORD11};
    color: {NORD6};
}}
QPushButton#pauseButton:enabled {{
    border: 1px solid {NORD12};
    color: {NORD12};
    font-weight: 600;
}}
QPushButton#pauseButton:hover:enabled {{
    background-color: {NORD12};
    color: {NORD6};
}}
QProgressBar {{
    border: 1px solid palette(mid);
    border-radius: 0px;
    text-align: center;
    min-height: 22px;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 0px;
}}
QPlainTextEdit {{
    background-color: {NORD0};
    color: {NORD4};
    border: 1px solid palette(mid);
    border-radius: 0px;
    padding: 6px;
    selection-background-color: {ACCENT};
}}
QTableWidget {{
    border: 1px solid palette(mid);
    border-radius: 0px;
    gridline-color: palette(mid);
}}
QHeaderView::section {{
    padding: 6px;
    border: none;
    border-bottom: 2px solid palette(mid);
    font-weight: 600;
}}
QCheckBox {{
    spacing: 8px;
}}
QTabWidget::pane {{
    border: 1px solid palette(mid);
    border-radius: 0px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 0px;
    border-top-right-radius: 0px;
}}
QTabBar::tab:selected {{
    background: palette(button);
    border-bottom: 2px solid {ACCENT};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    background: palette(light);
}}
"""


def build_dark_palette() -> QPalette:
    """Nord ("Nordic Dark") palette, applied regardless of the OS theme setting."""
    window = QColor(NORD0)
    base = QColor("#262b35")
    alt_base = QColor(NORD1)
    button = QColor(NORD1)
    text = QColor(NORD6)
    disabled_text = QColor(NORD3)

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, alt_base)
    palette.setColor(QPalette.ColorRole.ToolTipBase, window)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, button)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor(NORD11))
    palette.setColor(QPalette.ColorRole.Link, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(NORD0))
    palette.setColor(QPalette.ColorRole.PlaceholderText, disabled_text)
    palette.setColor(QPalette.ColorRole.Mid, QColor(NORD2))
    palette.setColor(QPalette.ColorRole.Light, QColor(NORD3))
    palette.setColor(QPalette.ColorRole.Dark, QColor("#242933"))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled_text)
    return palette


def make_app_icon(size: int = 64) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0, QColor(ACCENT))
    gradient.setColorAt(1, QColor("#1a4f8a"))
    painter.setBrush(QBrush(gradient))
    painter.setPen(Qt.PenStyle.NoPen)
    radius = size * 0.22
    painter.drawRoundedRect(0, 0, size, size, radius, radius)
    triangle = QPolygonF([
        QPointF(size * 0.38, size * 0.27),
        QPointF(size * 0.38, size * 0.73),
        QPointF(size * 0.75, size * 0.5),
    ])
    painter.setBrush(QColor("white"))
    painter.drawPolygon(triangle)
    painter.end()
    return QIcon(pixmap)
