#!/usr/bin/env python3
"""
Batch video formatter/upscaler.

Re-encodes downloaded (typically low-bitrate, 8-bit, 30fps, sub-1080p) videos
toward a high-quality delivery profile closer to native phone recordings:
  - HEVC (H.265), 10-bit (Main10 profile)
  - Denoised to reduce visible compression blockiness
  - Resolution normalized to Full HD vertical (1080x1920, see TARGET_WIDTH/
    TARGET_HEIGHT): lanczos-scaled to cover the target box, then center-
    cropped to trim any aspect-ratio overhang. A no-op for clips already at
    1080x1920. This is a standard upscale (sharper resampling), not AI
    super-resolution -- see the note below.
  - Frame rate raised to 60fps via a cheap duplication-based conversion
    (fps filter) -- NOT motion-compensated interpolation. True
    motion-compensated interpolation (minterpolate mi_mode=mci) was measured
    at ~260s for a 20s clip vs ~6s for plain fps conversion on the same
    hardware -- a ~40x cost for smoother in-between frames that most users
    don't need just to hit a 60fps target. It does not add new motion
    detail; frames are duplicated to fill the 60fps timing, matching what a
    "quality_density"/fps readout from analyze_videos.py checks for.
  - Bitrate raised to a target bits-per-pixel density, computed against the
    OUTPUT resolution (always 1080x1920) rather than the source's, since
    every clip is upscaled/cropped to that size regardless of input size.
    Default 0.19 (see TARGET_BPP) lands actual measured density around
    ~0.17, in the "Excellent" bucket used by analyze_videos.py -- set above
    the nominal "Excellent" cutoff of 0.15 because NVENC's VBR rate control
    undershoots the requested average.

This CANNOT recover detail that prior lossy compression already discarded --
it reduces further degradation and smooths out artifacts, it does not
perform true super-resolution. Color space is kept as the correct SDR
bt709 (not relabeled as HDR bt2020), since the source has no real HDR data
-- relabeling SDR pixel data as BT.2020 without genuine HDR mastering info
would make colors look washed out/wrong on playback, not better.

Encoder backend: the actual HEVC encode can run on CPU (libx265, software)
or GPU (NVENC/QSV/AMF hardware encoders), see ENCODERS/detect_gpu_encoders().
The fps-conversion and denoise filters always run on CPU regardless of
encoder choice (ffmpeg has no GPU path for them in this build), but they are
cheap relative to the encode step now that fps conversion is duplication-based
rather than motion-compensated. Use --cpu-limit / cpu_limit_pct to cap how
many threads the CPU-side work is allowed to use, and the ffmpeg process
always runs at BELOW_NORMAL priority so it yields to your foreground apps.

Usage:
    python format_videos.py                        # video_from_download -> video_formatted
    python format_videos.py --in FOLDER --out FOLDER
    python format_videos.py --bpp 0.18              # target quality density
    python format_videos.py --no-interpolate        # keep source fps instead of converting to 60
    python format_videos.py --encoder nvenc         # force an encoder (auto|cpu|nvenc|qsv|amf)
    python format_videos.py --cpu-limit 50          # cap CPU-side threads to ~50% of cores
    python format_videos.py --dry-run               # print ffmpeg commands only

This module is also imported by gui_app.py (PySide6 GUI front-end).
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int], None]

# sys.stdout/stderr are typed as TextIO, which has no .reconfigure() -- it's
# only present on the concrete io.TextIOWrapper CPython actually hands back.
# Look it up dynamically so static type checkers don't flag a bogus missing
# attribute, and simply no-op if it's genuinely unavailable (e.g. redirected
# to something that isn't a TextIOWrapper).
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
FFPROBE = BASE_DIR / "ffprobe.exe"
FFMPEG = BASE_DIR / "ffmpeg.exe"
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}

DEFAULT_IN = BASE_DIR / "video_from_download"
DEFAULT_OUT = BASE_DIR / "video_formatted"

TARGET_BPP = 0.19       # bits-per-pixel target quality density -- set above the 0.15
                        # "Excellent" threshold because NVENC VBR undershoots the nominal
                        # target (measured ~0.16 requested -> ~0.148 actual on a test clip)
TARGET_FPS = 60
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
MIN_VIDEO_BITRATE_KBPS = 4000
DEFAULT_CPU_LIMIT_PCT = 50   # safety-first default: never silently pin all cores

ENCODERS = {
    "cpu":   {"codec": "libx265",    "label": "CPU (libx265, software)"},
    "nvenc": {"codec": "hevc_nvenc", "label": "NVIDIA GPU (NVENC)"},
    "qsv":   {"codec": "hevc_qsv",   "label": "Intel GPU (Quick Sync)"},
    "amf":   {"codec": "hevc_amf",   "label": "AMD GPU (AMF)"},
}
GPU_PRIORITY = ("nvenc", "qsv", "amf")  # preference order for --encoder auto


def detect_gpu_encoders(timeout: float = 15) -> dict[str, bool]:
    """Actually test-initialize each hardware encoder (not just check it's compiled in)."""
    available: dict[str, bool] = {"cpu": True}
    for key, spec in ENCODERS.items():
        if key == "cpu":
            continue
        cmd = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-f", "lavfi",
               "-i", "color=c=black:s=256x256:d=0.1", "-frames:v", "1",
               "-c:v", spec["codec"], "-f", "null", "-"]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
            available[key] = result.returncode == 0
        except (subprocess.SubprocessError, OSError):
            available[key] = False
    return available


def resolve_encoder(choice: str, available: dict[str, bool] | None = None) -> str:
    if choice != "auto":
        return choice
    available = available if available is not None else detect_gpu_encoders()
    for key in GPU_PRIORITY:
        if available.get(key):
            return key
    return "cpu"


def threads_for_cpu_limit(cpu_limit_pct: int | None) -> int:
    """0 means 'unlimited / let ffmpeg decide'."""
    if not cpu_limit_pct or cpu_limit_pct >= 100:
        return 0
    total = os.cpu_count() or 4
    return max(1, int(total * cpu_limit_pct / 100))


def parse_fps(rate_str: str) -> float:
    try:
        num, den = rate_str.split("/")
        den_f = float(den)
        return float(num) / den_f if den_f else 0.0
    except (ValueError, IndexError):
        return 0.0


def probe(path: Path) -> dict[str, Any]:
    cmd = [str(FFPROBE), "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", check=False)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"ffprobe failed: {result.stderr[:300]}")
    data: dict[str, Any] = json.loads(result.stdout)
    return data


def get_video_info(path: Path) -> dict[str, Any]:
    data = probe(path)
    fmt: dict[str, Any] = data.get("format", {})
    streams: list[dict[str, Any]] = data.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not vstream:
        raise RuntimeError("no video stream found")
    width = int(vstream.get("width", 0) or 0)
    height = int(vstream.get("height", 0) or 0)
    fps = parse_fps(vstream.get("avg_frame_rate", "0/0")) or parse_fps(vstream.get("r_frame_rate", "0/0"))
    side_data: list[dict[str, Any]] = vstream.get("side_data_list", []) or []
    rotated = any(abs(sd.get("rotation", 0)) in (90, 270) for sd in side_data)
    eff_w, eff_h = (height, width) if rotated else (width, height)
    return {
        "width": eff_w,
        "height": eff_h,
        "fps": fps,
        "duration": float(fmt.get("duration", 0) or 0),
    }


def target_bitrate_kbps(width: int, height: int, fps: float, bpp: float) -> int:
    fps = fps or 30
    kbps = (bpp * width * height * fps) / 1000
    return max(int(kbps), MIN_VIDEO_BITRATE_KBPS)


def build_filters(interpolate: bool) -> str:
    # Plain fps conversion (duplication-based), not motion-compensated
    # minterpolate -- ~40x cheaper (measured: ~6s vs ~260s on a 20s 1080x1920
    # clip) since it does no per-frame motion search. It hits the 60fps
    # target property without adding real in-between motion detail.
    filters: list[str] = []
    if interpolate:
        filters.append(f"fps={TARGET_FPS}")
    # Denoise before upscaling: fewer pixels to process, and it avoids
    # sharpening/amplifying noise that a later upscale would enlarge.
    filters.append("hqdn3d=2:2:4:4")
    # Normalize every clip to Full HD vertical (1080x1920): lanczos-scale to
    # cover the target box, then center-crop any aspect-ratio overhang. This
    # is a no-op (scale factor 1, zero crop) for clips already at 1080x1920.
    filters.append(f"scale=w={TARGET_WIDTH}:h={TARGET_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos")
    filters.append(f"crop={TARGET_WIDTH}:{TARGET_HEIGHT}")
    filters.append("format=yuv420p10le")
    return ",".join(filters)


def build_cmd(src: Path, dst: Path, br_kbps: int, filters: str,
              encoder: str = "cpu", threads: int = 0) -> list[str]:
    codec = ENCODERS.get(encoder, ENCODERS["cpu"])["codec"]
    cmd = [str(FFMPEG), "-y", "-i", str(src), "-vf", filters]
    if threads:
        cmd += ["-filter_threads", str(threads)]
    cmd += ["-c:v", codec, "-profile:v", "main10", "-pix_fmt", "yuv420p10le"]
    if encoder == "cpu":
        if threads:
            cmd += ["-x265-params", f"pools={threads}:frame-threads={min(threads, 8)}"]
    elif encoder == "nvenc":
        cmd += ["-preset", "p5", "-rc", "vbr"]
    elif encoder == "qsv":
        cmd += ["-preset", "medium"]
    elif encoder == "amf":
        cmd += ["-quality", "balanced"]
    cmd += [
        "-b:v", f"{br_kbps}k", "-maxrate", f"{int(br_kbps * 1.5)}k", "-bufsize", f"{int(br_kbps * 2)}k",
        "-tag:v", "hvc1",
        "-c:a", "aac", "-b:a", "192k",
        str(dst),
    ]
    return cmd


def _run_ffmpeg(cmd: list[str], dst: Path, log: LogFn, stop_event: threading.Event | None) -> str:
    """Returns 'ok', 'failed', or 'cancelled'."""
    log_path = dst.with_suffix(".log.txt")
    t0 = time.time()
    with open(log_path, "w", encoding="utf-8", errors="replace") as lf:
        if sys.platform == "win32":
            # Never let the encode fight the user's foreground apps for CPU scheduling.
            proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT,
                                     creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT)
        while proc.poll() is None:
            if stop_event is not None and stop_event.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                log(f"   cancelled after {time.time() - t0:.1f}s")
                return "cancelled"
            time.sleep(0.3)
    elapsed = time.time() - t0
    if proc.returncode != 0:
        log(f"   FAILED ({elapsed:.1f}s) - see {log_path.name}")
        return "failed"
    try:
        log_path.unlink(missing_ok=True)
    except OSError:
        log(f"   (could not remove {log_path.name}, harmless)")
    log(f"   done in {elapsed:.1f}s -> {dst.name}")
    return "ok"


def format_video(src: Path, dst: Path, bpp: float, interpolate: bool, dry_run: bool = False,
                  log: LogFn = print, stop_event: threading.Event | None = None,
                  encoder: str = "cpu", cpu_limit_pct: int | None = DEFAULT_CPU_LIMIT_PCT,
                  fallback_to_cpu: bool = True) -> bool:
    info = get_video_info(src)
    out_fps = TARGET_FPS if interpolate else (info["fps"] or 30)
    # Bitrate must target the OUTPUT pixel count, not the source's -- every
    # clip is normalized to TARGET_WIDTH x TARGET_HEIGHT by build_filters(),
    # regardless of source resolution.
    br_kbps = target_bitrate_kbps(TARGET_WIDTH, TARGET_HEIGHT, out_fps, bpp)
    filters = build_filters(interpolate)
    threads = threads_for_cpu_limit(cpu_limit_pct)

    def attempt(enc: str) -> str:
        cmd = build_cmd(src, dst, br_kbps, filters, encoder=enc, threads=threads)
        log(f"-> {src.name}")
        log(f"   source : {info['width']}x{info['height']} @ {round(info['fps'], 2)}fps")
        cpu_note = f", CPU threads capped ~{threads}" if threads else ""
        log(f"   target : {TARGET_WIDTH}x{TARGET_HEIGHT}, ~{br_kbps}kbps, "
            f"{'60fps (fps-converted)' if interpolate else 'source fps kept'}, "
            f"10-bit HEVC via {ENCODERS[enc]['label']}{cpu_note}")
        if dry_run:
            log("   [dry-run] " + " ".join(cmd))
            return "ok"
        return _run_ffmpeg(cmd, dst, log, stop_event)

    result = attempt(encoder)
    if result == "failed" and encoder != "cpu" and fallback_to_cpu:
        log(f"   {ENCODERS[encoder]['label']} failed on this file, retrying with CPU encoder...")
        result = attempt("cpu")

    return result == "ok"


def run_batch(in_folder: Path, out_folder: Path, bpp: float = TARGET_BPP,
              interpolate: bool = True, dry_run: bool = False, skip_existing: bool = True,
              log: LogFn = print, stop_event: threading.Event | None = None,
              progress: ProgressFn | None = None,
              encoder: str = "cpu",
              cpu_limit_pct: int | None = DEFAULT_CPU_LIMIT_PCT) -> tuple[int, int, int]:
    """Format every video in in_folder into out_folder. Returns (ok, fail, skipped)."""
    out_folder.mkdir(parents=True, exist_ok=True)
    files = [p for p in sorted(in_folder.iterdir())
             if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
    total = len(files)
    ok = fail = skipped = 0

    if total == 0:
        log(f"No video files found in {in_folder}")
        return ok, fail, skipped

    for idx, src in enumerate(files, 1):
        if stop_event is not None and stop_event.is_set():
            log("Batch cancelled.")
            break
        dst = out_folder / (src.stem + "_formatted.mp4")
        if skip_existing and dst.exists():
            log(f"-> {src.name} [skipped, already exists]")
            skipped += 1
            if progress:
                progress(idx, total)
            continue
        try:
            if format_video(src, dst, bpp, interpolate, dry_run, log=log, stop_event=stop_event,
                             encoder=encoder, cpu_limit_pct=cpu_limit_pct):
                ok += 1
            else:
                fail += 1
        except Exception as e:  # noqa: BLE001 - one bad file must not abort the whole batch
            log(f"   ERROR on {src.name}: {e}")
            fail += 1
        if progress:
            progress(idx, total)

    log(f"\nDone. {ok} succeeded, {fail} failed, {skipped} skipped.")
    return ok, fail, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--in", dest="in_folder", default=str(DEFAULT_IN))
    parser.add_argument("--out", dest="out_folder", default=str(DEFAULT_OUT))
    parser.add_argument("--bpp", type=float, default=TARGET_BPP, help="target bits-per-pixel quality density")
    parser.add_argument("--no-interpolate", action="store_true", help="keep source fps instead of converting to 60fps")
    parser.add_argument("--overwrite", action="store_true", help="re-encode even if output file already exists")
    parser.add_argument("--encoder", choices=["auto", "cpu", "nvenc", "qsv", "amf"], default="auto",
                         help="encoder backend (auto picks best available GPU, falls back to CPU)")
    parser.add_argument("--cpu-limit", type=int, default=DEFAULT_CPU_LIMIT_PCT,
                         help="cap CPU-side (filter/encode) threads to this %% of logical cores, 100=unlimited")
    parser.add_argument("--dry-run", action="store_true", help="print ffmpeg commands without running them")
    args = parser.parse_args()

    if not FFMPEG.exists() or not FFPROBE.exists():
        print("ERROR: ffmpeg.exe/ffprobe.exe not found next to this script.", file=sys.stderr)
        sys.exit(1)

    in_folder = Path(args.in_folder)
    if not in_folder.exists():
        print(f"ERROR: input folder not found: {in_folder}", file=sys.stderr)
        sys.exit(1)
    out_folder = Path(args.out_folder)

    interpolate = not args.no_interpolate
    encoder = resolve_encoder(args.encoder)
    print(f"Input  -> {in_folder}")
    print(f"Output -> {out_folder}")
    print(f"Interpolation to {TARGET_FPS}fps: {'ON' if interpolate else 'OFF'}")
    print(f"Target quality density: {args.bpp} bits/pixel")
    print(f"Encoder: {ENCODERS[encoder]['label']}")
    print(f"CPU limit: {args.cpu_limit}% "
          f"({threads_for_cpu_limit(args.cpu_limit) or 'unlimited'} threads)")

    run_batch(in_folder, out_folder, args.bpp, interpolate, args.dry_run,
              skip_existing=not args.overwrite, log=print,
              encoder=encoder, cpu_limit_pct=args.cpu_limit)


if __name__ == "__main__":
    main()
