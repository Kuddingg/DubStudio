"""Chạy được cả khi chạy từ mã nguồn (python main.py) lẫn khi đã đóng gói thành .exe (PyInstaller)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent.parent
# Thư mục chứa file đi kèm (CHANGELOG.md...): bản .exe nằm trong _internal (sys._MEIPASS)
RES_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR)) if FROZEN else APP_DIR


def python_cmd() -> list[str]:
    """Lệnh tương đương `python` để chạy tác vụ nặng ở process riêng (Demucs, kiểm tra GPU).

    Bản .exe không có python.exe → dùng DubStudio-worker.exe (bản console của chính app) với cờ --py.
    """
    if FROZEN:
        return [str(APP_DIR / "DubStudio-worker.exe"), "--py"]
    exe = Path(sys.executable)
    console = exe.with_name("python.exe")         # app chạy bằng pythonw → dùng python.exe để có stdout/stderr
    return [str(console if console.exists() else exe)]


def setup_env() -> None:
    """Bản .exe: thêm FFmpeg đóng gói kèm vào PATH."""
    if FROZEN:
        ff = APP_DIR / "ffmpeg"
        if ff.exists():
            os.environ["PATH"] = str(ff) + os.pathsep + os.environ.get("PATH", "")


def run_py_mode(argv: list[str]) -> None:
    """Xử lý `DubStudio-worker.exe --py -m module ...` hoặc `--py -c code` (giống python)."""
    import runpy
    # Bản .exe bỏ qua PYTHONIOENCODING → console mặc định cp1252, in chữ tiếng Việt / ký tự đặc biệt sẽ chết.
    # Ép UTF-8 (app đọc output của worker bằng UTF-8).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = argv[2:]
    if args and args[0] == "-m":
        sys.argv = [args[1], *args[2:]]
        runpy.run_module(args[1], run_name="__main__", alter_sys=True)
    elif args and args[0] == "-c":
        sys.argv = ["-c", *args[2:]]
        exec(compile(args[1], "<string>", "exec"), {"__name__": "__main__"})
    else:
        print("Cách dùng: --py -m module [args] | --py -c code", file=sys.stderr)
        sys.exit(2)
