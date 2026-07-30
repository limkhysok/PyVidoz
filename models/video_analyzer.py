#!/usr/bin/env python3
"""
Video quality analyzer/comparator.

Scans video_from_download/ and video_from_iphone/, probes each file with
ffprobe, and prints a side-by-side technical comparison (resolution, codec,
bitrate, bits-per-pixel quality density, color depth, etc).

Usage:
    python -m models.video_analyzer
    python -m models.video_analyzer --json report.json   # also dump raw metrics
"""
import argparse
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypedDict

from models.config import BASE_DIR, FFPROBE, VIDEO_EXTS
from models.utils import ensure_utf8_stdio, parse_fps, probe

ensure_utf8_stdio()

FOLDERS = {
    "iPhone (recorded)": BASE_DIR / "video_from_iphone",
    "Downloaded": BASE_DIR / "video_from_download",
}


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


def _bit_depth_from_pix_fmt(pix_fmt: str | None) -> str:
    if pix_fmt is None:
        return "?"
    return "10-bit" if "p10" in pix_fmt else "8-bit"


def _is_rotated(side_data: list[dict[str, Any]]) -> bool:
    return any(abs(sd.get("rotation", 0)) in (90, 270) for sd in side_data)


def _parse_video_stream(vstream: dict[str, Any]) -> dict[str, Any]:
    side_data: list[dict[str, Any]] = vstream.get("side_data_list", []) or []
    return {
        "width": int(vstream.get("width", 0) or 0),
        "height": int(vstream.get("height", 0) or 0),
        "codec": vstream.get("codec_name"),
        "profile": vstream.get("profile"),
        "pix_fmt": vstream.get("pix_fmt"),
        "color_space": vstream.get("color_space"),
        "bitrate": int(vstream.get("bit_rate", 0) or 0),
        "fps": parse_fps(vstream.get("avg_frame_rate", "0/0")) or parse_fps(vstream.get("r_frame_rate", "0/0")),
        "rotated": _is_rotated(side_data),
    }


def analyze_file(path: Path) -> VideoInfo:
    data = probe(path)
    fmt: dict[str, Any] = data.get("format", {})
    streams: list[dict[str, Any]] = data.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
    astreams = [s for s in streams if s.get("codec_type") == "audio"]

    size_bytes = int(fmt.get("size", 0) or 0)
    duration = float(fmt.get("duration", 0) or 0)
    overall_bitrate = int(fmt.get("bit_rate", 0) or 0)

    v = _parse_video_stream(vstream) if vstream else {}
    width = v.get("width", 0)
    height = v.get("height", 0)
    vcodec = v.get("codec")
    profile = v.get("profile")
    pix_fmt = v.get("pix_fmt")
    color_space = v.get("color_space")
    vbitrate = v.get("bitrate", 0)
    fps = v.get("fps", 0.0)
    rotated = v.get("rotated", False)

    audio_bitrate_total = sum(int(a.get("bit_rate", 0) or 0) for a in astreams)
    if vbitrate == 0 and overall_bitrate:
        vbitrate = max(overall_bitrate - audio_bitrate_total, 0)

    eff_w, eff_h = (height, width) if rotated else (width, height)
    pixels = eff_w * eff_h
    bpp = (vbitrate / (pixels * fps)) if pixels and fps else 0.0
    bit_depth = _bit_depth_from_pix_fmt(pix_fmt)

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


def _print_metric_averages(results: dict[str, list[VideoInfo]]) -> None:
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


def _print_verdict(results: dict[str, list[VideoInfo]]) -> None:
    dl = results.get("Downloaded", [])
    ip = results.get("iPhone (recorded)", [])
    if not (dl and ip):
        return
    dl_bpp = avg(r.get("bits_per_pixel", 0.0) for r in dl)
    ip_bpp = avg(r.get("bits_per_pixel", 0.0) for r in ip)
    dl_br = avg(r.get("video_bitrate_mbps", 0.0) for r in dl)
    ip_br = avg(r.get("video_bitrate_mbps", 0.0) for r in ip)
    if dl_bpp <= 0:
        return
    print(f"Verdict: iPhone recordings carry ~{round(ip_bpp / dl_bpp, 1)}x more data per pixel")
    print(f"         ({round(ip_br,2)} Mbps vs {round(dl_br,2)} Mbps video bitrate) than the downloaded copies.")
    print("         Downloaded files were almost certainly re-encoded/compressed by the")
    print("         platform (and possibly again by the download tool), which is the direct")
    print("         cause of the visible quality gap.")


def _group_by_resolution(results: dict[str, list[VideoInfo]]) -> dict[str, dict[str, list[VideoInfo]]]:
    by_res: dict[str, dict[str, list[VideoInfo]]] = {}
    for lbl, rows in results.items():
        for r in rows:
            by_res.setdefault(r.get("resolution", "unknown"), {}).setdefault(lbl, []).append(r)
    return by_res


def _print_resolution_group(res: str, by_label: dict[str, list[VideoInfo]]) -> None:
    print(f"\n  Resolution {res}:")
    for lbl, rows in by_label.items():
        for r in rows:
            print(f"    [{lbl}] {r.get('file', '')}")
            print(f"        codec={r.get('video_codec')} ({r.get('bit_depth')}) fps={r.get('fps')} "
                  f"bitrate={r.get('video_bitrate_mbps')}Mbps bpp={r.get('bits_per_pixel')} "
                  f"({r.get('quality_density')})")


def _print_same_resolution_comparison(results: dict[str, list[VideoInfo]]) -> None:
    print("\n" + "-" * 60)
    print("SAME-RESOLUTION COMPARISON (fairest test)")
    print("-" * 60)
    by_res = _group_by_resolution(results)

    matched_any = False
    for res, by_label in by_res.items():
        if len(by_label) < 2:
            continue
        matched_any = True
        _print_resolution_group(res, by_label)
    if not matched_any:
        print("  No two folders share an identical resolution to compare directly.")
        print("  (Bits-per-pixel above already normalizes for resolution differences.)")


def print_summary(results: dict[str, list[VideoInfo]]):
    print("\n" + "=" * 60)
    print("SUMMARY COMPARISON")
    print("=" * 60)
    _print_metric_averages(results)
    print()
    _print_verdict(results)
    # Same-resolution apples-to-apples comparison (removes resolution as a variable)
    _print_same_resolution_comparison(results)


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
        import json
        out_path = Path(args.json)
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nFull metrics written to {out_path}")


if __name__ == "__main__":
    main()
