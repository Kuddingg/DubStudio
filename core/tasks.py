"""Chạy hàm nặng (ffprobe, cắt frame, quét hệ thống...) trên thread nền, trả kết quả về UI thread."""
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Sig(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Task(QRunnable):
    def __init__(self, fn, args, sig):
        super().__init__()
        self.fn, self.args, self.sig = fn, args, sig

    def run(self):
        try:
            try:
                result = self.fn(*self.args)
            except Exception as e:  # noqa: BLE001 - báo lỗi về UI
                self.sig.failed.emit(str(e))
                return
            self.sig.done.emit(result)
        except RuntimeError:
            pass  # app đã đóng trong lúc việc nền còn chạy → không còn ai nhận kết quả


_alive: set = set()


def run_async(fn, *args, on_done=None, on_error=None) -> None:
    sig = _Sig()  # tạo ở UI thread → signal tự chuyển về UI thread
    _alive.add(sig)
    if on_done:
        sig.done.connect(on_done)
    if on_error:
        sig.failed.connect(on_error)
    sig.done.connect(lambda *_: _alive.discard(sig))
    sig.failed.connect(lambda *_: _alive.discard(sig))
    QThreadPool.globalInstance().start(_Task(fn, args, sig))
