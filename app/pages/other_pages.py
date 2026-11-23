"""Tab Công cụ video và Hỗ trợ."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from .. import icons
from ..theme import C
from ..widgets.common import Card, button, chip, dpr, label, toast

def _badge(icon_name: str, color: str, size: int = 40) -> QPixmap:
    r = dpr()
    S = int(size * r)
    pm = QPixmap(S, S)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    bg = QColor(color)
    bg.setAlpha(36)
    p.setPen(Qt.NoPen)
    p.setBrush(bg)
    p.drawRoundedRect(0, 0, S, S, S * 0.3, S * 0.3)
    ic = icons.pixmap(icon_name, color, int(size * 0.5))
    p.drawPixmap(int((S - ic.width()) / 2), int((S - ic.height()) / 2), ic)
    p.end()
    pm.setDevicePixelRatio(r)
    return pm


RATIOS = ["9:16 · TikTok / Shorts", "1:1 · Vuông", "16:9 · YouTube"]
BGS = ["Nền mờ", "Nền đen", "Phóng to lấp đầy"]


def _tools():
    from core import toolops
    return [
        ("music", C["green"], "Tách giọng & nhạc nền", "Tách lời nói và nhạc nền thành 2 file mp3 riêng bằng AI (Demucs).",
         [("file", "Video / âm thanh", "file:media", None)], toolops.separate_audio),
        ("scan", C["cyan"], "Trích phụ đề", "Lấy phụ đề gốc ra file SRT: đọc chữ cứng ở 1/5 dưới khung hình (OCR) "
         "hoặc nghe giọng nói (ASR). Muốn chọn vùng chữ khác, dùng tab Biên tập.",
         [("file", "Video", "file:video", None), ("mode", "Cách lấy", "combo", ["Giọng nói (ASR)", "Chữ trên hình (OCR)"])],
         toolops.extract_subs),
        ("languages", C["accent"], "Dịch file SRT", "Dịch một file phụ đề có sẵn bằng AI, theo kịch bản và AI dịch "
         "đang chọn ở tab Biên tập.", [("file", "File SRT", "file:srt", None)], toolops.translate_srt),
        ("mic", C["amber"], "Tạo giọng từ SRT", "Đọc file phụ đề thành 1 file mp3 khớp thời gian, dùng giọng / tốc độ / "
         "cao độ đang chọn ở tab Biên tập.", [("file", "File SRT", "file:srt", None)], toolops.voice_from_srt),
        ("captions", C["accent2"], "Ghép phụ đề cứng", "In file SRT vào video theo Kiểu phụ đề đang chỉnh ở tab Biên tập.",
         [("file", "Video", "file:video", None), ("srt", "File SRT", "file:srt", None)], toolops.burn_subs),
        ("maximize", C["red"], "Đổi khung hình", "Chuyển video sang khung dọc 9:16 / vuông 1:1 / ngang 16:9 cho từng nền tảng.",
         [("file", "Video", "file:video", None), ("ratio", "Khung", "combo", RATIOS), ("bg", "Nền", "combo", BGS),
          ("srt", "Phụ đề", "file:srt", "(tùy chọn) file SRT để in vào vùng trống")], toolops.to_vertical),
        ("zap", C["cyan"], "Nén & đổi định dạng", "Giảm dung lượng, đổi MP4 / MKV / WEBM; dùng Encoder đang chọn ở tab Biên tập.",
         [("file", "Video", "file:video", None), ("format", "Định dạng", "combo", ["MP4", "MKV", "WEBM"]),
          ("quality", "Chất lượng", "combo", ["Cân bằng", "Cao", "Nhanh"]),
          ("max_height", "Độ phân giải tối đa", "combo", ["Giữ nguyên", "1080p", "720p", "480p"])], toolops.compress),
        ("download", C["green"], "Tải video", "Tải video từ link về máy để biên tập (yt-dlp). "
         "Chỉ tải video bạn có quyền sử dụng.", [("url", "Link video", "url", "https://…")], toolops.download),
        ("wave", C["accent"], "Tìm giọng giống mẫu", "Đưa video có giọng bạn thích: app tách giọng, đo cao độ / tốc độ "
         "rồi cho từng giọng có sẵn đọc thử để tìm giọng + cao độ + tốc độ giống nhất.",
         [("file", "Video mẫu", "file:media", None), ("start", "Bắt đầu từ", "number", (0, 36000, 5, " giây")),
          ("length", "Độ dài đoạn mẫu", "number", (10, 120, 30, " giây"))], None),
    ]


def _voice_match(p, cfg, report, stop):
    from core import voicematch
    from core.log import log

    from ..paths import DATA
    wd = DATA / "tools" / "voicematch"
    voicematch.cleanup(wd)
    r = voicematch.match(p["file"], float(p.get("start", 0)), float(p.get("length", 30)), wd, cfg, report, stop)
    if not r:
        return {}
    best = r["results"][0]
    log(f"Giọng giống nhất: {best['voice']} · cao độ {best['pitch']:+d} Hz · tốc độ x{best['speed']}", "ok")
    msg = f"Giọng mẫu: cao độ {r['target']['f0']:.0f} Hz" + (
        f", {r['target']['rate']:.1f} âm tiết/giây" if r["target"].get("rate") else "")
    return {"files": [], "message": msg, "match": r}


class VoiceMatchResult(QFrame):
    def __init__(self, res: dict, apply_voice, parent=None):
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        super().__init__(parent)
        self.setObjectName("Card")
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(8)
        self.player, self.audio = QMediaPlayer(self), QAudioOutput(self)
        self.player.setAudioOutput(self.audio)

        def play(path):
            self.player.stop()
            self.player.setSource(QUrl())
            self.player.setSource(QUrl.fromLocalFile(path))
            self.player.play()

        top = QHBoxLayout()
        top.addWidget(label("Giọng mẫu (đã tách nhạc)", "Value"), 1)
        b = button("Nghe", "volume", "tool")
        b.clicked.connect(lambda: play(res["match"]["sample"]))
        top.addWidget(b)
        v.addLayout(top)
        for i, r in enumerate(res["match"]["results"]):
            row = QHBoxLayout()
            tag = chip("Giống nhất", "ok") if i == 0 else chip(f"#{i + 1}")
            row.addWidget(tag)
            row.addWidget(label(f"{r['voice'].split(' (')[0]}  ·  cao độ {r['pitch']:+d} Hz  ·  tốc độ x{r['speed']:.2f}"
                                f"   (đo được {r['f0']:.0f} Hz, độ lệch {r['score']})", "Muted"), 1)
            nb = button("Nghe", "volume", "tool")
            nb.clicked.connect(lambda _=False, s=r["sample"]: play(s))
            ab = button("Áp dụng", "check", "primary" if i == 0 else "tool")
            ab.clicked.connect(lambda _=False, r=r: (apply_voice(r["voice"], r["pitch"], r["speed"]),
                                                    toast(self, "Đã áp dụng giọng cho tab Biên tập", "ok")))
            row.addWidget(nb)
            row.addWidget(ab)
            v.addLayout(row)
        v.addWidget(label("Máy chỉ đo được cao độ, độ lên xuống và tốc độ, hãy nghe để so màu giọng.", "Dim", wrap=True))


class ToolCard(QFrame):
    def __init__(self, icon_name, color, title, desc, on_open):
        super().__init__()
        self.setObjectName("ToolCard")
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 18, 18, 16)
        v.setSpacing(10)
        b = QLabel()
        b.setPixmap(_badge(icon_name, color))
        v.addWidget(b)
        v.addWidget(label(title, "H2"))
        v.addWidget(label(desc, "Muted", wrap=True), 1)
        open_btn = button("Mở công cụ", "arrow-right", "tool")
        open_btn.clicked.connect(on_open)
        v.addWidget(open_btn, 0, Qt.AlignLeft)


class ToolsPage(QScrollArea):
    def __init__(self, get_cfg, apply_voice):
        super().__init__()
        self.get_cfg, self.apply_voice = get_cfg, apply_voice
        self.setWidgetResizable(True)
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 0, 8, 0)
        g.setSpacing(16)
        tools = _tools()
        for i, (ic, color, title, desc, fields, fn) in enumerate(tools):
            g.addWidget(ToolCard(ic, color, title, desc,
                                 lambda _=False, t=(ic, color, title, desc, fields, fn): self._open(*t)), i // 3, i % 3)
        g.setRowStretch(len(tools) // 3 + 1, 1)
        self.setWidget(w)

    def _open(self, ic, color, title, desc, fields, fn):
        from ..dialogs.tool_dialog import ToolDialog
        result = None
        if fn is None:                       # Tìm giọng giống mẫu
            fn = _voice_match
            result = lambda res, parent: VoiceMatchResult(res, self.apply_voice, parent) if res.get("match") else None
        ToolDialog(title, ic, color, desc, fields, fn, self.get_cfg, self, result).exec()


STEPS = [("captions", "Trích xuất", "OCR / ASR"), ("languages", "Dịch AI", "theo kịch bản"),
         ("music", "Tách nhạc", "Demucs"), ("mic", "Lồng tiếng", "Edge TTS"),
         ("wave", "Căn khớp", "co giãn audio"), ("film", "Render", "FFmpeg + NVENC")]

SHORTCUTS = [("Delete", "Xóa vùng đang chọn trên khung xem trước"),
             ("Nhấp đúp vào vùng Chữ", "Sửa nội dung watermark"),
             ("Nhấp đúp vào video", "Mở cửa sổ sửa phụ đề"),
             ("Space (trong Sửa phụ đề)", "Phát / tạm dừng"),
             ("Nhấp đúp vào câu", "Nhảy video tới câu đó"),
             ("Kéo thả file / thư mục", "Thêm video hàng loạt")]


class HelpPage(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 8, 0)
        v.setSpacing(16)

        flow = Card("Quy trình tự động", "sparkles", C["accent"])
        row = QHBoxLayout()
        row.setSpacing(8)
        for i, (ic, t, s) in enumerate(STEPS):
            col = QVBoxLayout()
            col.setSpacing(6)
            col.setAlignment(Qt.AlignHCenter)
            b = QLabel()
            b.setPixmap(_badge(ic, [C["accent"], C["cyan"], C["green"], C["amber"], C["accent2"], C["red"]][i], 48))
            b.setAlignment(Qt.AlignCenter)
            col.addWidget(b)
            n = label(f"{i + 1}. {t}", "Value")
            n.setAlignment(Qt.AlignCenter)
            col.addWidget(n)
            d = label(s, "Dim")
            d.setAlignment(Qt.AlignCenter)
            col.addWidget(d)
            row.addLayout(col, 1)
            if i < len(STEPS) - 1:
                a = QLabel()
                a.setPixmap(icons.pixmap("arrow-right", C["dim"], 18))
                row.addWidget(a)
        flow.add(row)
        v.addWidget(flow)

        h = QHBoxLayout()
        h.setSpacing(16)
        guide = Card("Hướng dẫn sử dụng", "book", C["cyan"])
        from PySide6.QtWidgets import QApplication, QTextBrowser

        from core.runtime import RES_DIR
        view = QTextBrowser()
        view.setOpenExternalLinks(True)
        view.setStyleSheet(f"QTextBrowser {{ background: transparent; border: none; color: {C['text']}; "
                           f"font-family: '{QApplication.font().family()}'; font-size: 13px; }}")
        try:
            md = (RES_DIR / "HUONG_DAN_SU_DUNG.md").read_text("utf-8")
            md = md.split("\n", 1)[1] if md.startswith("# ") else md      # bỏ tiêu đề lớn (đã có tên card)
        except OSError:
            md = "Không tìm thấy file HUONG_DAN_SU_DUNG.md."
        view.setMarkdown(md)
        view.setMinimumHeight(520)
        guide.add(view, 1)
        h.addWidget(guide, 2)

        about = Card("Về ứng dụng", "help", C["muted"])
        about.add(label("DubStudio", "H2"))
        about.add(label("Dịch & lồng tiếng video Trung → Việt bằng AI.", "Muted", wrap=True))
        from core.version import VERSION
        about.add(label(f"Phiên bản {VERSION}. Trích phụ đề (OCR / nhận giọng nói), dịch bằng Gemini hoặc Ollama, "
                        "tách nhạc nền (Demucs), lồng tiếng (Edge TTS), căn khớp thời gian và xuất video (FFmpeg).",
                        "Dim", wrap=True))
        from core.runtime import FROZEN
        from ..paths import DATA
        about.add(label(f"Dữ liệu (cấu hình, project, model AI): {DATA}" + (" · bản cài đặt" if FROZEN else ""),
                        "Dim", wrap=True))
        about.add(label("Phím tắt", "Value"))
        g = QGridLayout()
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(8)
        for i, (k, d) in enumerate(SHORTCUTS):
            g.addWidget(chip(k, "info"), i, 0, Qt.AlignLeft)
            g.addWidget(label(d, "Muted", wrap=True), i, 1)
        g.setColumnStretch(1, 1)
        about.add(g)
        about.body.addStretch()
        h.addWidget(about, 1)
        v.addLayout(h, 1)
        v.addStretch()
        self.setWidget(w)
