"""Styling, palette, icon, and display-config constants for the View layer."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPalette,
    QPixmap,
    QPolygonF,
)

CPU_LIMIT_OPTIONS = [
    ("Low (~20% of cores)", 20),
    ("Medium (~50% of cores) - recommended", 50),
    ("High (~70% of cores)", 70),
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

STATUS_COLORS = {
    "idle": "#808080",
    "running": "#d68a10",
    "done": "#2e9e44",
    "error": "#d64545",
    "cancelled": "#d68a10",
}

QUALITY_BADGE_COLORS = {
    "Excellent": ("#d7f5df", "#1e7a34"),
    "Good": ("#dbe9fb", "#1a56a8"),
    "Fair": ("#fdf1d0", "#a1750a"),
    "Heavily compressed": ("#fbdada", "#a3242c"),
}

ACCENT = "#2f7dd8"
ACCENT_HOVER = "#3d8ae6"

STYLE_SHEET = f"""
QWidget {{
    font-size: 10.5pt;
}}
QGroupBox {{
    font-weight: 600;
    border: 1px solid palette(mid);
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
}}
QLineEdit, QComboBox, QDoubleSpinBox {{
    padding: 5px 8px;
    border: 1px solid palette(mid);
    border-radius: 4px;
    background-color: palette(base);
    min-height: 20px;
}}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QPushButton {{
    padding: 7px 16px;
    border-radius: 5px;
    border: 1px solid palette(mid);
    background-color: palette(button);
}}
QPushButton:hover {{
    background-color: palette(light);
}}
QPushButton#startButton {{
    background-color: {ACCENT};
    color: white;
    border: none;
    font-weight: 600;
    padding: 8px 22px;
}}
QPushButton#startButton:hover:enabled {{
    background-color: {ACCENT_HOVER};
}}
QPushButton#startButton:disabled {{
    background-color: #9fb8d6;
    color: #f0f0f0;
}}
QPushButton#cancelButton:enabled {{
    border: 1px solid #d64545;
    color: #d64545;
    font-weight: 600;
}}
QPushButton#cancelButton:hover:enabled {{
    background-color: #d64545;
    color: white;
}}
QProgressBar {{
    border: 1px solid palette(mid);
    border-radius: 5px;
    text-align: center;
    min-height: 22px;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 4px;
}}
QPlainTextEdit {{
    background-color: #1e1e1e;
    color: #d4d4d4;
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 6px;
    selection-background-color: {ACCENT};
}}
QTableWidget {{
    border: 1px solid palette(mid);
    border-radius: 6px;
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
    border-radius: 8px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
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
    """CapCut-style dark palette, applied regardless of the OS theme setting."""
    window = QColor("#1b1d23")
    base = QColor("#15161b")
    alt_base = QColor("#20222a")
    button = QColor("#252831")
    text = QColor("#e6e6e6")
    disabled_text = QColor("#6b6f7a")

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
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff5c5c"))
    palette.setColor(QPalette.ColorRole.Link, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, disabled_text)
    palette.setColor(QPalette.ColorRole.Mid, QColor("#33363f"))
    palette.setColor(QPalette.ColorRole.Light, QColor("#2c2f38"))
    palette.setColor(QPalette.ColorRole.Dark, QColor("#0f1014"))
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
