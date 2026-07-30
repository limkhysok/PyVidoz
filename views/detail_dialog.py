"""Modal dialog showing the full technical profile of a probed video."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from models.video_analyzer import VideoInfo
from views.theme import DETAIL_SECTIONS


class DetailDialog(QDialog):
    def __init__(self, info: VideoInfo, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"Video Details - {info.get('file', '')}")
        self.resize(460, 560)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        if "error" in info:
            layout.addWidget(QLabel(f"Could not read this file:\n{info['error']}"))
        else:
            for section_title, fields in DETAIL_SECTIONS:
                box = QGroupBox(section_title)
                form = QFormLayout(box)
                form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
                for label, key in fields:
                    value = info.get(key, "n/a")
                    value_label = QLabel(str(value))
                    value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                    form.addRow(QLabel(f"{label}:"), value_label)
                layout.addWidget(box)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
