"""Cột cấu hình bên trái của tab Biên tập."""
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QFileDialog, QFontComboBox, QGridLayout,
                               QHBoxLayout, QLineEdit, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from .. import theme
from ..theme import C
from ..widgets.binder import Binder
from ..widgets.common import (Card, ColorSwatch, LabeledToggle, Segmented, SliderRow, button, combo,
                              divider, field_label, form_grid, label, no_buttons, shrinkable, toast)

from core.tts import VOICE_LABELS as VOICES  # noqa: E402


class SubPreview(QWidget):
    """Xem trước kiểu phụ đề ngay trong panel."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(74)
        self.style_ = {}

    def set_style(self, s: dict):
        self.style_ = s
        self.update()

    def paintEvent(self, e):
        s = self.style_
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(0, 0, r.width(), r.height())
        g.setColorAt(0, QColor("#1E3A44"))
        g.setColorAt(0.6, QColor("#2A2140"))
        g.setColorAt(1, QColor("#3B2430"))
        clip = QPainterPath()
        clip.addRoundedRect(r, 10, 10)
        p.setClipPath(clip)
        p.fillRect(r, g)

        text = "Đây là phụ đề tiếng Việt mẫu"
        f = QFont(s.get("sub_font") or theme.FONT)
        f.setBold(bool(s.get("sub_bold", True)))
        f.setPixelSize(int(max(11, min(26, s.get("sub_size", 48) * 0.36))))
        fm = QFontMetricsF(f)
        w = fm.horizontalAdvance(text)
        if w > r.width() - 20:
            f.setPixelSize(max(9, int(f.pixelSize() * (r.width() - 20) / w)))
            fm = QFontMetricsF(f)
            w = fm.horizontalAdvance(text)
        base = QPointF(r.center().x() - w / 2, r.bottom() - 16)
        if s.get("sub_box"):
            box = QColor(s.get("sub_box_color", "#000000"))
            box.setAlpha(170)
            p.setPen(Qt.NoPen)
            p.setBrush(box)
            p.drawRoundedRect(QRectF(base.x() - 8, base.y() - fm.ascent() - 4, w + 16, fm.height() + 8), 4, 4)
        path = QPainterPath()
        path.addText(base, f, text)
        ow = float(s.get("sub_outline_w", 3))
        if ow > 0:
            p.setPen(QPen(QColor(s.get("sub_outline", "#000000")), ow * 0.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(s.get("sub_color", "#FFE14D")))
        p.drawPath(path)


class ConfigPanel(QScrollArea):
    changed = Signal()

    def __init__(self, preset_names: list[str]):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFixedWidth(372)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.binder = Binder(self)
        self.binder.changed.connect(self.changed)
        self.binder.changed.connect(self._refresh_preview)

        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 8, 0)
        v.setSpacing(12)
        v.addWidget(self._output_card())
        v.addWidget(self._translate_card(preset_names))
        v.addWidget(self._voice_card())
        v.addWidget(self._sub_card())
        v.addStretch()
        self.setWidget(body)
        self._refresh_preview()

    # ----------------------------------------------------------------- cards
    def _output_card(self):
        c = Card("Xuất bản", "upload", C["accent2"])
        b = self.binder
        g = form_grid()
        self.out = b.bind("output", QLineEdit(str(Path.home() / "Videos" / "DubStudio")))
        browse = button("", "folder", "tool", "Chọn thư mục xuất")
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self.out, 1)
        row.addWidget(browse)
        g.addWidget(field_label("Thư mục"), 0, 0)
        g.addLayout(row, 0, 1)
        g.addWidget(field_label("Tỉ lệ"), 1, 0)
        g.addWidget(b.bind("ratio", combo(["Giữ nguyên", "9:16 · TikTok / Shorts", "16:9 · YouTube", "1:1 · Vuông"])), 1, 1)
        g.addWidget(field_label("Nền"), 2, 0)
        g.addWidget(b.bind("bg", combo(["Nền mờ", "Nền đen", "Phóng to lấp đầy"])), 2, 1)
        g.addWidget(field_label("Encoder"), 3, 0)
        g.addWidget(b.bind("encoder", combo(["NVIDIA NVENC", "CPU · x264", "Intel QuickSync", "AMD AMF"])), 3, 1)
        g.addWidget(field_label("Chất lượng"), 4, 0)
        g.addWidget(b.bind("quality", combo(["Cao", "Cân bằng", "Nhanh"], "Cân bằng")), 4, 1)
        c.add(g)
        c.add(divider())
        t = QGridLayout()
        t.setHorizontalSpacing(12)
        t.setVerticalSpacing(10)
        t.addWidget(b.bind("do_sub", LabeledToggle("Phụ đề", True, "Ghép phụ đề tiếng Việt vào video")), 0, 0)
        t.addWidget(b.bind("do_dub", LabeledToggle("Lồng tiếng", True, "Tạo giọng đọc AI và trộn vào video")), 0, 1)
        t.addWidget(b.bind("do_render", LabeledToggle("Render", True, "Xuất file video cuối cùng")), 1, 0)
        c.add(t)
        return c

    def _translate_card(self, presets):
        c = Card("Dịch thuật", "languages", C["cyan"])
        b = self.binder
        g = form_grid()
        self.preset = b.bind("preset", combo(presets))
        g.addWidget(field_label("Kịch bản"), 0, 0)
        g.addWidget(self.preset, 0, 1)
        g.addWidget(field_label("Trích xuất"), 1, 0)
        g.addWidget(b.bind("extract", Segmented(["Hình (OCR)", "Giọng (ASR)"])), 1, 1)
        g.addWidget(field_label("Ngôn ngữ"), 2, 0)
        lang = QHBoxLayout()
        lang.setSpacing(6)
        lang.addWidget(b.bind("src_lang", combo(["Tự nhận diện", "Tiếng Trung", "Tiếng Anh", "Tiếng Hàn", "Tiếng Nhật"])), 1)
        lang.addWidget(label("→", "Muted"))
        lang.addWidget(b.bind("dst_lang", combo(["Tiếng Việt", "English", "Bahasa Indonesia", "ภาษาไทย"])), 1)
        g.addLayout(lang, 2, 1)
        g.addWidget(field_label("AI dịch"), 3, 0)
        g.addWidget(b.bind("llm", combo(["Gemini", "Ollama · chạy local"])), 3, 1)
        c.add(g)
        c.add(b.bind("keep_translation", LabeledToggle(
            "Giữ bản dịch đã có", True,
            "Chạy lại thì giữ nguyên câu đã dịch / đã sửa tay, chỉ dịch câu còn trống.\n"
            "Tắt đi khi muốn dịch lại toàn bộ (vd vừa đổi kịch bản).")))
        return c

    def _voice_card(self):
        c = Card("Giọng đọc AI", "mic", C["green"])
        b = self.binder
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(b.bind("voice", combo(VOICES)), 1)
        self.btn_test_voice = button("", "play", "tool", "Nghe thử giọng với tốc độ đang chọn")
        self.btn_test_voice.clicked.connect(self._preview_voice)
        row.addWidget(self.btn_test_voice)
        c.add(row)

        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(8)
        speed = no_buttons(QDoubleSpinBox())
        speed.setRange(0.5, 2.0)
        speed.setSingleStep(0.05)
        speed.setValue(1.0)
        speed.setSuffix(" x")
        lead = no_buttons(QSpinBox())
        lead.setRange(-2000, 2000)
        lead.setSingleStep(50)
        lead.setSuffix(" ms")
        lead.setToolTip("Đọc sớm/muộn hơn mốc thời gian của phụ đề")
        g.addWidget(field_label("Tốc độ"), 0, 0)
        g.addWidget(b.bind("speed", speed), 0, 1)
        g.addWidget(field_label("Lệch"), 0, 2)
        g.addWidget(b.bind("lead", lead), 0, 3)
        pitch = no_buttons(QSpinBox())
        pitch.setRange(-50, 50)
        pitch.setSingleStep(5)
        pitch.setSuffix(" Hz")
        pitch.setToolTip("Âm = giọng trầm hơn, dương = cao hơn. Chỉ áp dụng cho giọng Edge (HoaiMy, NamMinh).\n"
                         "Ví dụ HoaiMy −10 Hz khớp giọng đọc bản tin trong video mẫu.")
        g.addWidget(field_label("Cao độ"), 1, 0)
        g.addWidget(b.bind("pitch", pitch), 1, 1)
        g.setColumnStretch(1, 1)
        g.setColumnStretch(3, 1)
        c.add(g)

        c.add(b.bind("smart_voice", LabeledToggle("Smart Voice", True, "Tự co giãn tốc độ đọc cho khớp thời lượng câu")))
        c.add(b.bind("keep_music", LabeledToggle("Giữ nhạc nền", True, "Tách giọng gốc bằng AI, giữ lại nhạc nền")))
        c.add(divider())
        c.add(b.bind("vol_music", SliderRow("Nhạc nền", 0, 200, 100, suffix="%")))
        c.add(b.bind("vol_ai", SliderRow("Giọng AI", 0, 200, 120, suffix="%")))
        c.add(b.bind("vol_orig", SliderRow("Giọng gốc", 0, 100, 0, suffix="%")))
        c.add(divider())
        c.add(label("Xử lý âm thanh", "Dim"))
        fx = QGridLayout()
        fx.setHorizontalSpacing(12)
        fx.setVerticalSpacing(8)
        for i, (k, t) in enumerate([("fx_eq", "Equalizer"), ("fx_hp", "High-pass"),
                                    ("fx_comp", "Compressor"), ("fx_norm", "Normalize")]):
            cb = QCheckBox(t)
            cb.setChecked(True)
            cb.setCursor(Qt.PointingHandCursor)
            fx.addWidget(b.bind(k, cb), i // 2, i % 2)
        c.add(fx)
        return c

    def _sub_card(self):
        c = Card("Kiểu phụ đề", "type", C["amber"])
        b = self.binder
        self.preview = SubPreview()
        c.add(self.preview)
        g = form_grid()
        font = shrinkable(QFontComboBox())
        font.setCurrentFont(QFont("Arial"))
        g.addWidget(field_label("Font"), 0, 0)
        g.addWidget(b.bind("sub_font", font), 0, 1)
        size = no_buttons(QSpinBox())
        size.setRange(10, 140)
        size.setValue(48)
        size.setSuffix(" px")
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(b.bind("sub_size", size), 1)
        row.addWidget(field_label("Màu"))
        row.addWidget(b.bind("sub_color", ColorSwatch("#FFE14D", "Màu chữ")))
        g.addWidget(field_label("Cỡ chữ"), 1, 0)
        g.addLayout(row, 1, 1)
        ow = no_buttons(QSpinBox())
        ow.setRange(0, 12)
        ow.setValue(3)
        ow.setSuffix(" px")
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(b.bind("sub_outline_w", ow), 1)
        row2.addWidget(field_label("Màu"))
        row2.addWidget(b.bind("sub_outline", ColorSwatch("#000000", "Màu viền")))
        g.addWidget(field_label("Viền"), 2, 0)
        g.addLayout(row2, 2, 1)
        c.add(g)
        row3 = QHBoxLayout()
        row3.addWidget(b.bind("sub_bold", LabeledToggle("In đậm", True)))
        row3.addWidget(b.bind("sub_box", LabeledToggle("Nền chữ", False)))
        row3.addWidget(b.bind("sub_box_color", ColorSwatch("#000000", "Màu nền chữ")))
        c.add(row3)
        g2 = form_grid()
        place = combo(["Tự động", "Trên video (theo vùng Sub)", "Vùng trống của khung mới"])
        place.setToolTip("Khi đổi khung (vd 9:16): Tự động = đặt phụ đề vào vùng nền trống dưới video nếu đủ chỗ,\n"
                         "chữ to và dễ đọc hơn. Trên video = giữ đúng vị trí vùng Sub đã kéo.")
        g2.addWidget(field_label("Vị trí"), 0, 0)
        g2.addWidget(b.bind("sub_place", place), 0, 1)
        c.add(g2)
        return c

    # ----------------------------------------------------------------- voice preview
    # Tạo sẵn câu đọc thử ở nền (lúc mở app và mỗi khi đổi giọng/tốc độ) → bấm ▶ là phát ngay.
    def start_voice_warmup(self):
        """Gọi sau khi cửa sổ hiện: nạp sẵn trình phát + thư viện TTS, tạo sẵn câu đọc thử."""
        from PySide6.QtCore import QTimer
        self._pending: set[str] = set()
        self._play_when_ready: str | None = None
        self._prefetch_timer = QTimer(self, singleShot=True, interval=700, timeout=self._prefetch_voice)
        # lambda: không để tín hiệu truyền nhầm tham số (số thứ tự / giá trị) vào QTimer.start(msec)
        self.binder.fields["voice"].currentIndexChanged.connect(lambda *_: self._prefetch_timer.start())
        self.binder.fields["speed"].valueChanged.connect(lambda *_: self._prefetch_timer.start())
        self.binder.fields["pitch"].valueChanged.connect(lambda *_: self._prefetch_timer.start())
        self._ensure_player()
        self._prefetch_voice()

    def _sample_path(self):
        from core import tts

        from ..paths import CACHE
        v = self.values()
        try:
            vid = tts.voice_id(v["voice"])
        except tts.TTSError:
            return None, v
        pch = tts.eff_pitch(vid, v.get("pitch", 0))
        suffix = "" if pch == "+0Hz" else f"_{pch}"
        return CACHE / f"voice_{vid}_{tts.rate_str(v['speed'])}{suffix}.mp3", v

    def _ensure_player(self):
        if hasattr(self, "_player"):
            return
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._player.errorOccurred.connect(
            lambda _e, msg: toast(self, f"Không phát được âm thanh: {msg or 'lỗi thiết bị âm thanh'}", "err"))

    def _prefetch_voice(self):
        out, v = self._sample_path()
        if out is None or out.exists() or str(out) in self._pending:
            return
        from core import tts
        from core.log import log
        from core.tasks import run_async
        self._pending.add(str(out))

        def done(path, key=str(out)):
            self._pending.discard(key)
            if self._play_when_ready == key:
                self._play_when_ready = None
                self._play(path)

        def failed(err, key=str(out)):
            self._pending.discard(key)
            log(f"Tạo sẵn giọng đọc thử lỗi: {err}", "warn")
            if self._play_when_ready == key:
                self._play_when_ready = None
                self.btn_test_voice.setEnabled(True)
                toast(self, f"Không nghe thử được: {err}", "err")

        run_async(tts.synth_one, tts.SAMPLE, v["voice"], v["speed"], out, v.get("pitch", 0),
                  on_done=done, on_error=failed)

    def _play(self, path):
        from PySide6.QtCore import QUrl
        self._ensure_player()
        self.btn_test_voice.setEnabled(True)
        self._player.stop()
        self._player.setSource(QUrl())          # ép nạp lại file kể cả khi bấm lần 2
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._player.play()

    def _preview_voice(self):
        if not hasattr(self, "_pending"):
            self.start_voice_warmup()
        out, v = self._sample_path()
        if out is None:
            from core import tts
            try:
                tts.voice_id(v["voice"])
            except tts.TTSError as e:
                toast(self, str(e), "warn")
            return
        if out.exists():
            self._play(out)                       # đã tạo sẵn → phát ngay
            return
        # chưa có (vừa đổi giọng hoặc đang tạo dở) → phát ngay khi tạo xong
        self._play_when_ready = str(out)
        self.btn_test_voice.setEnabled(False)
        toast(self, "Đang tạo giọng đọc thử…", "info")
        self._prefetch_voice()

    # ----------------------------------------------------------------- api
    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất", self.out.text())
        if d:
            self.out.setText(d)

    def _refresh_preview(self):
        self.preview.set_style(self.binder.values())

    def values(self) -> dict:
        return self.binder.values()

    def set_values(self, d: dict):
        self.binder.set_values(d)
        self.out.setCursorPosition(0)
        self._refresh_preview()

    def set_presets(self, names: list[str]):
        cur = self.preset.currentText()
        self.preset.blockSignals(True)
        self.preset.clear()
        self.preset.addItems(names)
        i = self.preset.findText(cur)
        self.preset.setCurrentIndex(max(0, i))
        self.preset.blockSignals(False)
