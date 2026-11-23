"""Kênh log dùng chung: mọi nơi gọi log(...), tab Hệ thống hiển thị."""
import time

from PySide6.QtCore import QObject, Signal


class _Bus(QObject):
    message = Signal(str, str)  # level, text


_bus = None


def bus() -> _Bus:
    global _bus
    if _bus is None:
        _bus = _Bus()
    return _bus


def log(text: str, level: str = "info") -> None:
    bus().message.emit(level, f"[{time.strftime('%H:%M:%S')}] {text}")
