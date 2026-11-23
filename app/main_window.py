from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from core.log import log
from core.settings import Settings

from . import icons
from .pages.editor_page import EditorPage
from .pages.other_pages import HelpPage, ToolsPage
from .pages.script_page import ScriptPage
from .pages.system_page import SystemPage
from .paths import SETTINGS_FILE
from .theme import C
from .widgets.common import brand_mark, dark_titlebar, dot_pixmap, label

PAGES = [
    ("captions", "Biên tập & lồng tiếng", "Thêm video, chọn vùng phụ đề và chạy toàn bộ quy trình"),
    ("file-text", "Kịch bản dịch", "Preset prompt, thuật ngữ và bộ lọc từ cho AI dịch"),
    ("scissors", "Công cụ video", "Các tiện ích xử lý lẻ"),
    ("cpu", "Hệ thống", "Phần cứng, model AI, API key và thiết lập OCR"),
    ("help", "Hỗ trợ", "Quy trình, phím tắt và thông tin ứng dụng"),
]
NAV_TEXT = ["Biên tập", "Kịch bản dịch", "Công cụ", "Hệ thống", "Hỗ trợ"]
TONE_COLOR = {"ok": C["green"], "run": C["accent"], "warn": C["amber"], "err": C["red"]}


class Sidebar(QFrame):
    changed = Signal(int)

    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(224)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 18, 14, 14)
        v.setSpacing(4)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        mark = QLabel()
        mark.setPixmap(brand_mark(36))
        brand.addWidget(mark)
        bt = QVBoxLayout()
        bt.setSpacing(0)
        bt.addWidget(label("DubStudio", "Brand"))
        bt.addWidget(label("Dịch & lồng tiếng AI", "BrandSub"))
        brand.addLayout(bt)
        brand.addStretch()
        v.addLayout(brand)
        v.addSpacing(22)
        v.addWidget(label("MENU", "NavSection"))
        v.addSpacing(4)

        self.group = QButtonGroup(self)
        self.btns = []
        for i, ((ic, *_), text) in enumerate(zip(PAGES, NAV_TEXT)):
            b = QPushButton("  " + text)
            b.setObjectName("Nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setIconSize(icons.pixmap(ic).deviceIndependentSize().toSize())
            self.group.addButton(b, i)
            self.btns.append((b, ic))
            v.addWidget(b)
        self.group.idClicked.connect(self.select)
        v.addStretch()

        plan = QFrame()
        plan.setObjectName("PlanBox")
        pv = QVBoxLayout(plan)
        pv.setContentsMargins(12, 10, 12, 12)
        pv.setSpacing(4)
        top = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap("sparkles", C["amber"], 14))
        top.addWidget(ic)
        from core.version import VERSION
        top.addWidget(label(f"DubStudio {VERSION}", "Value"))
        top.addStretch()
        pv.addLayout(top)
        pv.addWidget(label("OCR · ASR · Dịch AI · Lồng tiếng", "Dim"))
        v.addWidget(plan)
        self.select(0)

    def select(self, i: int):
        self.group.button(i).setChecked(True)
        for k, (b, ic) in enumerate(self.btns):
            b.setIcon(icons.icon(ic, "#FFFFFF" if k == i else C["muted"], 18))
        self.changed.emit(i)


class TopBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("TopBar")
        self.setFixedHeight(68)
        h = QHBoxLayout(self)
        h.setContentsMargins(24, 0, 24, 0)
        v = QVBoxLayout()
        v.setSpacing(0)
        v.setAlignment(Qt.AlignVCenter)
        self.title = label("", "PageTitle")
        self.sub = label("", "PageSub")
        v.addWidget(self.title)
        v.addWidget(self.sub)
        h.addLayout(v)
        h.addStretch()
        pill = QFrame()
        pill.setObjectName("Pill")
        ph = QHBoxLayout(pill)
        ph.setContentsMargins(12, 6, 14, 6)
        ph.setSpacing(8)
        self.dot = QLabel()
        self.status = label("", "Value")
        ph.addWidget(self.dot)
        ph.addWidget(self.status)
        pill.setFixedHeight(32)
        h.addWidget(pill, 0, Qt.AlignVCenter)
        self.set_status("Sẵn sàng", "ok")

    def set_page(self, i: int):
        self.title.setText(PAGES[i][1])
        self.sub.setText(PAGES[i][2])

    def set_status(self, text: str, tone: str):
        self.status.setText(text)
        self.dot.setPixmap(dot_pixmap(TONE_COLOR.get(tone, C["muted"])))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DubStudio — Dịch & lồng tiếng video")
        self.setWindowIcon(icons.icon("wave", C["accent"], 32))
        self.resize(1520, 920)
        self.setMinimumSize(1240, 760)
        self.settings = Settings(SETTINGS_FILE)

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.sidebar = Sidebar()
        h.addWidget(self.sidebar)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.topbar = TopBar()
        right.addWidget(self.topbar)
        h.addLayout(right, 1)

        self.system = SystemPage()
        from core import secret
        self.system.set_values(secret.decrypt_section(self.settings.section("system")))
        self.scripts = ScriptPage()
        self.editor = EditorPage(self.scripts.names(), self.system.values)
        self.editor.config.set_values(self.settings.section("config"))

        self.stack = QStackedWidget()
        self.tools = ToolsPage(lambda: {**self.system.values(), **self.editor.config.values()}, self._apply_voice)
        for p in (self.editor, self.scripts, self.tools, self.system, HelpPage()):
            wrap = QWidget()
            lay = QVBoxLayout(wrap)
            lay.setContentsMargins(20, 18, 20, 20)
            lay.addWidget(p)
            self.stack.addWidget(wrap)
        right.addWidget(self.stack, 1)

        self.sidebar.changed.connect(self._go)
        self.scripts.presetsChanged.connect(self.editor.config.set_presets)
        self.editor.statusChanged.connect(self.topbar.set_status)
        self.system.changed.connect(lambda: self.editor.canvas.set_logo(self.system.values().get("logo_path") or None))

        self._save_timer = QTimer(self, singleShot=True, interval=700, timeout=self.save_settings)
        self.editor.configChanged.connect(self._save_timer.start)
        self.system.changed.connect(self._save_timer.start)
        self.system.recommend.connect(self._apply_recommend)
        self.system.checkUpdate.connect(lambda: self.check_update(manual=True))
        self._upd = self.settings.section("update")            # {"last_seen", "skip"}
        self._go(0)
        log("DubStudio đã sẵn sàng", "ok")
        QTimer.singleShot(800, self._warmup)
        QTimer.singleShot(600, self._whats_new)
        if self.system.values().get("auto_update", True):
            QTimer.singleShot(4000, lambda: self.check_update(manual=False))

    # ---------------------------------------------------------------- cập nhật
    def _whats_new(self):
        """Lần đầu mở sau khi cập nhật lên bản mới → hiện 'Có gì mới'."""
        from core import updater
        from core.version import VERSION
        last = self._upd.get("last_seen")
        if last and updater.is_newer(VERSION, last):
            from .dialogs.update_dialog import WhatsNewDialog
            WhatsNewDialog(VERSION, updater.changelog_notes(VERSION), self).exec()
        if last != VERSION:
            self._upd["last_seen"] = VERSION
            self.save_settings()

    def check_update(self, manual: bool = False):
        from core import updater
        from core.tasks import run_async

        from .widgets.common import toast
        if not updater.configured():
            if manual:
                toast(self, "Chưa cấu hình nguồn cập nhật (UPDATE_SOURCE trong core/version.py)", "warn")
            return
        if manual:
            toast(self, "Đang kiểm tra bản mới…", "info")

        def done(info):
            if not info:
                if manual:
                    toast(self, "Bạn đang dùng bản mới nhất", "ok")
                return
            if not manual and info["version"] == self._upd.get("skip"):
                return                                     # người dùng đã chọn bỏ qua bản này
            log(f"Có bản mới {info['version']}", "ok")
            self.show_update(info)

        def failed(err):
            log(f"Kiểm tra cập nhật: {err}", "warn")
            if manual:
                toast(self, err, "err")

        run_async(updater.check, on_done=done, on_error=failed)

    def show_update(self, info: dict):
        from PySide6.QtWidgets import QApplication

        from .dialogs.update_dialog import UpdateDialog
        dlg = UpdateDialog(info, self)
        dlg.exec()
        if dlg.result_action == "skip":
            self._upd["skip"] = info["version"]
            self.save_settings()
        elif dlg.result_action == "installing":
            self._quitting_for_update = True
            self.close()                                   # lưu cấu hình rồi thoát để bộ cài thay file
            QApplication.quit()

    def _warmup(self):
        """Sau khi cửa sổ hiện: nạp sẵn thư viện TTS ở nền rồi tạo sẵn câu đọc thử → bấm ▶ phát ngay."""
        from core import tts
        from core.tasks import run_async
        cfg = self.editor.config
        run_async(tts.warmup, on_done=lambda _: cfg.start_voice_warmup() if not hasattr(cfg, "_pending") else None,
                  on_error=lambda e: log(f"Không nạp được Edge-TTS: {e}", "warn"))

    def _apply_voice(self, voice: str, pitch: int, speed: float):
        self.editor.config.set_values({"voice": voice, "pitch": pitch, "speed": speed})
        self.save_settings()

    def _apply_recommend(self, reco: dict):
        from .widgets.common import toast
        self.editor.config.set_values({"encoder": reco.get("encoder", "CPU · x264")})
        self.system.set_values({"device": reco.get("device", "CPU")})
        self.save_settings()
        toast(self, f"Đã áp dụng: Encoder {reco.get('encoder')} · Thiết bị {reco.get('device')}", "ok")

    def _go(self, i: int):
        self.stack.setCurrentIndex(i)
        self.topbar.set_page(i)

    def save_settings(self):
        self.settings.set_section("config", self.editor.config.values())
        from core import secret
        self.settings.set_section("system", secret.encrypt_section(self.system.values()))   # API key mã hóa DPAPI
        if hasattr(self, "_upd"):
            self.settings.set_section("update", self._upd)
        self.settings.save()

    def showEvent(self, e):
        super().showEvent(e)
        dark_titlebar(self)

    def closeEvent(self, e):
        if self.editor.is_running():
            if QMessageBox.question(self, "Đang xử lý", "Video vẫn đang xử lý. Dừng và thoát?") != QMessageBox.Yes:
                e.ignore()
                return
            self.editor.worker.stop()
            self.editor.worker.wait(3000)
        self.save_settings()
        self.editor.save_jobs()
        super().closeEvent(e)
