"""Kênh log dùng chung: mọi nơi gọi log(...) → tab Hệ thống hiển thị + ghi ra file theo ngày.

File: <DATA>/logs/dubstudio-YYYY-MM-DD.log (giữ 14 ngày). Khi app lỗi, người dùng gửi file này cho bạn.
"""
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, Signal

KEEP_DAYS = 14
_lock = threading.Lock()


class _Bus(QObject):
    message = Signal(str, str)  # level, text


_bus = None


def bus() -> _Bus:
    global _bus
    if _bus is None:
        _bus = _Bus()
    return _bus


def log_dir() -> Path:
    from app.paths import DATA
    d = DATA / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_file() -> Path:
    return log_dir() / f"dubstudio-{datetime.now():%Y-%m-%d}.log"


def write_file(level: str, text: str) -> None:
    try:
        with _lock, open(log_file(), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} [{level.upper():5s}] {text}\n")
    except OSError:
        pass                                    # không ghi được file log thì thôi, không làm hỏng app


def cleanup_old() -> None:
    limit = datetime.now() - timedelta(days=KEEP_DAYS)
    for f in log_dir().glob("dubstudio-*.log"):
        try:
            if datetime.strptime(f.stem.split("-", 1)[1], "%Y-%m-%d") < limit:
                f.unlink()
        except (ValueError, OSError):
            pass


def log(text: str, level: str = "info") -> None:
    write_file(level, text)
    bus().message.emit(level, f"[{time.strftime('%H:%M:%S')}] {text}")
