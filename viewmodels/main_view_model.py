"""ViewModel for the main window: owns application/batch state and the
background QThread workers, and exposes Qt signals/methods for the View to
bind to. No widget code lives here."""
import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from models.config import FFMPEG, FFPROBE
from models.video_analyzer import VideoInfo
from models.video_formatter import resolve_encoder
from viewmodels.workers import EncoderDetectWorker, FormatWorker, ProbeWorker


class MainViewModel(QObject):
    logMessage = Signal(str)
    progressChanged = Signal(int, int)
    batchFinished = Signal(int, int, int)
    encodersDetected = Signal(dict)
    rowReady = Signal(dict)
    probingFinished = Signal()
    elapsedChanged = Signal(str)
    pauseStateChanged = Signal(bool)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.worker: FormatWorker | None = None
        self.probe_worker: ProbeWorker | None = None
        self.encoder_detect_worker: EncoderDetectWorker | None = None
        self.available_encoders: dict[str, bool] = {"cpu": True}
        self.row_info: dict[int, VideoInfo] = {}
        self.cancel_requested = False
        self.is_paused = False
        self._start_time: float | None = None

        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._emit_elapsed)

    # ---- static checks ---------------------------------------------------

    def ffmpeg_available(self) -> bool:
        return FFMPEG.exists() and FFPROBE.exists()

    # ---- encoder detection --------------------------------------------------

    def start_encoder_detection(self) -> None:
        self.encoder_detect_worker = EncoderDetectWorker()
        self.encoder_detect_worker.detected.connect(self._on_encoders_detected)
        self.encoder_detect_worker.start()

    def _on_encoders_detected(self, available: dict[str, bool]) -> None:
        self.available_encoders = available
        self.encodersDetected.emit(available)

    # ---- batch formatting --------------------------------------------------

    def is_running(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def start_batch(self, in_folder: Path, out_folder: Path, bpp: float,
                     encoder_choice: str, cpu_limit_pct: int) -> None:
        encoder = resolve_encoder(encoder_choice, self.available_encoders)
        self.cancel_requested = False
        self.is_paused = False
        self.row_info.clear()
        self._start_time = time.time()
        self._elapsed_timer.start()
        self.elapsedChanged.emit("Elapsed: 00:00")

        self.worker = FormatWorker(
            in_folder, out_folder,
            bpp=bpp,
            interpolate=True,
            skip_existing=True,
            encoder=encoder,
            cpu_limit_pct=cpu_limit_pct,
        )
        self.worker.logMessage.connect(self.logMessage.emit)
        self.worker.progressChanged.connect(self.progressChanged.emit)
        self.worker.fileReady.connect(self._on_row_ready)
        self.worker.finishedBatch.connect(self._on_batch_finished)
        self.worker.pauseStateChanged.connect(self.pauseStateChanged.emit)
        self.worker.start()

    def cancel_batch(self) -> None:
        if self.worker is not None:
            self.worker.request_stop()
            self.cancel_requested = True
            self.is_paused = False
            self.logMessage.emit("Cancelling... will stop after the current file finishes.")

    def pause_batch(self) -> None:
        if self.worker is not None:
            self.worker.request_pause()
            self.is_paused = True

    def resume_batch(self) -> None:
        if self.worker is not None:
            self.worker.request_resume()
            self.is_paused = False

    def request_stop_and_wait(self, timeout_ms: int = 10000) -> None:
        if self.worker is not None:
            self.worker.request_stop()
            self.worker.wait(timeout_ms)

    def _on_batch_finished(self, ok: int, fail: int, skipped: int) -> None:
        self._elapsed_timer.stop()
        self._emit_elapsed()
        self.is_paused = False
        self.batchFinished.emit(ok, fail, skipped)

    def _emit_elapsed(self) -> None:
        if self._start_time is None:
            return
        secs = int(time.time() - self._start_time)
        self.elapsedChanged.emit(f"Elapsed: {secs // 60:02d}:{secs % 60:02d}")

    # ---- output table / probing --------------------------------------------------

    def refresh_table(self, out_folder: Path) -> None:
        self.row_info.clear()
        if not out_folder.exists():
            self.probingFinished.emit()
            return
        self.probe_worker = ProbeWorker(out_folder)
        self.probe_worker.rowReady.connect(self._on_row_ready)
        self.probe_worker.finishedProbing.connect(self.probingFinished.emit)
        self.probe_worker.start()

    def _on_row_ready(self, info: VideoInfo) -> None:
        self.row_info[len(self.row_info)] = info
        self.rowReady.emit(info)

    def get_row_info(self, row: int) -> VideoInfo | None:
        return self.row_info.get(row)
