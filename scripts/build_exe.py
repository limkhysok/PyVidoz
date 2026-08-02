#!/usr/bin/env python3
"""Build the Windows PyVidoz.exe release folder.

Regenerates version_info.txt from models.config.APP_VERSION, runs
PyInstaller against pyvidoz.spec, then copies ffmpeg.exe/ffprobe.exe into
the resulting dist/PyVidoz/ folder (they're not bundled by the spec since
they're large, gitignored, and downloaded separately per the README).

Usage:
    python scripts/build_exe.py
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.config import APP_VERSION  # noqa: E402


def sync_version_info() -> None:
    parts = APP_VERSION.split(".")
    while len(parts) < 3:
        parts.append("0")
    filevers = tuple(int(p) for p in parts[:3]) + (0,)
    filevers_str = ".".join(str(p) for p in filevers)

    path = ROOT / "version_info.txt"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"filevers=\([^)]*\)", f"filevers={filevers!r}", text)
    text = re.sub(r"prodvers=\([^)]*\)", f"prodvers={filevers!r}", text)
    text = re.sub(r"(StringStruct\(u'FileVersion', u')[^']*(')", rf"\g<1>{filevers_str}\g<2>", text)
    text = re.sub(r"(StringStruct\(u'ProductVersion', u')[^']*(')", rf"\g<1>{filevers_str}\g<2>", text)
    path.write_text(text, encoding="utf-8")
    print(f"version_info.txt synced to {filevers_str}")


def main() -> None:
    ffmpeg = ROOT / "ffmpeg.exe"
    ffprobe = ROOT / "ffprobe.exe"
    missing = [p.name for p in (ffmpeg, ffprobe) if not p.exists()]
    if missing:
        print(f"ERROR: missing {', '.join(missing)} in {ROOT} -- download them first (see README).",
              file=sys.stderr)
        sys.exit(1)

    sync_version_info()

    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "pyvidoz.spec", "--noconfirm"],
        cwd=ROOT, check=True,
    )

    dist_dir = ROOT / "dist" / "PyVidoz"
    shutil.copy2(ffmpeg, dist_dir / "ffmpeg.exe")
    shutil.copy2(ffprobe, dist_dir / "ffprobe.exe")
    print(f"\nBuild complete: {dist_dir}")
    print("Zip that folder for a GitHub Release asset.")


if __name__ == "__main__":
    main()
