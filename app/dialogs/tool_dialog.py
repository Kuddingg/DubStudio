"""Cửa sổ chạy một công cụ lẻ: nhập tham số → chạy nền (có tiến độ, dừng được) → xem / mở kết quả."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QDoubleSpinBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QProgressBar, QPushButton, QVBoxLayout, QWidget)

from .. import icons
from ..theme import C
from ..widgets.common import Card, button, combo, dark_titlebar, field_label, form_grid, label, no_buttons, toast

FILTERS = {
    "video": "Video (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.m4v *.ts);;Tất cả (*.*)",
    "media": "Video / âm thanh (*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.wav *.m4a *.aac *.flac);;Tất cả (*.*)",
    "srt": "Phụ đề SubRip (*.srt)",
}


class ToolWorker(QThread):
    progress = Signal(float, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, params: dict, cfg: dict):
        super().__init__()
        self.fn, self.params, self.cfg = fn, params, cfg
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            res = self.fn(self.params, self.cfg, lambda p, m="": self.progress.emit(float(p), m), lambda: self._stop)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
            return
        self.done.emit(res or {})


class ToolDialog(QDialog):
    """fields: list[(key, nhãn, kiểu, tùy chọn)] — kiểu: file:video|media|srt, url, combo, number."""

    def __init__(self, title: str, icon_name: str, color: str, desc: str, fields: list, fn, get_cfg, parent=None,
                 result_widget=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(640, 420)
        self.fn, self.get_cfg, self.result_widget = fn, get_cfg, result_widget
        self.inputs: dict = {}
        self.worker: ToolWorker | None = None
        self.files: list[str] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 18)
        root.setSpacing(12)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, color, 22))
        head.addWidget(ic)
        head.addWidget(label(title, "H2"))
        head.addStretch()
        root.addLayout(head)
        root.addWidget(label(desc, "Muted", wrap=True))

        card = Card(padding=14)
        g = form_grid()
        for r, (key, text, kind, opt) in enumerate(fields):
            g.addWidget(field_label(text), r, 0)
            g.addWidget(self._field(key, kind, opt), r, 1)
        card.add(g)
        root.addWidget(card)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.status = label("", "Muted", wrap=True)
        root.addWidget(self.bar)
        root.addWidget(self.status)
        self.result_box = QVBoxLayout()
        root.addLayout(self.result_box)
        root.addStretch()

        btns = QHBoxLayout()
        self.btn_open = button("Mở thư mục kết quả", "folder", "ghost")
        self.btn_open.setVisible(False)
        self.btn_open.clicked.connect(self._open)
        btns.addWidget(self.btn_open)
        btns.addStretch()
        self.btn_stop = button("Dừng", "stop", "danger")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)
        self.btn_run = button("Chạy", "play", "primary")
        self.btn_run.setMinimumWidth(110)
        self.btn_run.clicked.connect(self._run)
        btns.addWidget(self.btn_stop)
        btns.addWidget(self.btn_run)
        root.addLayout(btns)

    # ---------------------------------------------------------------- fields
    def _field(self, key, kind, opt) -> QWidget:
        if kind.startswith("file"):
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            e = QLineEdit()
            e.setPlaceholderText(opt or "Chọn file…")
            b = button("", "folder", "tool", "Chọn file")
            flt = FILTERS.get(kind.split(":")[1], "")
            b.clicked.connect(lambda: self._pick(e, flt))
            h.addWidget(e, 1)
            h.addWidget(b)
            self.inputs[key] = e
            return w
        if kind == "url":
            e = QLineEdit()
            e.setPlaceholderText(opt or "https://…")
            self.inputs[key] = e
            return e
        if kind == "combo":
            c = combo(opt)
            self.inputs[key] = c
            return c
        if kind == "number":
            lo, hi, val, suffix = opt
            s = no_buttons(QDoubleSpinBox())
            s.setRange(lo, hi)
            s.setValue(val)
            s.setSuffix(suffix)
            s.setDecimals(0)
            self.inputs[key] = s
            return s
        raise ValueError(kind)

    def _pick(self, edit: QLineEdit, flt: str):
        f, _ = QFileDialog.getOpenFileName(self, "Chọn file", edit.text(), flt)
        if f:
            edit.setText(f)

    def _values(self) -> dict:
        v = {}
        for k, w in self.inputs.items():
            if isinstance(w, QLineEdit):
                v[k] = w.text().strip()
            elif isinstance(w, QDoubleSpinBox):
                v[k] = w.value()
            else:
                v[k] = w.currentText()
        return v

    # ---------------------------------------------------------------- run
    def _run(self):
        p = self._values()
        for k, w in self.inputs.items():
            if isinstance(w, QLineEdit) and not p[k] and not w.placeholderText().startswith("(tùy chọn"):
                toast(self, "Hãy điền đủ thông tin", "warn")
                return
            if isinstance(w, QLineEdit) and p[k] and not p[k].startswith("http") and not Path(p[k]).exists():
                toast(self, f"Không tìm thấy file: {p[k]}", "err")
                return
        self._clear_result()
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_open.setVisible(False)
        self.bar.setValue(0)
        self.status.setText("Đang chạy…")
        self.worker = ToolWorker(self.fn, p, self.get_cfg())
        self.worker.progress.connect(self._progress)
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _progress(self, p: float, msg: str):
        self.bar.setValue(int(p * 1000))
        if msg:
            self.status.setText(msg)

    def _done(self, res: dict):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if not res:
            self.status.setText("Đã dừng")
            return
        self.bar.setValue(1000)
        self.files = res.get("files", [])
        names = "\n".join(f"• {Path(f).name}" for f in self.files)
        self.status.setText(f"✓ {res.get('message', 'Xong')}" + (f"\n{names}" if names else ""))
        self.btn_open.setVisible(bool(self.files))
        if self.result_widget:
            w = self.result_widget(res, self)
            if w:
                self.result_box.addWidget(w)
                self.resize(self.width(), max(self.height(), 560))

    def _failed(self, err: str):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status.setText(f"✗ {err}")

    def _stop(self):
        if self.worker:
            self.worker.stop()
            self.status.setText("Đang dừng…")

    def _clear_result(self):
        while self.result_box.count():
            it = self.result_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def _open(self):
        if self.files:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.files[0]).parent)))

    def showEvent(self, e):
        super().showEvent(e)
        dark_titlebar(self)

    def closeEvent(self, e):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(5000)
        super().closeEvent(e)
