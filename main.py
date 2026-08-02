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
import datetime
import sys
import traceback
from types import TracebackType

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from models.config import BASE_DIR
from views.main_window import MainWindow
from views.theme import FONT_MONO, build_dark_palette, load_custom_fonts

CRASH_LOG = BASE_DIR / "crash_log.txt"


def _install_exception_hook() -> None:
    """Catch exceptions raised inside Qt slots so a packaged windowed .exe
    (no console to see a traceback in) shows the user something instead of
    just vanishing or hard-aborting."""

    def _hook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType | None,
    ) -> None:
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        timestamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        entry = f"\n[{timestamp}]\n{text}"
        try:
            with CRASH_LOG.open("a", encoding="utf-8") as f:
                f.write(entry)
        except OSError:
            pass
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        QMessageBox.critical(
            None,
            "Unexpected error",
            "PyVidoz hit an unexpected error.\n\n"
            f"Details were written to:\n{CRASH_LOG}\n\n{exc_value}",
        )

    sys.excepthook = _hook


def main():
    app = QApplication(sys.argv)
    _install_exception_hook()
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
