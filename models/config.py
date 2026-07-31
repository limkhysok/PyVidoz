"""Shared paths and constants used across the Model layer (and read by the
View for default field values / display labels)."""
from pathlib import Path

# models/ is one level below the project root, where ffmpeg.exe/ffprobe.exe
# and the video_from_*/video_formatted folders actually live.
BASE_DIR = Path(__file__).resolve().parent.parent
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
    "cpu":   {"codec": "libx265",    "label": "CPU (libx265)"},
    "nvenc": {"codec": "hevc_nvenc", "label": "NVIDIA (NVENC)"},
    "qsv":   {"codec": "hevc_qsv",   "label": "Intel (QSV)"},
    "amf":   {"codec": "hevc_amf",   "label": "AMD (AMF)"},
}
GPU_PRIORITY = ("nvenc", "qsv", "amf")  # preference order for --encoder auto
