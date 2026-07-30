"""Main application window (View layer). Builds widgets, forwards user
actions to MainViewModel, and updates widgets from ViewModel signals. No
business logic or thread management lives here."""
import os
from pathlib import Path

from PySide6.QtGui import QCloseEvent, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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

from models.config import (
    DEFAULT_CPU_LIMIT_PCT,
    DEFAULT_IN,
    DEFAULT_OUT,
    ENCODERS,
    GPU_PRIORITY,
    TARGET_BPP,
)
from models.video_analyzer import VideoInfo
from viewmodels.main_view_model import MainViewModel
from views.detail_dialog import DetailDialog
from views.theme import (
    CPU_LIMIT_OPTIONS,
    QUALITY_BADGE_COLORS,
    STATUS_COLORS,
    STYLE_SHEET,
    TABLE_COLUMNS,
    make_app_icon,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyVid")
        self.setWindowIcon(make_app_icon())
        self.resize(1150, 780)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(STYLE_SHEET)

        self.view_model = MainViewModel()
        self.view_model.logMessage.connect(self._on_log)
        self.view_model.progressChanged.connect(self._on_progress)
        self.view_model.batchFinished.connect(self._on_batch_finished)
        self.view_model.encodersDetected.connect(self._on_encoders_detected)
        self.view_model.rowReady.connect(self._add_row)
        self.view_model.elapsedChanged.connect(self._on_elapsed_changed)

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

        if not self.view_model.ffmpeg_available():
            QMessageBox.critical(self, "Missing ffmpeg",
                                  "ffmpeg.exe / ffprobe.exe not found next to the project root.")

        self.refresh_table()
        self.view_model.start_encoder_detection()

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

    def _on_encoders_detected(self, available: dict[str, bool]):
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
        if not self.view_model.ffmpeg_available():
            QMessageBox.critical(self, "Missing ffmpeg", "ffmpeg.exe / ffprobe.exe not found.")
            return

        self.log_view.clear()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self._set_status("Running...", "running")
        self.elapsed_label.setText("Elapsed: 00:00")

        self.view_model.start_batch(
            in_folder, out_folder,
            bpp=self.bpp_spin.value(),
            encoder_choice=self.encoder_combo.currentData(),
            cpu_limit_pct=self.cpu_limit_combo.currentData(),
        )

    def cancel_batch(self):
        self.view_model.cancel_batch()
        self._set_status("Cancelling...", "cancelled")
        self.cancel_btn.setEnabled(False)

    def _on_elapsed_changed(self, text: str):
        self.elapsed_label.setText(text)

    def _on_log(self, msg: str):
        self.log_view.appendPlainText(msg)

    def _on_progress(self, done: int, total: int):
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(done)

    def _on_batch_finished(self, ok: int, fail: int, skipped: int):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if self.view_model.cancel_requested:
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
        self.detail_btn.setEnabled(False)
        self.view_model.refresh_table(out_folder)

    def _add_row(self, info: VideoInfo):
        row = self.table.rowCount()
        self.table.insertRow(row)
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
        info = self.view_model.get_row_info(rows[0].row())
        if info is None:
            return
        dlg = DetailDialog(info, self)
        dlg.exec()

    def open_output_folder(self):
        out_folder = Path(self.out_edit.text())
        out_folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(out_folder))

    def closeEvent(self, event: QCloseEvent):
        if self.view_model.is_running():
            reply = QMessageBox.question(
                self, "Formatting in progress",
                "A batch is still running. Stop it and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.view_model.request_stop_and_wait(10000)
        event.accept()
