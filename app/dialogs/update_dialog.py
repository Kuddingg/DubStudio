"""Cửa sổ "Có bản mới" (tải + cài) và "Có gì mới" (sau khi cập nhật)."""
from __future__ import annotations

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QProgressBar, QTextBrowser, QVBoxLayout

from core import updater
from core.version import VERSION

from .. import icons
from ..theme import C
from ..widgets.common import button, chip, dark_titlebar, label


def _notes_view(md: str) -> QTextBrowser:
    v = QTextBrowser()
    v.setObjectName("Console")
    v.setOpenExternalLinks(True)
    v.setMarkdown(md or "_Không có ghi chú._")
    v.setStyleSheet(f"QTextBrowser {{ font-family: '{QApplication.font().family()}'; font-size: 13px; color: {C['text']}; }}")
    v.setMinimumHeight(180)
    return v


class _Downloader(QThread):
    progress = Signal(float, float)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, info):
        super().__init__()
        self.info, self._stop = info, False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            p = updater.download(self.info, lambda d, t: self.progress.emit(float(d), float(t)), lambda: self._stop)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
            return
        self.done.emit(str(p) if p else "")


class UpdateDialog(QDialog):
    """Kết quả: 'later' | 'skip' | 'installing'."""

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        self.info, self.result_action, self.worker = info, "later", None
        self.setWindowTitle("Có bản cập nhật mới")
        self.resize(560, 460)
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(12)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap("download", C["accent"], 26))
        head.addWidget(ic)
        t = QVBoxLayout()
        t.setSpacing(2)
        t.addWidget(label(f"DubStudio {info['version']} đã có", "H2"))
        size = f" · {info['size'] / 1e6:.0f} MB" if info.get("size") else ""
        t.addWidget(label(f"Bạn đang dùng bản {VERSION}{size}", "Muted"))
        head.addLayout(t, 1)
        head.addWidget(chip("Mới", "ok"))
        v.addLayout(head)
        v.addWidget(label("Có gì mới:", "FieldLabel"))
        v.addWidget(_notes_view(info.get("notes", "")), 1)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setVisible(False)
        self.status = label("", "Muted", wrap=True)
        v.addWidget(self.bar)
        v.addWidget(self.status)
        if not updater.can_self_install() and not updater.is_portable():
            self.status.setText("Đang chạy từ mã nguồn: bấm Tải về để lưu bộ cài, rồi tự chạy nó.")
        row = QHBoxLayout()
        self.btn_skip = button("Bỏ qua bản này", None, "ghost")
        self.btn_skip.clicked.connect(lambda: self._close("skip"))
        self.btn_later = button("Để sau", None, "tool")
        self.btn_later.clicked.connect(lambda: self._close("later"))
        if updater.is_portable():
            # bản portable: không có bộ cài để cài đè → mở trang tải bản .zip mới
            self.status.setText("Bản portable: tải file DubStudio-Portable mới, giải nén đè lên thư mục hiện tại "
                                "(giữ nguyên thư mục data để không mất cấu hình).")
            self.btn_go = button("Mở trang tải bản mới", "download", "primary")
            self.btn_go.clicked.connect(self._open_page)
        else:
            self.btn_go = button("Cập nhật ngay" if updater.can_self_install() else "Tải về", "download", "primary")
            self.btn_go.clicked.connect(self._start)
        row.addWidget(self.btn_skip)
        row.addStretch()
        row.addWidget(self.btn_later)
        row.addWidget(self.btn_go)
        v.addLayout(row)

    def _open_page(self):
        QDesktopServices.openUrl(QUrl(updater.release_page()))
        self._close("later")

    def _close(self, action: str):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
        self.result_action = action
        self.accept()

    def _start(self):
        self.btn_go.setEnabled(False)
        self.btn_skip.setEnabled(False)
        self.btn_later.setText("Hủy")
        self.bar.setVisible(True)
        self.status.setText("Đang tải bản cập nhật…")
        self.worker = _Downloader(self.info)
        self.worker.progress.connect(self._progress)
        self.worker.done.connect(self._downloaded)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _progress(self, done: float, total: float):
        if total:
            self.bar.setValue(int(done / total * 1000))
            self.status.setText(f"Đang tải… {done / 1e6:.0f} / {total / 1e6:.0f} MB")
        else:
            self.status.setText(f"Đang tải… {done / 1e6:.0f} MB")

    def _failed(self, err: str):
        self.status.setText(f"✗ {err}")
        self.btn_go.setEnabled(True)
        self.btn_go.setText("Thử lại")
        self.btn_later.setText("Để sau")

    def _downloaded(self, path: str):
        if not path:
            return
        self.bar.setValue(1000)
        if updater.can_self_install():
            self.status.setText("Đã tải xong, đang cài đặt, app sẽ tự mở lại…")
            QApplication.processEvents()
            updater.launch_installer(path)
            self.result_action = "installing"
            self.accept()
        else:
            self.status.setText(f"✓ Đã tải về: {path}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(__import__("pathlib").Path(path).parent)))
            self.btn_later.setText("Đóng")

    def showEvent(self, e):
        super().showEvent(e)
        dark_titlebar(self)


class WhatsNewDialog(QDialog):
    def __init__(self, version: str, notes: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Có gì mới")
        self.resize(520, 400)
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(12)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap("sparkles", C["amber"], 26))
        head.addWidget(ic)
        head.addWidget(label(f"Đã cập nhật lên DubStudio {version}", "H2"), 1)
        v.addLayout(head)
        v.addWidget(_notes_view(notes), 1)
        row = QHBoxLayout()
        row.addStretch()
        ok = button("Bắt đầu dùng", "check", "primary")
        ok.clicked.connect(self.accept)
        row.addWidget(ok)
        v.addLayout(row)

    def showEvent(self, e):
        super().showEvent(e)
        dark_titlebar(self)
