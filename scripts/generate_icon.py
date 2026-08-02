#!/usr/bin/env python3
"""Regenerate assets/icon.ico from the app's programmatic icon design
(views.theme.make_app_icon). Run after changing that drawing code.

Usage:
    python scripts/generate_icon.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
from PySide6.QtWidgets import QApplication

from views.theme import make_app_icon

OUT_PATH = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
RENDER_SIZE = 256
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> None:
    app = QApplication(sys.argv)
    icon = make_app_icon(RENDER_SIZE)
    pixmap = icon.pixmap(RENDER_SIZE, RENDER_SIZE)
    tmp_png = OUT_PATH.with_suffix(".png")
    pixmap.save(str(tmp_png), "PNG")

    image = Image.open(tmp_png).convert("RGBA")
    image.save(OUT_PATH, format="ICO", sizes=ICO_SIZES)
    tmp_png.unlink()
    print(f"Wrote {OUT_PATH}")
    del app


if __name__ == "__main__":
    main()
