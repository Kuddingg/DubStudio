import sys

from core import runtime


def main():
    from PySide6.QtWidgets import QApplication

    from app import theme
    from app.main_window import MainWindow
    from core import crash
    from core.version import VERSION

    crash.install(VERSION)                       # ghi lỗi bất ngờ ra file + báo người dùng
    app = QApplication(sys.argv)
    app.setApplicationName("DubStudio")
    theme.apply(app)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    if len(sys.argv) > 1 and sys.argv[1] == "--py":     # DubStudio-worker.exe --py -m demucs.separate ...
        runtime.run_py_mode(sys.argv)
        sys.exit(0)
    runtime.setup_env()
    main()
