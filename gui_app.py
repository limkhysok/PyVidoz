#!/usr/bin/env python3
"""
PySide6 GUI for the video formatter/upscaler.

Pick an input folder of downloaded videos, pick an output folder, hit Start.
Re-encoding runs in a background thread so the UI stays responsive. Once
files land in the output folder, select one in the table and press "Detail"
to see its full technical profile (resolution, codec, bitrate, bits/pixel
quality density, etc) via ffprobe -- the same metrics analyze_videos.py
reports.

Usage:
    python gui_app.py
"""
import os
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QCloseEvent,
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPalette,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from analyze_videos import VideoInfo, analyze_file
from format_videos import (
    DEFAULT_CPU_LIMIT_PCT,
    DEFAULT_IN,
    DEFAULT_OUT,
    ENCODERS,
    FFMPEG,
    FFPROBE,
    GPU_PRIORITY,
    TARGET_BPP,
    VIDEO_EXTS,
    detect_gpu_encoders,
    resolve_encoder,
    run_batch,
)

CPU_LIMIT_OPTIONS = [
    ("Low (~20% of cores)", 20),
    ("Medium (~50% of cores) - recommended", 50),
    ("High (~70% of cores)", 70),
    ("Unlimited (100%)", 100),
]

DETAIL_SECTIONS = [
    ("Video", [
        ("Resolution", "resolution"),
        ("Megapixels", "megapixels"),
        ("FPS", "fps"),
        ("Video Codec", "video_codec"),
        ("Profile", "profile"),
        ("Bit Depth", "bit_depth"),
        ("Pixel Format", "pix_fmt"),
        ("Color Space", "color_space"),
        ("Video Bitrate (Mbps)", "video_bitrate_mbps"),
        ("Bits / Pixel", "bits_per_pixel"),
        ("Quality Density", "quality_density"),
    ]),
    ("Audio", [
        ("Audio Codec", "audio_codec"),
        ("Audio Bitrate (kbps)", "audio_bitrate_kbps"),
    ]),
    ("File", [
        ("File", "file"),
        ("Overall Bitrate (Mbps)", "overall_bitrate_mbps"),
        ("Size (MB)", "size_mb"),
        ("Duration (s)", "duration_s"),
    ]),
]

TABLE_COLUMNS = [
    ("File", "file"),
    ("Resolution", "resolution"),
    ("FPS", "fps"),
    ("Codec", "video_codec"),
    ("Bit Depth", "bit_depth"),
    ("Video Bitrate (Mbps)", "video_bitrate_mbps"),
    ("Bits/Pixel", "bits_per_pixel"),
    ("Quality", "quality_density"),
    ("Size (MB)", "size_mb"),
]

STATUS_COLORS = {
    "idle": "#808080",
    "running": "#d68a10",
    "done": "#2e9e44",
    "error": "#d64545",
    "cancelled": "#d68a10",
}

QUALITY_BADGE_COLORS = {
    "Excellent": ("#d7f5df", "#1e7a34"),
    "Good": ("#dbe9fb", "#1a56a8"),
    "Fair": ("#fdf1d0", "#a1750a"),
    "Heavily compressed": ("#fbdada", "#a3242c"),
}

ACCENT = "#2f7dd8"
ACCENT_HOVER = "#3d8ae6"

STYLE_SHEET = f"""
QWidget {{
    font-size: 10.5pt;
}}
QGroupBox {{
    font-weight: 600;
    border: 1px solid palette(mid);
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
}}
QLineEdit, QComboBox, QDoubleSpinBox {{
    padding: 5px 8px;
    border: 1px solid palette(mid);
    border-radius: 4px;
    background-color: palette(base);
    min-height: 20px;
}}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QPushButton {{
    padding: 7px 16px;
    border-radius: 5px;
    border: 1px solid palette(mid);
    background-color: palette(button);
}}
QPushButton:hover {{
    background-color: palette(light);
}}
QPushButton#startButton {{
    background-color: {ACCENT};
    color: white;
    border: none;
    font-weight: 600;
    padding: 8px 22px;
}}
QPushButton#startButton:hover:enabled {{
    background-color: {ACCENT_HOVER};
}}
QPushButton#startButton:disabled {{
    background-color: #9fb8d6;
    color: #f0f0f0;
}}
QPushButton#cancelButton:enabled {{
    border: 1px solid #d64545;
    color: #d64545;
    font-weight: 600;
}}
QPushButton#cancelButton:hover:enabled {{
    background-color: #d64545;
    color: white;
}}
QProgressBar {{
    border: 1px solid palette(mid);
    border-radius: 5px;
    text-align: center;
    min-height: 22px;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 4px;
}}
QPlainTextEdit {{
    background-color: #1e1e1e;
    color: #d4d4d4;
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 6px;
    selection-background-color: {ACCENT};
}}
QTableWidget {{
    border: 1px solid palette(mid);
    border-radius: 6px;
    gridline-color: palette(mid);
}}
QHeaderView::section {{
    padding: 6px;
    border: none;
    border-bottom: 2px solid palette(mid);
    font-weight: 600;
}}
QCheckBox {{
    spacing: 8px;
}}
QTabWidget::pane {{
    border: 1px solid palette(mid);
    border-radius: 8px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{
    background: palette(button);
    border-bottom: 2px solid {ACCENT};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    background: palette(light);
}}
"""


def build_dark_palette() -> QPalette:
    """CapCut-style dark palette, applied regardless of the OS theme setting."""
    window = QColor("#1b1d23")
    base = QColor("#15161b")
    alt_base = QColor("#20222a")
    button = QColor("#252831")
    text = QColor("#e6e6e6")
    disabled_text = QColor("#6b6f7a")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, alt_base)
    palette.setColor(QPalette.ColorRole.ToolTipBase, window)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, button)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff5c5c"))
    palette.setColor(QPalette.ColorRole.Link, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, disabled_text)
    palette.setColor(QPalette.ColorRole.Mid, QColor("#33363f"))
    palette.setColor(QPalette.ColorRole.Light, QColor("#2c2f38"))
    palette.setColor(QPalette.ColorRole.Dark, QColor("#0f1014"))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled_text)
    return palette


def make_app_icon(size: int = 64) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0, QColor(ACCENT))
    gradient.setColorAt(1, QColor("#1a4f8a"))
    painter.setBrush(QBrush(gradient))
    painter.setPen(Qt.PenStyle.NoPen)
    radius = size * 0.22
    painter.drawRoundedRect(0, 0, size, size, radius, radius)
    triangle = QPolygonF([
        QPointF(size * 0.38, size * 0.27),
        QPointF(size * 0.38, size * 0.73),
        QPointF(size * 0.75, size * 0.5),
    ])
    painter.setBrush(QColor("white"))
    painter.drawPolygon(triangle)
    painter.end()
    return QIcon(pixmap)


class FormatWorker(QThread):
    logMessage = Signal(str)
    progressChanged = Signal(int, int)
    finishedBatch = Signal(int, int, int)

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

    def run(self):
        ok, fail, skipped = run_batch(
            self.in_folder, self.out_folder, self.bpp, self.interpolate,
            dry_run=False, skip_existing=self.skip_existing,
            log=lambda msg: self.logMessage.emit(msg),
            stop_event=self.stop_event,
            progress=lambda done, total: self.progressChanged.emit(done, total),
            encoder=self.encoder, cpu_limit_pct=self.cpu_limit_pct,
        )
        self.finishedBatch.emit(ok, fail, skipped)

    def request_stop(self):
        self.stop_event.set()


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


class DetailDialog(QDialog):
    def __init__(self, info: VideoInfo, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"Video Details - {info.get('file', '')}")
        self.resize(460, 560)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        if "error" in info:
            layout.addWidget(QLabel(f"Could not read this file:\n{info['error']}"))
        else:
            for section_title, fields in DETAIL_SECTIONS:
                box = QGroupBox(section_title)
                form = QFormLayout(box)
                form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
                for label, key in fields:
                    value = info.get(key, "n/a")
                    value_label = QLabel(str(value))
                    value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                    form.addRow(QLabel(f"{label}:"), value_label)
                layout.addWidget(box)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyVid")
        self.setWindowIcon(make_app_icon())
        self.resize(1150, 780)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(STYLE_SHEET)

        self.worker: FormatWorker | None = None
        self.probe_worker: ProbeWorker | None = None
        self.encoder_detect_worker: EncoderDetectWorker | None = None
        self._available_encoders: dict[str, bool] = {"cpu": True}
        self.row_info: dict[int, VideoInfo] = {}
        self._cancel_requested = False
        self._start_time: float | None = None

        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.setInterval(1000)
        self.elapsed_timer.timeout.connect(self._update_elapsed)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        root.addWidget(self._build_header())
        root.addWidget(self._build_folder_group())
        root.addWidget(self._build_options_group())
        root.addWidget(self._build_controls_group())

        tabs = QTabWidget()
        tabs.addTab(self._build_output_group(), "Output Videos")
        tabs.addTab(self._build_log_group(), "Logs")
        root.addWidget(tabs, stretch=1)

        if not FFMPEG.exists() or not FFPROBE.exists():
            QMessageBox.critical(self, "Missing ffmpeg",
                                  f"ffmpeg.exe / ffprobe.exe not found next to this script:\n{FFMPEG.parent}")

        self.refresh_table()
        self.start_encoder_detection()

    # ---- UI builders ----------------------------------------------------

    def _build_header(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(12)

        icon_label = QLabel()
        icon_label.setPixmap(make_app_icon(40).pixmap(40, 40))
        layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        title = QLabel("Video Formatter")
        title.setStyleSheet("font-size: 16pt; font-weight: 700;")
        subtitle = QLabel("Re-encode downloaded clips toward native phone-recording quality")
        subtitle.setStyleSheet("color: gray; font-size: 9.5pt;")
        text_layout.addWidget(title)
        text_layout.addWidget(subtitle)
        layout.addLayout(text_layout)
        layout.addStretch(1)

        return widget

    def _build_folder_group(self) -> QGroupBox:
        group = QGroupBox("Folders")
        layout = QFormLayout(group)
        layout.setSpacing(8)

        folder_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)

        self.in_edit = QLineEdit(str(DEFAULT_IN))
        in_browse = QPushButton(folder_icon, "Browse...")
        in_browse.clicked.connect(lambda: self._browse(self.in_edit))
        in_row = QHBoxLayout()
        in_row.addWidget(self.in_edit, stretch=1)
        in_row.addWidget(in_browse)
        layout.addRow("Input folder (downloaded videos):", in_row)

        self.out_edit = QLineEdit(str(DEFAULT_OUT))
        out_browse = QPushButton(folder_icon, "Browse...")
        out_browse.clicked.connect(lambda: self._browse(self.out_edit))
        out_row = QHBoxLayout()
        out_row.addWidget(self.out_edit, stretch=1)
        out_row.addWidget(out_browse)
        layout.addRow("Output folder:", out_row)

        return group

    def _build_options_group(self) -> QGroupBox:
        group = QGroupBox("Options")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        bpp_row = QHBoxLayout()
        bpp_row.addWidget(QLabel("Target quality density (bits/pixel):"))
        self.bpp_spin = QDoubleSpinBox()
        self.bpp_spin.setRange(0.02, 0.40)
        self.bpp_spin.setSingleStep(0.01)
        self.bpp_spin.setValue(TARGET_BPP)
        self.bpp_spin.setToolTip(
            "Higher = larger file, less compression.\n"
            "Default 0.19 lands around ~0.17 actual density (\"Excellent\") after\n"
            "NVENC VBR undershoot -- iPhone reference clips measured ~0.168.")
        bpp_row.addWidget(self.bpp_spin)
        bpp_row.addStretch(1)
        layout.addLayout(bpp_row)

        encoder_row = QHBoxLayout()
        encoder_row.addWidget(QLabel("Encoder:"))
        self.encoder_combo = QComboBox()
        self.encoder_combo.addItem("Detecting hardware...", "auto")
        self.encoder_combo.setEnabled(False)
        self.encoder_combo.setToolTip(
            "Which hardware performs the final HEVC encode.\n"
            "GPU is much faster for this step; the encode is now the dominant cost per clip.")
        encoder_row.addWidget(self.encoder_combo, stretch=1)
        layout.addLayout(encoder_row)

        cpu_row = QHBoxLayout()
        cpu_row.addWidget(QLabel("Performance:"))
        self.cpu_limit_combo = QComboBox()
        for label, pct in CPU_LIMIT_OPTIONS:
            self.cpu_limit_combo.addItem(label, pct)
        self.cpu_limit_combo.setCurrentIndex(
            next(i for i, (_, pct) in enumerate(CPU_LIMIT_OPTIONS) if pct == DEFAULT_CPU_LIMIT_PCT)
        )
        self.cpu_limit_combo.setToolTip(
            "Caps how many CPU cores/threads are used.\n"
            "Applies to the (cheap) fps-conversion/denoise filters always,\n"
            "and to the encode step too when Encoder is set to CPU.\n"
            "Note: ffmpeg has no equivalent 'GPU usage %' control, so this limit\n"
            "does not throttle the GPU encode step when Encoder is set to GPU.")
        cpu_row.addWidget(self.cpu_limit_combo, stretch=1)
        layout.addLayout(cpu_row)

        note = QLabel(
            "Note: clips are always converted to 60fps (cheap duplication-based fps filter, not\n"
            "motion-compensated interpolation) and skip re-encoding if already formatted. The\n"
            "HEVC encode is now the dominant cost per clip, so GPU encoding gives the biggest\n"
            "speedup. Performance caps CPU threads for filters (always) and for encoding (only\n"
            "when Encoder = CPU). The ffmpeg process always runs at below-normal priority so it\n"
            "won't starve your other apps."
        )
        note.setStyleSheet("color: gray; font-size: 11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        return group

    def _build_controls_group(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "Start")
        self.start_btn.setObjectName("startButton")
        self.start_btn.clicked.connect(self.start_batch)
        self.cancel_btn = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop), "Cancel")
        self.cancel_btn.setObjectName("cancelButton")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_batch)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch(1)

        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet(f"color: {STATUS_COLORS['idle']}; font-weight: 600;")
        btn_row.addWidget(self.status_label)

        self.elapsed_label = QLabel("")
        self.elapsed_label.setStyleSheet("color: gray;")
        btn_row.addWidget(self.elapsed_label)
        layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%v / %m files (%p%)")
        layout.addWidget(self.progress_bar)

        return widget

    def _build_log_group(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        font = self.log_view.font()
        font.setFamily("Consolas")
        self.log_view.setFont(font)
        layout.addWidget(self.log_view)
        return widget

    def _build_output_group(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload), "Refresh List")
        refresh_btn.clicked.connect(self.refresh_table)
        open_btn = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon), "Open Output Folder")
        open_btn.clicked.connect(self.open_output_folder)
        self.detail_btn = QPushButton(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView), "Detail")
        self.detail_btn.setEnabled(False)
        self.detail_btn.setToolTip("Select a video above, then click here (or double-click the row) for full properties.")
        self.detail_btn.clicked.connect(self.show_detail)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(open_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.detail_btn)
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, len(TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels([label for label, _ in TABLE_COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table)

        return widget

    # ---- actions ----------------------------------------------------

    def _browse(self, line_edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "Select folder", line_edit.text())
        if folder:
            line_edit.setText(folder)

    def _set_status(self, text: str, kind: str):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {STATUS_COLORS[kind]}; font-weight: 600;")

    def start_encoder_detection(self):
        self.encoder_detect_worker = EncoderDetectWorker()
        self.encoder_detect_worker.detected.connect(self._on_encoders_detected)
        self.encoder_detect_worker.start()

    def _on_encoders_detected(self, available: dict[str, bool]):
        self._available_encoders = available
        self.encoder_combo.clear()
        gpu_found = [k for k in GPU_PRIORITY if available.get(k)]
        self.encoder_combo.addItem(ENCODERS["cpu"]["label"], "cpu")
        if gpu_found:
            best = gpu_found[0]
            self.encoder_combo.addItem(f"GPU ({ENCODERS[best]['label']})", "auto")
            self.encoder_combo.setCurrentIndex(1)
            self._on_log(f"Detected GPU encoder(s): {', '.join(ENCODERS[k]['label'] for k in gpu_found)}"
                         f" -- using {ENCODERS[best]['label']} for the GPU option.")
        else:
            self.encoder_combo.addItem("GPU (none detected, will use CPU)", "auto")
            self._on_log("No usable GPU encoder detected; GPU option will fall back to CPU (libx265).")
        self.encoder_combo.setEnabled(True)

    def start_batch(self):
        in_folder = Path(self.in_edit.text())
        out_folder = Path(self.out_edit.text())

        if not in_folder.exists():
            QMessageBox.warning(self, "Input folder not found", f"{in_folder} does not exist.")
            return
        if not FFMPEG.exists() or not FFPROBE.exists():
            QMessageBox.critical(self, "Missing ffmpeg", "ffmpeg.exe / ffprobe.exe not found.")
            return

        self.log_view.clear()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self._cancel_requested = False
        self._set_status("Running...", "running")
        self._start_time = time.time()
        self.elapsed_label.setText("Elapsed: 00:00")
        self.elapsed_timer.start()

        self.worker = FormatWorker(
            in_folder, out_folder,
            bpp=self.bpp_spin.value(),
            interpolate=True,
            skip_existing=True,
            encoder=resolve_encoder(self.encoder_combo.currentData(), self._available_encoders),
            cpu_limit_pct=self.cpu_limit_combo.currentData(),
        )
        self.worker.logMessage.connect(self._on_log)
        self.worker.progressChanged.connect(self._on_progress)
        self.worker.finishedBatch.connect(self._on_batch_finished)
        self.worker.start()

    def cancel_batch(self):
        if self.worker is not None:
            self.worker.request_stop()
            self._cancel_requested = True
            self._on_log("Cancelling... will stop after the current file finishes.")
            self._set_status("Cancelling...", "cancelled")
            self.cancel_btn.setEnabled(False)

    def _update_elapsed(self):
        if self._start_time is None:
            return
        secs = int(time.time() - self._start_time)
        self.elapsed_label.setText(f"Elapsed: {secs // 60:02d}:{secs % 60:02d}")

    def _on_log(self, msg: str):
        self.log_view.appendPlainText(msg)

    def _on_progress(self, done: int, total: int):
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(done)

    def _on_batch_finished(self, ok: int, fail: int, skipped: int):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.elapsed_timer.stop()
        self._update_elapsed()
        if self._cancel_requested:
            self._set_status("Cancelled", "cancelled")
        elif fail:
            self._set_status(f"Done ({fail} failed)", "error")
        else:
            self._set_status("Done", "done")
        QMessageBox.information(self, "Batch finished",
                                 f"Succeeded: {ok}\nFailed: {fail}\nSkipped: {skipped}")
        self.refresh_table()

    def refresh_table(self):
        out_folder = Path(self.out_edit.text())
        self.table.setRowCount(0)
        self.row_info.clear()
        self.detail_btn.setEnabled(False)
        if not out_folder.exists():
            return
        self.probe_worker = ProbeWorker(out_folder)
        self.probe_worker.rowReady.connect(self._add_row)
        self.probe_worker.start()

    def _add_row(self, info: VideoInfo):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.row_info[row] = info
        if "error" in info:
            item = QTableWidgetItem(f"{info.get('file', '')} (unreadable)")
            self.table.setItem(row, 0, item)
            for col in range(1, len(TABLE_COLUMNS)):
                self.table.setItem(row, col, QTableWidgetItem("-"))
            return
        for col, (_, key) in enumerate(TABLE_COLUMNS):
            item = QTableWidgetItem(str(info.get(key, "")))
            if key == "quality_density":
                colors = QUALITY_BADGE_COLORS.get(info.get(key, ""))
                if colors:
                    bg, fg = colors
                    item.setBackground(QColor(bg))
                    item.setForeground(QColor(fg))
                    bold_font = item.font()
                    bold_font.setBold(True)
                    item.setFont(bold_font)
            self.table.setItem(row, col, item)

    def _on_selection_changed(self):
        self.detail_btn.setEnabled(bool(self.table.selectedItems()))

    def _on_row_double_clicked(self, item: QTableWidgetItem) -> None:
        self.show_detail()

    def show_detail(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        info = self.row_info.get(rows[0].row())
        if info is None:
            return
        dlg = DetailDialog(info, self)
        dlg.exec()

    def open_output_folder(self):
        out_folder = Path(self.out_edit.text())
        out_folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(out_folder))

    def closeEvent(self, event: QCloseEvent):
        if self.worker is not None and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "Formatting in progress",
                "A batch is still running. Stop it and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.worker.request_stop()
            self.worker.wait(10000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(build_dark_palette())
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
