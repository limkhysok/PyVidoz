"""Main application window (View layer). Builds widgets, forwards user
actions to MainViewModel, and updates widgets from ViewModel signals. No
business logic or thread management lives here."""
import os
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
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
    ICON_COLOR,
    ICON_COLOR_DANGER,
    ICON_COLOR_DISABLED,
    QUALITY_BADGE_COLORS,
    STATUS_COLORS,
    STYLE_SHEET,
    TABLE_COLUMNS,
    make_app_icon,
)


BOLD_LABEL_STYLE = "font-weight: 600;"


def _icon(name: str, color: str = ICON_COLOR):
    return qta.icon(name, color=color, color_disabled=ICON_COLOR_DISABLED)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._last_log_size = 180

        self.setWindowTitle("PyVidoz")
        self.setWindowIcon(make_app_icon())
        self.resize(1300, 820)
        self.setMinimumSize(1000, 620)
        self.setStyleSheet(STYLE_SHEET)

        self.view_model = MainViewModel()
        self.view_model.logMessage.connect(self._on_log)
        self.view_model.progressChanged.connect(self._on_progress)
        self.view_model.batchFinished.connect(self._on_batch_finished)
        self.view_model.encodersDetected.connect(self._on_encoders_detected)
        self.view_model.rowReady.connect(self._add_row)
        self.view_model.elapsedChanged.connect(self._on_elapsed_changed)
        self.view_model.pauseStateChanged.connect(self._on_pause_state_changed)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        body = QHBoxLayout()
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_main_panel(), stretch=1)
        root.addLayout(body, stretch=1)

        if not self.view_model.ffmpeg_available():
            QMessageBox.critical(self, "Missing ffmpeg",
                                  "ffmpeg.exe / ffprobe.exe not found next to the project root.")

        self.refresh_table()
        self.view_model.start_encoder_detection()

    # ---- UI builders ----------------------------------------------------

    def _build_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("sidebarPanel")
        panel.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(28)
        layout.addWidget(self._build_options_section())
        layout.addWidget(self._build_folder_section())
        layout.addWidget(self._build_controls_group())
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        scroll.setFixedWidth(340)
        return scroll

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(BOLD_LABEL_STYLE)
        return label

    def _build_folder_section(self) -> QWidget:
        section = QFrame()
        section.setObjectName("folderSection")
        section.setFrameShape(QFrame.Shape.NoFrame)
        outer = QVBoxLayout(section)
        outer.setContentsMargins(0, 0, 0, 28)
        outer.setSpacing(10)

        folder_icon = _icon("fa5s.folder-open")

        outer.addWidget(self._field_label("Input Folder"))
        self.in_edit = QLineEdit(str(DEFAULT_IN))
        self.in_edit.setToolTip("Folder containing the downloaded videos to re-encode.")
        in_browse = QPushButton(folder_icon, "")
        in_browse.setToolTip("Browse...")
        in_browse.setFixedWidth(34)
        in_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        in_browse.clicked.connect(lambda: self._browse(self.in_edit))
        in_row = QHBoxLayout()
        in_row.addWidget(self.in_edit, stretch=1)
        in_row.addWidget(in_browse)
        outer.addLayout(in_row)

        outer.addWidget(self._field_label("Output Folder"))
        self.out_edit = QLineEdit(str(DEFAULT_OUT))
        out_browse = QPushButton(folder_icon, "")
        out_browse.setToolTip("Browse...")
        out_browse.setFixedWidth(34)
        out_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        out_browse.clicked.connect(lambda: self._browse(self.out_edit))
        out_row = QHBoxLayout()
        out_row.addWidget(self.out_edit, stretch=1)
        out_row.addWidget(out_browse)
        outer.addLayout(out_row)

        return section

    def _build_options_section(self) -> QWidget:
        section = QFrame()
        section.setObjectName("optionsSection")
        section.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 28)
        layout.setSpacing(8)

        layout.addWidget(self._field_label("Quality"))
        self.bpp_spin = QDoubleSpinBox()
        self.bpp_spin.setRange(0.02, 0.40)
        self.bpp_spin.setSingleStep(0.01)
        self.bpp_spin.setValue(TARGET_BPP)
        self.bpp_spin.setToolTip(
            "Higher = larger file, less compression.\n"
            "Default 0.19 lands around ~0.17 actual density (\"Excellent\") after\n"
            "NVENC VBR undershoot -- iPhone reference clips measured ~0.168.")
        layout.addWidget(self.bpp_spin)

        layout.addWidget(self._field_label("Encoder"))
        self.encoder_combo = QComboBox()
        self.encoder_combo.addItem("Detecting hardware...", "auto")
        self.encoder_combo.setEnabled(False)
        self.encoder_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.encoder_combo.setToolTip(
            "Which hardware performs the final HEVC encode.\n"
            "GPU is much faster for this step; the encode is now the dominant cost per clip.")
        layout.addWidget(self.encoder_combo)

        layout.addWidget(self._field_label("Performance"))
        self.cpu_limit_combo = QComboBox()
        self.cpu_limit_combo.setCursor(Qt.CursorShape.PointingHandCursor)
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
        layout.addWidget(self.cpu_limit_combo)

        return section

    def _build_controls_group(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton(_icon("fa5s.play", color="white"), "Start")
        self.start_btn.setObjectName("startButton")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.clicked.connect(self.start_batch)
        self.pause_btn = QPushButton(_icon("fa5s.pause"), "Pause")
        self.pause_btn.setObjectName("pauseButton")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_btn.setToolTip(
            "Finishes the file currently encoding, then holds before starting the next one.")
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.cancel_btn = QPushButton(_icon("fa5s.stop", color=ICON_COLOR_DANGER), "Cancel")
        self.cancel_btn.setObjectName("cancelButton")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.cancel_batch)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.pause_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet(f"color: {STATUS_COLORS['idle']}; {BOLD_LABEL_STYLE}")
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        self.elapsed_label = QLabel("")
        self.elapsed_label.setStyleSheet("color: gray;")
        status_row.addWidget(self.elapsed_label)
        layout.addLayout(status_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%v / %m files (%p%)")
        layout.addWidget(self.progress_bar)

        return widget

    def _build_main_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton(_icon("fa5s.sync-alt"), "Refresh List")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_table)
        open_btn = QPushButton(_icon("fa5s.folder-open"), "Open Output Folder")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(self.open_output_folder)
        self.detail_btn = QPushButton(_icon("fa5s.list-ul"), "Detail")
        self.detail_btn.setEnabled(False)
        self.detail_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.detail_btn.setToolTip("Select a video above, then click here (or double-click the row) for full properties.")
        self.detail_btn.clicked.connect(self.show_detail)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(open_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.detail_btn)
        layout.addLayout(btn_row)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.addWidget(self._build_table())
        self.splitter.addWidget(self._build_log_panel())
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        layout.addWidget(self.splitter, stretch=1)
        # setSizes() is a no-op until the splitter has real geometry, so
        # apply the initial split after the first layout pass.
        QTimer.singleShot(0, lambda: self.splitter.setSizes([560, self._last_log_size]))

        return widget

    def _build_table(self) -> QTableWidget:
        # Column 0 is a synthetic "#" row index, not part of TABLE_COLUMNS.
        self.table = QTableWidget(0, len(TABLE_COLUMNS) + 1)
        self.table.setHorizontalHeaderLabels(["#"] + [label for label, _ in TABLE_COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)

        header = self.table.horizontalHeader()
        for col in range(2, len(TABLE_COLUMNS) + 1):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 36)
        # File names (esp. downloaded clips) can be very long; cap and elide
        # instead of letting them push Quality/Size off-screen.
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, 260)
        header.setStretchLastSection(True)

        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_row_double_clicked)
        return self.table

    def _build_log_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header_row = QHBoxLayout()
        header_row.addWidget(self._field_label("Logs"))
        header_row.addStretch(1)
        self.logs_toggle_btn = QPushButton("Hide")
        self.logs_toggle_btn.setFlat(True)
        self.logs_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logs_toggle_btn.clicked.connect(self._toggle_logs)
        header_row.addWidget(self.logs_toggle_btn)
        layout.addLayout(header_row)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        layout.addWidget(self.log_view)
        return panel

    def _toggle_logs(self) -> None:
        sizes = self.splitter.sizes()
        if self.log_view.isVisible():
            self._last_log_size = sizes[1]
            self.log_view.setVisible(False)
            self.splitter.setSizes([sum(sizes), 0])
            self.logs_toggle_btn.setText("Show")
        else:
            self.log_view.setVisible(True)
            total = sum(sizes)
            restore = self._last_log_size or 180
            self.splitter.setSizes([max(total - restore, 100), restore])
            self.logs_toggle_btn.setText("Hide")

    # ---- actions ----------------------------------------------------

    def _browse(self, line_edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "Select folder", line_edit.text())
        if folder:
            line_edit.setText(folder)

    def _set_status(self, text: str, kind: str):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {STATUS_COLORS[kind]}; {BOLD_LABEL_STYLE}")

    def _on_encoders_detected(self, available: dict[str, bool]):
        self.encoder_combo.clear()
        gpu_found = [k for k in GPU_PRIORITY if available.get(k)]
        self.encoder_combo.addItem(ENCODERS["cpu"]["label"], "cpu")
        if gpu_found:
            best = gpu_found[0]
            self.encoder_combo.addItem(f"GPU - {ENCODERS[best]['label']}", "auto")
            self.encoder_combo.setCurrentIndex(1)
            self._on_log(f"Detected GPU encoder(s): {', '.join(ENCODERS[k]['label'] for k in gpu_found)}"
                         f" -- using {ENCODERS[best]['label']} for the GPU option.")
        else:
            self.encoder_combo.addItem("GPU (none found)", "auto")
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
        self.pause_btn.setEnabled(True)
        self._reset_pause_button()
        self.cancel_btn.setEnabled(True)
        self._set_status("Running...", "running")
        self.elapsed_label.setText("Elapsed: 00:00")

        self.view_model.start_batch(
            in_folder, out_folder,
            bpp=self.bpp_spin.value(),
            encoder_choice=self.encoder_combo.currentData(),
            cpu_limit_pct=self.cpu_limit_combo.currentData(),
        )

    def toggle_pause(self):
        if self.view_model.is_paused:
            self.view_model.resume_batch()
            self._reset_pause_button()
            self._set_status("Running...", "running")
        else:
            self.view_model.pause_batch()
            self.pause_btn.setText("Resume")
            self.pause_btn.setIcon(_icon("fa5s.play"))
            self._set_status("Pausing...", "cancelled")

    def _on_pause_state_changed(self, active: bool):
        # Fires once the worker actually reaches the wait point between files,
        # which can lag the button click by however long the current file
        # takes to finish encoding.
        if active and self.view_model.is_paused:
            self._set_status("Paused", "cancelled")

    def _reset_pause_button(self):
        self.pause_btn.setText("Pause")
        self.pause_btn.setIcon(_icon("fa5s.pause"))

    def cancel_batch(self):
        self.view_model.cancel_batch()
        self._reset_pause_button()
        self.pause_btn.setEnabled(False)
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
        self.pause_btn.setEnabled(False)
        self._reset_pause_button()
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

        index_item = QTableWidgetItem(str(row + 1))
        index_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 0, index_item)

        if "error" in info:
            item = QTableWidgetItem(f"{info.get('file', '')} (unreadable)")
            self.table.setItem(row, 1, item)
            for col in range(2, len(TABLE_COLUMNS) + 1):
                self.table.setItem(row, col, QTableWidgetItem("-"))
            return
        for col, (_, key) in enumerate(TABLE_COLUMNS, start=1):
            item = QTableWidgetItem(str(info.get(key, "")))
            if key == "file":
                item.setToolTip(str(info.get(key, "")))
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
