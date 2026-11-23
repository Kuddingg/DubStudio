"""Bắt lỗi không lường trước: ghi traceback vào file log + báo người dùng (có nút mở thư mục nhật ký).

- sys.excepthook: lỗi ở luồng giao diện
- threading.excepthook: lỗi ở luồng nền
- faulthandler: app sập hẳn (lỗi thư viện C/C++) vẫn ghi lại được vào logs/crash.log
"""
import faulthandler
import platform
import sys
import threading
import traceback

from .log import cleanup_old, log_dir, log_file, write_file

_fault_file = None


_notifier = None


def _report(exc_type, exc, tb, where: str):
    detail = "".join(traceback.format_exception(exc_type, exc, tb))
    write_file("crash", f"Lỗi không mong muốn ({where}):\n{detail}")
    try:
        from PySide6.QtWidgets import QApplication
        if QApplication.instance() and _notifier is not None:
            _notifier.crashed.emit(exc)      # tín hiệu → hộp thoại hiện ở luồng giao diện (kể cả lỗi từ luồng nền)
    except Exception:  # noqa: BLE001
        pass


def _make_notifier():
    from PySide6.QtCore import QObject, Signal

    class _Notifier(QObject):
        crashed = Signal(object)

    n = _Notifier()
    n.crashed.connect(_show)
    return n


def _show(exc):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QMessageBox
    box = QMessageBox()
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle("DubStudio gặp lỗi")
    box.setText("Có lỗi không mong muốn. App vẫn chạy tiếp, nhưng thao tác vừa rồi có thể chưa hoàn tất.")
    box.setInformativeText(f"{type(exc).__name__}: {exc}\n\nChi tiết đã lưu ở:\n{log_file()}\n"
                           "Gửi file này cho nhà phát triển để được hỗ trợ.")
    open_btn = box.addButton("Mở thư mục nhật ký", QMessageBox.ActionRole)
    box.addButton("Đóng", QMessageBox.RejectRole)
    box.exec()
    if box.clickedButton() is open_btn:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir())))


def install(version: str):
    global _fault_file, _notifier
    cleanup_old()
    _notifier = _make_notifier()               # tạo ở luồng chính
    write_file("info", f"===== DubStudio {version} khởi động · Windows {platform.release()} "
                       f"({platform.version()}) · Python {platform.python_version()}")
    sys.excepthook = lambda t, e, tb: _report(t, e, tb, "giao diện")
    threading.excepthook = lambda a: _report(a.exc_type, a.exc_value, a.exc_traceback, f"luồng {a.thread.name}")
    try:
        _fault_file = open(log_dir() / "crash.log", "a", encoding="utf-8")
        faulthandler.enable(_fault_file)
    except OSError:
        pass
