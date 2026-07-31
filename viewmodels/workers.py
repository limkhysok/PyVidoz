"""Background QThread workers. Each one wraps a single Model-layer call and
reports back via Qt signals; MainViewModel owns and re-emits these."""
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from models.config import VIDEO_EXTS
from models.video_analyzer import VideoInfo, analyze_file
from models.video_formatter import detect_gpu_encoders, run_batch


class FormatWorker(QThread):
    logMessage = Signal(str)
    progressChanged = Signal(int, int)
    finishedBatch = Signal(int, int, int)
    pauseStateChanged = Signal(bool)

    def __init__(self, in_folder: Path, out_folder: Path, bpp: float,
                 interpolate: bool, skip_existing: bool, encoder: str, cpu_limit_pct: int):
        super().__init__()
        self.in_folder = in_folder
        self.out_folder = out_folder
        self.bpp = bpp
        self.interpolate = interpolate
        self.skip_existing = skip_existing
        self.encoder = encoder
        self.cpu_limit_pct = cpu_limit_pct
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()

    def run(self):
        ok, fail, skipped = run_batch(
            self.in_folder, self.out_folder, self.bpp, self.interpolate,
            dry_run=False, skip_existing=self.skip_existing,
            log=lambda msg: self.logMessage.emit(msg),
            stop_event=self.stop_event,
            pause_event=self.pause_event,
            on_pause_state=lambda active: self.pauseStateChanged.emit(active),
            progress=lambda done, total: self.progressChanged.emit(done, total),
            encoder=self.encoder, cpu_limit_pct=self.cpu_limit_pct,
        )
        self.finishedBatch.emit(ok, fail, skipped)

    def request_stop(self):
        self.stop_event.set()
        # Cancelling must also break out of a paused wait.
        self.pause_event.clear()

    def request_pause(self):
        self.pause_event.set()

    def request_resume(self):
        self.pause_event.clear()


class EncoderDetectWorker(QThread):
    detected = Signal(dict)

    def run(self) -> None:
        self.detected.emit(detect_gpu_encoders())


class ProbeWorker(QThread):
    rowReady = Signal(dict)
    finishedProbing = Signal()

    def __init__(self, folder: Path):
        super().__init__()
        self.folder = folder

    def run(self) -> None:
        if self.folder.exists():
            files = [p for p in sorted(self.folder.iterdir())
                     if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
            for p in files:
                info: VideoInfo
                try:
                    info = analyze_file(p)
                    info["path"] = str(p)
                except Exception as e:  # noqa: BLE001 - probing must never crash the batch
                    info = {"file": p.name, "path": str(p), "error": str(e)}
                self.rowReady.emit(info)
        self.finishedProbing.emit()
