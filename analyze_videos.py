#!/usr/bin/env python3
"""
Video quality analyzer/comparator.

Scans video_from_download/ and video_from_iphone/, probes each file with
ffprobe, and prints a side-by-side technical comparison (resolution, codec,
bitrate, bits-per-pixel quality density, color depth, etc).

Usage:
    python analyze_videos.py
    python analyze_videos.py --json report.json   # also dump raw metrics
"""
import argparse
import json
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypedDict

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001, S110 - stdout/stderr may not support reconfigure at all
    pass

BASE_DIR = Path(__file__).resolve().parent
FFPROBE = BASE_DIR / "ffprobe.exe"
FOLDERS = {
    "iPhone (recorded)": BASE_DIR / "video_from_iphone",
    "Downloaded": BASE_DIR / "video_from_download",
}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


class VideoInfo(TypedDict, total=False):
    """Shape returned by analyze_file(): either a full metrics record, or
    just file/path/error when ffprobe/parsing failed on that file."""
    file: str
    path: str
    error: str
    size_mb: float
    duration_s: float
    resolution: str
    megapixels: float
    fps: float
    video_codec: str | None
    profile: str | None
    bit_depth: str
    pix_fmt: str | None
    color_space: str | None
    video_bitrate_mbps: float
    overall_bitrate_mbps: float
    bits_per_pixel: float
    quality_density: str
    audio_codec: str | None
    audio_bitrate_kbps: float


def probe(path: Path) -> dict[str, Any]:
    cmd = [str(FFPROBE), "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", check=False)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"ffprobe failed on {path.name}: {result.stderr[:300]}")
    return json.loads(result.stdout)


def parse_fps(rate_str: str) -> float:
    try:
        num, den = rate_str.split("/")
        den_val = float(den)
        return float(num) / den_val if den_val else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def bpp_label(bpp: float) -> str:
    if bpp >= 0.15:
        return "Excellent"
    if bpp >= 0.08:
        return "Good"
    if bpp >= 0.04:
        return "Fair"
    if bpp > 0:
        return "Heavily compressed"
    return "n/a"


def analyze_file(path: Path) -> VideoInfo:
    data = probe(path)
    fmt: dict[str, Any] = data.get("format", {})
    streams: list[dict[str, Any]] = data.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
    astreams = [s for s in streams if s.get("codec_type") == "audio"]

    size_bytes = int(fmt.get("size", 0) or 0)
    duration = float(fmt.get("duration", 0) or 0)
    overall_bitrate = int(fmt.get("bit_rate", 0) or 0)

    width = height = 0
    fps = 0.0
    vcodec = pix_fmt = color_space = profile = None
    vbitrate = 0
    rotated = False

    if vstream:
        width = int(vstream.get("width", 0) or 0)
        height = int(vstream.get("height", 0) or 0)
        vcodec = vstream.get("codec_name")
        profile = vstream.get("profile")
        pix_fmt = vstream.get("pix_fmt")
        color_space = vstream.get("color_space")
        vbitrate = int(vstream.get("bit_rate", 0) or 0)
        fps = parse_fps(vstream.get("avg_frame_rate", "0/0")) or parse_fps(vstream.get("r_frame_rate", "0/0"))
        side_data: list[dict[str, Any]] = vstream.get("side_data_list", []) or []
        for sd in side_data:
            if "rotation" in sd and abs(sd["rotation"]) in (90, 270):
                rotated = True

    audio_bitrate_total = sum(int(a.get("bit_rate", 0) or 0) for a in astreams)
    if vbitrate == 0 and overall_bitrate:
        vbitrate = max(overall_bitrate - audio_bitrate_total, 0)

    eff_w, eff_h = (height, width) if rotated else (width, height)
    pixels = eff_w * eff_h
    bpp = (vbitrate / (pixels * fps)) if pixels and fps else 0.0
    bit_depth = "10-bit" if pix_fmt and ("p10" in pix_fmt) else ("8-bit" if pix_fmt else "?")

    return {
        "file": path.name,
        "size_mb": round(size_bytes / 1_000_000, 2),
        "duration_s": round(duration, 2),
        "resolution": f"{eff_w}x{eff_h}" if pixels else "unknown",
        "megapixels": round(pixels / 1_000_000, 2),
        "fps": round(fps, 2),
        "video_codec": vcodec,
        "profile": profile,
        "bit_depth": bit_depth,
        "pix_fmt": pix_fmt,
        "color_space": color_space,
        "video_bitrate_mbps": round(vbitrate / 1_000_000, 3),
        "overall_bitrate_mbps": round(overall_bitrate / 1_000_000, 3),
        "bits_per_pixel": round(bpp, 4),
        "quality_density": bpp_label(bpp),
        "audio_codec": astreams[0].get("codec_name") if astreams else None,
        "audio_bitrate_kbps": round(int(astreams[0].get("bit_rate", 0) or 0) / 1000, 1) if astreams else 0,
    }


def scan_folder(folder: Path) -> list[VideoInfo]:
    if not folder.exists():
        return []
    files = [p for p in sorted(folder.iterdir())
             if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
    rows: list[VideoInfo] = []
    for p in files:
        try:
            rows.append(analyze_file(p))
        except Exception as e:  # noqa: BLE001 - one bad file must not abort the whole scan
            print(f"  [skip] {p.name}: {e}", file=sys.stderr)
    return rows


def print_table(label: str, rows: list[VideoInfo]):
    print(f"\n=== {label} - {len(rows)} file(s) ===")
    if not rows:
        print("  (no video files found)")
        return
    for r in rows:
        print(f"\n  {r.get('file', '')}")
        print(f"    Resolution : {r.get('resolution')}  @ {r.get('fps')} fps")
        print(f"    Codec      : {r.get('video_codec')} ({r.get('profile')}), "
              f"{r.get('bit_depth')}, {r.get('pix_fmt')}, {r.get('color_space')}")
        print(f"    Bitrate    : video {r.get('video_bitrate_mbps')} Mbps | overall {r.get('overall_bitrate_mbps')} Mbps")
        print(f"    Bits/pixel : {r.get('bits_per_pixel')}  -> {r.get('quality_density')}")
        print(f"    Audio      : {r.get('audio_codec')} @ {r.get('audio_bitrate_kbps')} kbps")
        print(f"    Size       : {r.get('size_mb')} MB, {r.get('duration_s')}s")


def avg(vals: Iterable[float]) -> float:
    kept = [v for v in vals if v]
    return round(sum(kept) / len(kept), 3) if kept else 0.0


def print_summary(results: dict[str, list[VideoInfo]]):
    print("\n" + "=" * 60)
    print("SUMMARY COMPARISON")
    print("=" * 60)
    header = f"{'Metric':<24}"
    labels = list(results.keys())
    for lbl in labels:
        header += f"{lbl:>18}"
    print(header)

    metrics: list[tuple[str, str]] = [
        ("Avg video bitrate (Mbps)", "video_bitrate_mbps"),
        ("Avg bits/pixel", "bits_per_pixel"),
        ("Avg resolution (MP)", "megapixels"),
        ("Avg fps", "fps"),
    ]
    for name, key in metrics:
        line = f"{name:<24}"
        for lbl in labels:
            val = avg(float(r.get(key, 0.0) or 0.0) for r in results[lbl])
            line += f"{val:>18}"
        print(line)

    print()
    dl = results.get("Downloaded", [])
    ip = results.get("iPhone (recorded)", [])
    if dl and ip:
        dl_bpp = avg(r.get("bits_per_pixel", 0.0) for r in dl)
        ip_bpp = avg(r.get("bits_per_pixel", 0.0) for r in ip)
        dl_br = avg(r.get("video_bitrate_mbps", 0.0) for r in dl)
        ip_br = avg(r.get("video_bitrate_mbps", 0.0) for r in ip)
        if dl_bpp > 0:
            print(f"Verdict: iPhone recordings carry ~{round(ip_bpp / dl_bpp, 1)}x more data per pixel")
            print(f"         ({round(ip_br,2)} Mbps vs {round(dl_br,2)} Mbps video bitrate) than the downloaded copies.")
            print("         Downloaded files were almost certainly re-encoded/compressed by the")
            print("         platform (and possibly again by the download tool), which is the direct")
            print("         cause of the visible quality gap.")

    # Same-resolution apples-to-apples comparison (removes resolution as a variable)
    print("\n" + "-" * 60)
    print("SAME-RESOLUTION COMPARISON (fairest test)")
    print("-" * 60)
    by_res: dict[str, dict[str, list[VideoInfo]]] = {}
    for lbl, rows in results.items():
        for r in rows:
            by_res.setdefault(r.get("resolution", "unknown"), {}).setdefault(lbl, []).append(r)

    matched_any = False
    for res, by_label in by_res.items():
        if len(by_label) < 2:
            continue
        matched_any = True
        print(f"\n  Resolution {res}:")
        for lbl, rows in by_label.items():
            for r in rows:
                print(f"    [{lbl}] {r.get('file', '')}")
                print(f"        codec={r.get('video_codec')} ({r.get('bit_depth')}) fps={r.get('fps')} "
                      f"bitrate={r.get('video_bitrate_mbps')}Mbps bpp={r.get('bits_per_pixel')} "
                      f"({r.get('quality_density')})")
    if not matched_any:
        print("  No two folders share an identical resolution to compare directly.")
        print("  (Bits-per-pixel above already normalizes for resolution differences.)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", metavar="FILE", help="write full per-file metrics to this JSON file")
    args = parser.parse_args()

    if not FFPROBE.exists():
        print(f"ERROR: ffprobe.exe not found at {FFPROBE}", file=sys.stderr)
        sys.exit(1)

    results: dict[str, list[VideoInfo]] = {}
    for label, folder in FOLDERS.items():
        print(f"Scanning {folder} ...")
        results[label] = scan_folder(folder)

    for label, rows in results.items():
        print_table(label, rows)

    print_summary(results)

    if args.json:
        out_path = Path(args.json)
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nFull metrics written to {out_path}")


if __name__ == "__main__":
    main()
