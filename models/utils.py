"""Small helpers shared by video_analyzer.py and video_formatter.py."""
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from models.config import FFPROBE


def ensure_utf8_stdio() -> None:
    """Force UTF-8 stdout/stderr where the runtime supports .reconfigure().

    sys.stdout/stderr are typed as TextIO, which has no .reconfigure() --
    it's only present on the concrete io.TextIOWrapper CPython actually
    hands back. Look it up dynamically so static type checkers don't flag
    a bogus missing attribute, and simply no-op if it's genuinely
    unavailable (e.g. redirected to something that isn't a TextIOWrapper).
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def parse_fps(rate_str: str) -> float:
    try:
        num, den = rate_str.split("/")
        den_f = float(den)
        return float(num) / den_f if den_f else 0.0
    except (ValueError, IndexError, ZeroDivisionError):
        return 0.0


def probe(path: Path) -> dict[str, Any]:
    cmd = [str(FFPROBE), "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", check=False)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"ffprobe failed on {path.name}: {result.stderr[:300]}")
    data: dict[str, Any] = json.loads(result.stdout)
    return data
