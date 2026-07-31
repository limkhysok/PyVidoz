#!/usr/bin/env python3
"""
Entry point for the PyVidoz GUI application.

Pick an input folder of downloaded videos, pick an output folder, hit Start.
Re-encoding runs in a background thread so the UI stays responsive. Once
files land in the output folder, select one in the table and press "Detail"
to see its full technical profile (resolution, codec, bitrate, bits/pixel
quality density, etc) via ffprobe.

Usage:
    python main.py
"""
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from views.main_window import MainWindow
from views.theme import FONT_MONO, build_dark_palette, load_custom_fonts


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    load_custom_fonts()
    app.setPalette(build_dark_palette())
    font = QFont(FONT_MONO)
    font.setPointSize(9)
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
