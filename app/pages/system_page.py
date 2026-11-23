"""Tab Hệ thống: phần cứng, thành phần AI, API key, thiết lập OCR, lớp mặc định, nhật ký."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QScrollArea, QVBoxLayout, QWidget)

from core import system_info
from core.log import bus, log
from core.translate import GEMINI_MODELS
from core.tasks import run_async

from .. import icons
from ..theme import C
from ..widgets.binder import Binder
from ..widgets.common import (Card, ElidedLabel, LabeledToggle, SliderRow, button, combo, dot_pixmap,
                              field_label, form_grid, label)

LEVEL_COLOR = {"info": C["muted"], "ok": "#4ADE80", "warn": "#FCC86B", "error": "#FF8FA3"}


class StatTile(QFrame):
    def __init__(self, icon_name: str, title: str):
        super().__init__()
        self.setObjectName("StatTile")
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 10, 12, 10)
        h.setSpacing(10)
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, C["muted"], 18))
        h.addWidget(ic)
        v = QVBoxLayout()
        v.setSpacing(1)
        v.addWidget(label(title, "Dim"))
        self.value = ElidedLabel("Đang kiểm tra…", Qt.ElideRight)
        self.value.setStyleSheet("font-weight: 600;")
        v.addWidget(self.value)
        h.addLayout(v, 1)
        self.dot = QLabel()
        self.dot.setPixmap(dot_pixmap(C["dim"]))
        h.addWidget(self.dot)

    def set(self, text: str, ok: bool | None):
        self.value.setText(text)
        self.dot.setPixmap(dot_pixmap({True: C["green"], False: C["red"], None: C["amber"]}[ok]))


class SystemPage(QWidget):
    changed = Signal()
    recommend = Signal(dict)   # gợi ý cấu hình từ Kiểm tra GPU: {"encoder", "device"}
    checkUpdate = Signal()     # người dùng bấm "Kiểm tra cập nhật"

    def __init__(self):
        super().__init__()
        self.binder = Binder(self)
        self.binder.changed.connect(self.changed)
        self._checked = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 8, 0)
        v.setSpacing(16)
        scroll.setWidget(body)

        v.addWidget(self._hardware_card())
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(self._ai_card(), 1)
        row.addWidget(self._ocr_card(), 1)
        v.addLayout(row)
        row15 = QHBoxLayout()
        row15.setSpacing(16)
        row15.addWidget(self._gpu_card(), 1)
        row15.addWidget(self._ollama_card(), 1)
        v.addLayout(row15)
        row2 = QHBoxLayout()
        row2.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(16)
        left.addWidget(self._update_card())
        left.addWidget(self._layers_card(), 1)
        row2.addLayout(left, 1)
        row2.addWidget(self._log_card(), 1)
        v.addLayout(row2)
        v.addStretch()

    # ---------------------------------------------------------------- cards
    def _hardware_card(self):
        c = Card("Phần cứng & thành phần", "cpu", C["accent"])
        re = button("Kiểm tra lại", "refresh", "ghost")
        re.clicked.connect(self.check)
        c.header.addWidget(re)
        g = QGridLayout()
        g.setSpacing(10)
        spec = [("cpu", "cpu", "CPU"), ("ram", "layers", "RAM"), ("gpu", "zap", "GPU"),
                ("ffmpeg", "film", "FFmpeg"), ("yt-dlp", "download", "yt-dlp"),
                ("faster_whisper", "mic", "Whisper (ASR)"), ("paddleocr", "scan", "OCR engine"),
                ("demucs", "music", "Tách giọng (Demucs)"), ("edge_tts", "volume", "Edge-TTS")]
        self.tiles = {}
        for i, (k, ic, t) in enumerate(spec):
            self.tiles[k] = StatTile(ic, t)
            g.addWidget(self.tiles[k], i // 3, i % 3)
        c.add(g)
        return c

    def _ai_card(self):
        c = Card("AI & API key", "key", C["cyan"])
        b = self.binder
        g = form_grid()
        g.addWidget(field_label("Thiết bị"), 0, 0)
        g.addWidget(b.bind("device", combo(["Tự động", "GPU (CUDA)", "CPU"])), 0, 1)
        g.addWidget(field_label("Độ chính xác"), 1, 0)
        g.addWidget(b.bind("precision", combo(["Tự động", "float16", "int8", "float32"])), 1, 1)
        model = combo(GEMINI_MODELS)
        model.setToolTip("Tự động: dùng model tốt nhất, quá tải thì tự chuyển sang model dự phòng")
        g.addWidget(field_label("Model Gemini"), 2, 0)
        g.addWidget(b.bind("gemini_model", model), 2, 1)
        asr_m = combo(["small", "medium", "large-v3"])
        asr_m.setToolTip("Model nhận giọng nói (khi Trích xuất = Giọng (ASR)).\n"
                         "small: nhanh, ~480MB · medium: chính xác hơn, ~1.5GB · large-v3: tốt nhất, ~3GB (nên có GPU)")
        g.addWidget(field_label("Model ASR"), 3, 0)
        g.addWidget(b.bind("asr_model", asr_m), 3, 1)
        c.add(g)
        c.add(field_label("API key Gemini (mỗi dòng một key, tự đổi key khi hết quota)"))
        keys = QPlainTextEdit()
        keys.setObjectName("Console")
        keys.setPlaceholderText("AIza...\nAQ....")
        keys.setFixedHeight(96)
        b.bind("api_keys", keys)
        c.add(self._secret_box(keys))
        c.add(b.bind("creative_meta", LabeledToggle("Tự sinh tiêu đề, mô tả, tags cho video", True)))
        return c

    def _secret_box(self, edit: QPlainTextEdit) -> QWidget:
        """Ô nhập key có che: mặc định chỉ hiện đầu/cuối mỗi key, bấm 'Hiện / sửa' mới thấy đủ để sửa."""
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        masked = QPlainTextEdit()
        masked.setObjectName("Console")
        masked.setReadOnly(True)
        masked.setFixedHeight(edit.height() if edit.height() > 30 else 96)
        v.addWidget(masked)
        v.addWidget(edit)
        toggle = button("Hiện / sửa", "edit", "ghost", "Hiện đầy đủ key để sửa (nhớ ẩn lại khi quay màn hình)")
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(toggle)
        v.addLayout(row)

        def mask(k: str) -> str:
            return k if len(k) <= 10 else f"{k[:7]}{'•' * 10}{k[-4:]}"

        def refresh():
            lines = [ln.strip() for ln in edit.toPlainText().splitlines() if ln.strip()]
            masked.setPlainText("\n".join(mask(k) for k in lines) if lines else "")
            masked.setPlaceholderText("Chưa có key, bấm Hiện / sửa để nhập")

        def flip():
            showing = edit.isVisible()
            edit.setVisible(not showing)
            masked.setVisible(showing)
            toggle.setText("Hiện / sửa" if showing else "Ẩn")
            if showing:
                refresh()
            else:
                edit.setFocus()

        edit.setVisible(False)
        toggle.clicked.connect(flip)
        edit.textChanged.connect(refresh)
        refresh()
        return box

    def _update_card(self):
        from core import updater
        from core.version import VERSION
        c = Card("Cập nhật phần mềm", "download", C["accent"])
        src = updater.UPDATE_SOURCE.replace("github:", "GitHub: ") if updater.configured() else "chưa cấu hình (core/version.py)"
        c.add(label(f"Phiên bản đang dùng: {VERSION} · Nguồn cập nhật: {src}", "Muted", wrap=True))
        r = QHBoxLayout()
        r.addWidget(self.binder.bind("auto_update", LabeledToggle("Tự kiểm tra khi mở app", True)), 1)
        b = button("Kiểm tra cập nhật", "refresh", "tool")
        b.clicked.connect(self.checkUpdate)
        r.addWidget(b)
        c.add(r)
        return c

    def _gpu_card(self):
        c = Card("Kiểm tra GPU & tăng tốc", "zap", C["green"])
        c.add(label("Chạy khi mang app sang máy mới: thử thật encoder video, tách nhạc, OCR và nhận giọng nói "
                    "trên GPU, rồi gợi ý cấu hình nhanh nhất cho máy đó.", "Dim", wrap=True))
        self.gpu_result = QPlainTextEdit()
        self.gpu_result.setObjectName("Console")
        self.gpu_result.setReadOnly(True)
        self.gpu_result.setFixedHeight(130)
        self.gpu_result.setPlaceholderText("Bấm Chạy kiểm tra (mất khoảng 10–30 giây)")
        c.add(self.gpu_result)
        r = QHBoxLayout()
        self.btn_apply_gpu = button("Áp dụng gợi ý", "check", "primary")
        self.btn_apply_gpu.setEnabled(False)
        self.btn_apply_gpu.clicked.connect(lambda: self.recommend.emit(self._gpu_reco))
        run = button("Chạy kiểm tra", "zap", "tool")
        run.clicked.connect(self._run_gpu_check)
        r.addStretch()
        r.addWidget(run)
        r.addWidget(self.btn_apply_gpu)
        c.add(r)
        self._gpu_reco = {}
        return c

    def _run_gpu_check(self):
        from core import gpucheck
        self.gpu_result.setPlainText("Đang kiểm tra…")
        self.btn_apply_gpu.setEnabled(False)

        def done(rep: dict):
            lines = [f"{'✓' if ok else ('–' if ok is None else '✗')} {name}: {msg}" for name, ok, msg in rep["items"]]
            lines.append(f"→ Gợi ý: Encoder = {rep['encoder']} · Thiết bị = {rep['device']}")
            self.gpu_result.setPlainText("\n".join(lines))
            self._gpu_reco = {"encoder": rep["encoder"], "device": rep["device"]}
            self.btn_apply_gpu.setEnabled(True)
            log("Kiểm tra GPU: " + lines[-1], "ok")

        run_async(gpucheck.run, on_done=done, on_error=lambda e: self.gpu_result.setPlainText(f"Lỗi: {e}"))

    def _ollama_card(self):
        c = Card("Ollama (AI dịch chạy trên máy)", "cpu", C["cyan"])
        b = self.binder
        c.add(label("Cài Ollama từ ollama.com rồi tải model, vd: ollama pull qwen2.5:7b. "
                    "Ở tab Biên tập chọn AI dịch = Ollama.", "Dim", wrap=True))
        g = form_grid()
        url = b.bind("ollama_url", QLineEdit("http://localhost:11434"))
        self.ollama_model = combo(["qwen2.5:7b", "qwen2.5:14b", "qwen3:8b"])
        self.ollama_model.setEditable(True)
        b.bind("ollama_model", self.ollama_model)
        self.ollama_model.editTextChanged.connect(lambda *_: self.changed.emit())
        g.addWidget(field_label("Địa chỉ"), 0, 0)
        g.addWidget(url, 0, 1)
        g.addWidget(field_label("Model"), 1, 0)
        g.addWidget(self.ollama_model, 1, 1)
        c.add(g)
        r = QHBoxLayout()
        self.ollama_status = label("", "Dim", wrap=True)
        r.addWidget(self.ollama_status, 1)
        test = button("Kiểm tra", "refresh", "tool", "Kết nối Ollama và lấy danh sách model đã tải")
        test.clicked.connect(self._test_ollama)
        r.addWidget(test)
        c.add(r)
        return c

    def _test_ollama(self):
        from core.translate import OllamaClient
        v = self.values()
        client = OllamaClient(v.get("ollama_url", ""), v.get("ollama_model", ""))
        self.ollama_status.setText("Đang kết nối…")

        def done(models: list):
            if not models:
                self.ollama_status.setText("Kết nối được nhưng chưa tải model nào: chạy ollama pull qwen2.5:7b")
                return
            cur = self.ollama_model.currentText()
            self.ollama_model.blockSignals(True)
            self.ollama_model.clear()
            self.ollama_model.addItems(models)
            self.ollama_model.setCurrentText(cur if cur in models else models[0])
            self.ollama_model.blockSignals(False)
            self.changed.emit()
            ok = cur in models
            self.ollama_status.setText(f"✓ {len(models)} model: {', '.join(models[:4])}"
                                       + ("" if ok else f" (chưa có “{cur}”, đã chọn {models[0]})"))

        run_async(client.list_models, on_done=done, on_error=lambda e: self.ollama_status.setText(f"✗ {e}"))

    def _ocr_card(self):
        c = Card("Thiết lập OCR", "scan", C["green"])
        b = self.binder
        lw = 96
        c.add(b.bind("ocr_conf", SliderRow("Độ tin cậy", 0, 1, 0.75, 0.01, 2, label_width=lw)))
        c.add(b.bind("ocr_fps", SliderRow("Số khung/giây", 1, 30, 5, 1, 0, label_width=lw)))
        c.add(b.bind("ocr_sens", SliderRow("Ngưỡng đổi câu", 0.05, 0.8, 0.25, 0.01, 2, label_width=lw)))
        c.add(b.bind("ocr_merge", SliderRow("Gộp câu", 0, 1, 0.75, 0.01, 2, label_width=lw)))
        c.add(b.bind("ocr_gap", SliderRow("Khoảng nghỉ", 0, 2, 0.3, 0.05, 2, "s", label_width=lw)))
        c.add(b.bind("ocr_pad", SliderRow("Đệm thời gian", 0, 1, 0.1, 0.05, 2, "s", label_width=lw)))
        c.add(b.bind("ocr_max", SliderRow("Ký tự tối đa", 20, 200, 100, 1, 0, label_width=lw)))
        reset = button("Khôi phục mặc định", "refresh", "ghost")
        reset.clicked.connect(lambda: self.binder.set_values(
            {"ocr_conf": 0.75, "ocr_fps": 5, "ocr_sens": 0.25, "ocr_merge": 0.75,
             "ocr_gap": 0.3, "ocr_pad": 0.1, "ocr_max": 100}) or self.changed.emit())
        r = QHBoxLayout()
        r.addStretch()
        r.addWidget(reset)
        c.add(r)
        return c

    def _layers_card(self):
        c = Card("Lớp mặc định khi thêm video", "layers", C["amber"])
        b = self.binder
        c.add(b.bind("auto_layers", LabeledToggle("Tự động thêm logo / watermark cho video mới", False)))
        g = form_grid()
        self.logo = b.bind("logo_path", QLineEdit())
        self.logo.setPlaceholderText("Đường dẫn file PNG")
        pick = button("", "folder", "tool", "Chọn logo")
        pick.clicked.connect(self._pick_logo)
        lr = QHBoxLayout()
        lr.setSpacing(6)
        lr.addWidget(self.logo, 1)
        lr.addWidget(pick)
        g.addWidget(field_label("Logo"), 0, 0)
        g.addLayout(lr, 0, 1)
        wm = b.bind("watermark", QLineEdit("@kenh_cua_ban"))
        g.addWidget(field_label("Watermark"), 1, 0)
        g.addWidget(wm, 1, 1)
        c.add(g)
        c.add(label("Vùng logo/chữ vẫn kéo thả được trên khung xem trước của từng video.", "Dim", wrap=True))
        c.body.addStretch()
        return c

    def _log_card(self):
        c = Card("Nhật ký", "terminal", C["muted"])
        clear = button("Xóa", "trash", "ghost")
        c.header.addWidget(clear)
        self.console = QPlainTextEdit()
        self.console.setObjectName("Console")
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(200)
        self.console.setMaximumBlockCount(2000)
        clear.clicked.connect(self.console.clear)
        c.add(self.console, 1)
        bus().message.connect(self.append_log)
        return c

    # ---------------------------------------------------------------- logic
    def append_log(self, level: str, text: str):
        color = LEVEL_COLOR.get(level, C["muted"])
        self.console.appendHtml(f'<span style="color:{color}">{text.replace("<", "&lt;")}</span>')
        self.console.moveCursor(QTextCursor.End)

    def _pick_logo(self):
        f, _ = QFileDialog.getOpenFileName(self, "Chọn logo", "", "Ảnh (*.png *.jpg *.webp)")
        if f:
            self.logo.setText(f)

    def check(self):
        for t in self.tiles.values():
            t.set("Đang kiểm tra…", None)
        run_async(system_info.detect, on_done=self._show_info,
                  on_error=lambda e: log(f"Kiểm tra hệ thống lỗi: {e}", "error"))

    def _show_info(self, i: dict):
        t = self.tiles
        t["cpu"].set(i["cpu"], True)
        t["ram"].set(i["ram"], True)
        t["gpu"].set(i["gpu"], i["cuda"] or None)
        t["ffmpeg"].set("Đã tìm thấy" if i["ffmpeg"] and i["ffprobe"] else "Chưa cài", i["ffmpeg"] and i["ffprobe"])
        t["yt-dlp"].set("Đã tìm thấy" if i["yt-dlp"] else "Chưa cài (tùy chọn)", True if i["yt-dlp"] else None)
        for k in ("faster_whisper", "paddleocr", "demucs", "edge_tts"):
            t[k].set("Sẵn sàng" if i[k] else "Chưa cài", True if i[k] else None)
        log(f"GPU: {i['gpu']} · RAM {i['ram']} · FFmpeg {'OK' if i['ffmpeg'] else 'thiếu'}",
            "ok" if i["ffmpeg"] else "warn")

    def showEvent(self, e):
        super().showEvent(e)
        if not self._checked:
            self._checked = True
            self.check()

    def values(self) -> dict:
        return self.binder.values()

    def set_values(self, d: dict):
        self.binder.set_values(d)
