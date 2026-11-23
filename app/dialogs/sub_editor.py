"""Cửa sổ sửa phụ đề: xem video kèm sub, bảng câu, tìm/thay, sửa thời gian & nội dung."""
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QUrl
from PySide6.QtGui import QColor
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPlainTextEdit, QSlider,
                               QSplitter, QTableView, QVBoxLayout)

from core.project import Job
from core.srt import Cue, ms_to_tc, parse_srt, tc_to_ms, write_srt

from .. import icons
from ..theme import C
from ..widgets.common import Card, button, chip, combo, dark_titlebar, field_label, label, toast

# Dữ liệu mẫu để xem giao diện khi chưa chạy bước trích xuất/dịch
DEMO = [
    ("从前，在一个偏远的小山村里", "Ngày xửa ngày xưa, ở một ngôi làng nhỏ hẻo lánh"),
    ("住着一个名叫小林的少年", "có một chàng thiếu niên tên là Tiểu Lâm"),
    ("他每天都上山砍柴", "Ngày nào cậu cũng lên núi đốn củi"),
    ("有一天，他在山洞里发现了一本古书", "Một hôm, cậu tìm thấy một cuốn sách cổ trong hang núi"),
    ("书上写着：有缘人得之", "Trên sách ghi: người hữu duyên sẽ có được nó"),
    ("从那天起，他的命运彻底改变了", "Từ ngày đó, vận mệnh của cậu hoàn toàn thay đổi"),
    ("师父说：修行之路，贵在坚持", "Sư phụ nói: con đường tu hành, quý ở sự kiên trì"),
    ("三年后，他终于下山了", "Ba năm sau, cuối cùng cậu cũng xuống núi"),
]


def demo_cues() -> list[Cue]:
    return [Cue(1000 + i * 2600, 1000 + i * 2600 + 2300, zh, vi) for i, (zh, vi) in enumerate(DEMO)]


class CueModel(QAbstractTableModel):
    HEAD = ["#", "Bắt đầu", "Kết thúc", "Câu gốc", "Bản dịch", "Giọng"]

    def __init__(self, cues: list[Cue]):
        super().__init__()
        self.cues = cues
        self.voice: dict[int, dict] = {}   # index tts/index.json theo số thứ tự câu

    def _voice_cell(self, r: int, c: Cue):
        e = self.voice.get(r)
        if not c.dst.strip():
            return "", None
        if not e or e.get("text") != c.dst.strip() or not e.get("dur"):
            return "chưa đọc", C["dim"]
        # Khung thực tế bước Căn khớp được dùng: tới lúc câu kế tiếp bắt đầu (mượn khoảng lặng phía sau)
        nxt = self.cues[r + 1].start if r + 1 < len(self.cues) else c.end + 1000
        avail = max(0.1, (nxt - c.start) / 1000 - 0.05)
        need = e["dur"] / avail
        if need <= 1.0:
            return f"{e['dur']:.1f}s ✓", C["green"]
        if need <= 1.35:
            return f"{e['dur']:.1f}s · tăng tốc x{need:.2f}", C["amber"]
        return f"{e['dur']:.1f}s · tràn {e['dur'] / 1.35 - avail:.1f}s", C["red"]

    def rowCount(self, parent=QModelIndex()):
        return len(self.cues)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEAD)

    def data(self, idx, role=Qt.DisplayRole):
        c = self.cues[idx.row()]
        col = idx.column()
        if col == 5:
            text, color = self._voice_cell(idx.row(), c)
            if role == Qt.DisplayRole:
                return text
            if role == Qt.ForegroundRole and color:
                return QColor(color)
            if role == Qt.TextAlignmentRole:
                return int(Qt.AlignCenter)
            if role == Qt.ToolTipRole and color in (C["red"], C["amber"]):
                return ("Vàng: bước Căn khớp sẽ tự đọc nhanh hơn cho vừa.\n"
                        "Đỏ: tăng tốc tối đa x1.35 vẫn không vừa → nên rút gọn bản dịch hoặc bấm Dịch lại")
            return None
        if role == Qt.DisplayRole:
            return [str(idx.row() + 1), ms_to_tc(c.start), ms_to_tc(c.end), c.src, c.dst][col]
        if role == Qt.TextAlignmentRole and col < 3:
            return int(Qt.AlignCenter)
        if role == Qt.ForegroundRole:
            if col == 0:
                return QColor(C["dim"])
            if col in (1, 2, 3):
                return QColor(C["muted"])
        return None

    def headerData(self, s, o, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and o == Qt.Horizontal:
            return self.HEAD[s]
        return None

    def reset(self, cues=None):
        self.beginResetModel()
        if cues is not None:
            self.cues = cues
        self.endResetModel()

    def refresh_row(self, r: int):
        self.dataChanged.emit(self.index(r, 0), self.index(r, self.columnCount() - 1))


class SubEditorDialog(QDialog):
    def __init__(self, job: Job, parent=None, cfg: dict | None = None):
        super().__init__(parent)
        self.job = job
        self.cfg = cfg or {}
        self.setWindowTitle(f"Sửa phụ đề — {job.name}")
        self.resize(1240, 940)
        self.setMinimumSize(980, 700)
        self.srt_vi = job.workdir / "sub_vi.srt"
        self.srt_zh = job.workdir / "sub_zh.srt"
        self._cur_cue = -1
        self._undo: list = []
        self._redo: list = []
        self._dirty = False
        self.cues = self._load()
        self.model = CueModel(self.cues)
        from core import tts
        self.model.voice = tts.load_index(job.workdir)
        self.voice_player = QMediaPlayer(self)
        self.voice_out = QAudioOutput(self)
        self.voice_player.setAudioOutput(self.voice_out)
        self.voice_player.errorOccurred.connect(
            lambda _e, msg: toast(self, f"Không phát được âm thanh: {msg or 'lỗi thiết bị âm thanh'}", "err"))

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 18)
        root.setSpacing(12)
        root.addLayout(self._header())
        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        split.addWidget(self._player())
        split.addWidget(self._editor())
        split.setSizes([330, 600])
        root.addWidget(split, 1)
        if self.cues:
            self.table.selectRow(0)
        from PySide6.QtGui import QKeySequence, QShortcut
        for seq, fn in ((QKeySequence.Undo, self.undo), ("Ctrl+Y", self.redo), (QKeySequence.Redo, self.redo),
                        (QKeySequence.Save, lambda: self._save())):
            QShortcut(QKeySequence(seq), self, activated=fn)
        self._sync_undo_btns()

    # ---------------------------------------------------------------- data
    def _load(self) -> list[Cue]:
        if self.srt_vi.exists():
            vi = parse_srt(self.srt_vi.read_text(encoding="utf-8"))
            if self.srt_zh.exists():
                zh = parse_srt(self.srt_zh.read_text(encoding="utf-8"))
                for a, b in zip(vi, zh):
                    a.src = b.dst
            self._demo = False
            return vi
        if self.srt_zh.exists():
            # mới trích xuất xong, chưa dịch: hiện câu gốc, bản dịch để trống
            self._demo = False
            return [Cue(c.start, c.end, c.dst, "") for c in parse_srt(self.srt_zh.read_text(encoding="utf-8"))]
        self._demo = True
        return demo_cues()

    # ---------------------------------------------------------------- UI
    def _header(self):
        h = QHBoxLayout()
        h.setSpacing(10)
        ic = QLabel()
        ic.setPixmap(icons.pixmap("captions", C["accent"], 22))
        h.addWidget(ic)
        t = label("Sửa phụ đề", "H2")
        h.addWidget(t)
        self.count = chip(f"{len(self.cues)} câu", "info")
        h.addWidget(self.count)
        if self._demo:
            h.addWidget(chip("Dữ liệu mẫu, chưa chạy trích xuất", "warn"))
        h.addStretch()
        open_btn = button("Mở SRT…", "folder")
        open_btn.clicked.connect(self._open_srt)
        save_btn = button("Lưu SRT", "save", "primary")
        save_btn.clicked.connect(lambda: self._save())
        self.btn_tr_empty = button("Dịch câu trống", "sparkles", "tool", "Chỉ dịch những câu chưa có bản dịch")
        self.btn_tr_empty.clicked.connect(lambda: self._translate_many(only_empty=True))
        self.btn_tr_all = button("Dịch lại tất cả", "refresh", "tool",
                                 "Dịch lại toàn bộ theo kịch bản đang chọn (ghi đè cả câu đã sửa tay)")
        self.btn_tr_all.clicked.connect(lambda: self._translate_many(only_empty=False))
        self.btn_undo = button("", "undo", "tool", "Hoàn tác (Ctrl+Z)")
        self.btn_undo.clicked.connect(self.undo)
        self.btn_redo = button("", "redo", "tool", "Làm lại (Ctrl+Y)")
        self.btn_redo.clicked.connect(self.redo)
        h.addWidget(self.btn_undo)
        h.addWidget(self.btn_redo)
        h.addSpacing(8)
        h.addWidget(self.btn_tr_empty)
        h.addWidget(self.btn_tr_all)
        h.addSpacing(8)
        h.addWidget(open_btn)
        h.addWidget(save_btn)
        return h

    def _translate_many(self, only_empty: bool):
        from PySide6.QtWidgets import QMessageBox

        from core import presets, translate
        from core.tasks import run_async
        idx = [i for i, c in enumerate(self.cues) if c.src.strip() and (not only_empty or not c.dst.strip())]
        if not idx:
            toast(self, "Không có câu nào cần dịch" if only_empty else "Chưa có câu gốc để dịch", "warn")
            return
        if not only_empty and QMessageBox.question(
                self, "Dịch lại tất cả", f"Dịch lại {len(idx)} câu theo kịch bản “{self.cfg.get('preset', 'Mặc định')}”?\n"
                "Các câu đã sửa tay sẽ bị ghi đè.") != QMessageBox.Yes:
            return
        items = presets.load()
        preset = next((p for p in items if p["name"] == self.cfg.get("preset")), items[0])
        srcs = [self.cues[i].src for i in idx]
        secs = [(self.cues[i].end - self.cues[i].start) / 1000 for i in idx]
        for b in (self.btn_tr_empty, self.btn_tr_all):
            b.setEnabled(False)
        toast(self, f"Đang dịch {len(idx)} câu…", "info")

        def done(vis: list):
            r = self._row()                                # nhớ dòng đang chọn trước khi làm mới bảng
            self._snapshot()
            for i, v in zip(idx, vis):
                if v:
                    self.cues[i].dst = v
            self.model.reset()
            self._cur_cue = -2
            if 0 <= r < len(self.cues):
                self.table.selectRow(r)                    # chọn lại → ô Bản dịch hiện nội dung mới
                self.ed_dst.setPlainText(self.cues[r].dst)
            for b in (self.btn_tr_empty, self.btn_tr_all):
                b.setEnabled(True)
            self._save(silent=True)                        # dịch tốn công → lưu luôn
            toast(self, f"Đã dịch {sum(1 for v in vis if v)} câu và lưu phụ đề", "ok")

        def failed(err: str):
            for b in (self.btn_tr_empty, self.btn_tr_all):
                b.setEnabled(True)
            toast(self, f"Dịch lỗi: {err}", "err")

        run_async(translate.translate_all, srcs, preset, self.cfg, lambda p: None, lambda: False, 40, 6, secs,
                  on_done=done, on_error=failed)

    def _player(self):
        c = Card(padding=12)
        panel = QFrame()
        panel.setObjectName("VideoPanel")
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(0, 0, 0, 10)
        pv.setSpacing(4)
        self.video = QVideoWidget()
        self.video.setMinimumHeight(120)
        self.video.setStyleSheet("background: #000;")
        pv.addWidget(self.video, 1)
        self.vi_lbl = QLabel(" ")
        self.vi_lbl.setAlignment(Qt.AlignCenter)
        self.vi_lbl.setWordWrap(True)
        self.vi_lbl.setStyleSheet("color: #FFE14D; font-size: 20px; font-weight: 700; background: transparent;")
        self.zh_lbl = QLabel(" ")
        self.zh_lbl.setAlignment(Qt.AlignCenter)
        self.zh_lbl.setStyleSheet("color: #E8EAF1; font-size: 14px; background: transparent;")
        pv.addWidget(self.vi_lbl)
        pv.addWidget(self.zh_lbl)
        c.add(panel, 1)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        if Path(self.job.path).exists():
            self.player.setSource(QUrl.fromLocalFile(self.job.path))
        self.player.positionChanged.connect(self._on_pos)
        self.player.durationChanged.connect(lambda d: self.seek.setRange(0, d))
        self.player.playbackStateChanged.connect(self._on_state)

        ctl = QHBoxLayout()
        ctl.setSpacing(8)
        back = button("", "rewind", "tool", "Lùi 5 giây")
        back.clicked.connect(lambda: self.player.setPosition(max(0, self.player.position() - 5000)))
        self.play_btn = button("", "play", "primary", "Phát / tạm dừng (Space)")
        self.play_btn.setFixedWidth(44)
        self.play_btn.clicked.connect(self._toggle_play)
        fwd = button("", "forward", "tool", "Tới 5 giây")
        fwd.clicked.connect(lambda: self.player.setPosition(self.player.position() + 5000))
        self.seek = QSlider(Qt.Horizontal)
        self.seek.setCursor(Qt.PointingHandCursor)
        self.seek.sliderMoved.connect(self.player.setPosition)
        self.time_lbl = label("00:00:00,000", "Mono")
        speed = combo(["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"], "1.0x")
        speed.setFixedWidth(84)
        speed.currentTextChanged.connect(lambda t: self.player.setPlaybackRate(float(t[:-1])))
        vol_ic = QLabel()
        vol_ic.setPixmap(icons.pixmap("volume", C["muted"], 16))
        vol = QSlider(Qt.Horizontal)
        vol.setRange(0, 100)
        vol.setValue(80)
        vol.setFixedWidth(90)
        vol.valueChanged.connect(lambda v: self.audio.setVolume(v / 100))
        self.audio.setVolume(0.8)
        for w in (back, self.play_btn, fwd):
            ctl.addWidget(w)
        ctl.addWidget(self.seek, 1)
        ctl.addWidget(self.time_lbl)
        ctl.addWidget(speed)
        ctl.addWidget(vol_ic)
        ctl.addWidget(vol)
        c.add(ctl)

        # dòng thời gian: sóng âm + khối câu kéo thả
        from ..widgets.timeline import Timeline, waveform_peaks
        self.timeline = Timeline()
        self.timeline.set_cues(self.cues)
        self.timeline.setToolTip("Kéo khối để dời câu · kéo mép để chỉnh bắt đầu / kết thúc · "
                                 "bấm chỗ trống để tua · lăn chuột: cuộn · Ctrl + lăn: phóng to / thu nhỏ")
        self.timeline.seek.connect(self.player.setPosition)
        self.timeline.cueSelected.connect(self.table_select)
        self.timeline.editStarted.connect(self._snapshot)
        self.timeline.cueChanged.connect(self._timeline_changed)
        self.player.durationChanged.connect(self.timeline.set_duration)
        c.add(self.timeline)
        if Path(self.job.path).exists():
            from core.tasks import run_async
            run_async(waveform_peaks, self.job.path, on_done=self.timeline.set_peaks)
        return c

    def table_select(self, i: int):
        if 0 <= i < len(self.cues):
            self.table.selectRow(i)

    def _timeline_changed(self, i: int):
        self.model.refresh_row(i)
        if self._row() == i:
            self.ed_start.setText(ms_to_tc(self.cues[i].start))
            self.ed_end.setText(ms_to_tc(self.cues[i].end))
        self._cur_cue = -2
        self._dirty = True

    # ---------------------------------------------------------------- hoàn tác / làm lại
    def _state(self):
        return [(c.start, c.end, c.src, c.dst) for c in self.cues]

    def _snapshot(self):
        """Lưu trạng thái TRƯỚC mỗi thay đổi (để Ctrl+Z quay lại)."""
        self._undo.append(self._state())
        del self._undo[:-100]
        self._redo.clear()
        self._dirty = True
        self._sync_undo_btns()

    def _restore(self, st):
        r = self._row()
        self.cues[:] = [Cue(*t) for t in st]                # giữ nguyên danh sách (bảng + dòng thời gian dùng chung)
        self.model.reset()
        self.count.setText(f"{len(self.cues)} câu")
        self._cur_cue = -2
        if self.cues:
            self.table.selectRow(max(0, min(r, len(self.cues) - 1)))
        self.timeline.update()
        self._sync_undo_btns()

    def undo(self):
        if not self._undo:
            toast(self, "Không còn gì để hoàn tác", "info")
            return
        self._redo.append(self._state())
        self._restore(self._undo.pop())

    def redo(self):
        if not self._redo:
            toast(self, "Không còn gì để làm lại", "info")
            return
        self._undo.append(self._state())
        self._restore(self._redo.pop())

    def _sync_undo_btns(self):
        if hasattr(self, "btn_undo"):
            self.btn_undo.setEnabled(bool(self._undo))
            self.btn_redo.setEnabled(bool(self._redo))

    # ---------------------------------------------------------------- gộp / tách câu
    def _merge_next(self):
        r = self._row()
        if r < 0 or r + 1 >= len(self.cues):
            toast(self, "Chọn một câu có câu kế tiếp để gộp", "warn")
            return
        self._snapshot()
        a, b = self.cues[r], self.cues.pop(r + 1)
        cjk = lambda s: any("一" <= ch <= "鿿" for ch in s)
        a.end = b.end
        a.src = (a.src + ("" if cjk(a.src) and cjk(b.src) else " ") + b.src).strip()
        a.dst = f"{a.dst} {b.dst}".strip()
        self.model.reset()
        self.count.setText(f"{len(self.cues)} câu")
        self.table.selectRow(r)
        self.timeline.update()
        toast(self, f"Đã gộp câu #{r + 1} với câu sau", "ok")

    def _split(self):
        r = self._row()
        if r < 0:
            return
        c = self.cues[r]
        if c.end - c.start < 400:
            toast(self, "Câu quá ngắn để tách", "warn")
            return
        pos = self.player.position()
        t = pos if c.start + 200 < pos < c.end - 200 else (c.start + c.end) // 2   # tách tại đầu phát nếu nằm trong câu
        text = self.ed_dst.toPlainText().strip() or c.dst
        cur = self.ed_dst.textCursor().position()
        if 0 < cur < len(text):
            k = cur                                                 # tách tại con trỏ trong ô Bản dịch
        else:
            spaces = [i for i, ch in enumerate(text) if ch == " "]
            k = min(spaces, key=lambda i: abs(i - len(text) / 2)) if spaces else len(text) // 2
        frac = (t - c.start) / (c.end - c.start)
        ks = int(round(len(c.src) * frac))
        self._snapshot()
        new = Cue(t, c.end, c.src[ks:].strip(), text[k:].strip())
        c.end, c.src, c.dst = t, c.src[:ks].strip(), text[:k].strip()
        self.cues.insert(r + 1, new)
        self.model.reset()
        self.count.setText(f"{len(self.cues)} câu")
        self.table.selectRow(r)
        self.timeline.update()
        toast(self, f"Đã tách câu #{r + 1} tại {ms_to_tc(t)}", "ok")

    def _editor(self):
        c = Card(padding=12)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.find = QLineEdit()
        self.find.setPlaceholderText("Tìm trong phụ đề… (Enter để tìm tiếp)")
        self.find.addAction(icons.icon("search", C["muted"], 16), QLineEdit.LeadingPosition)
        self.find.returnPressed.connect(self._find_next)
        self.repl = QLineEdit()
        self.repl.setPlaceholderText("Thay bằng…")
        rep_btn = button("Thay tất cả", "refresh")
        rep_btn.clicked.connect(self._replace_all)
        bar.addWidget(self.find, 2)
        bar.addWidget(self.repl, 1)
        bar.addWidget(rep_btn)
        c.add(bar)

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(32)
        hh = self.table.horizontalHeader()
        hh.setHighlightSections(False)
        for i, w in enumerate([46, 112, 112]):
            hh.setSectionResizeMode(i, QHeaderView.Fixed)
            self.table.setColumnWidth(i, w)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.Stretch)
        hh.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 190)
        self.table.selectionModel().currentRowChanged.connect(self._row_changed)
        self.table.doubleClicked.connect(lambda i: self.player.setPosition(self.cues[i.row()].start))
        c.add(self.table, 1)

        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(8)
        self.ed_start = QLineEdit()
        self.ed_end = QLineEdit()
        for e in (self.ed_start, self.ed_end):
            e.setFixedWidth(130)
            e.setAlignment(Qt.AlignCenter)
        self.ed_src = QLineEdit()
        self.ed_src.setReadOnly(True)
        self.ed_dst = QPlainTextEdit()
        self.ed_dst.setFixedHeight(56)
        g.addWidget(field_label("Bắt đầu"), 0, 0)
        g.addWidget(self.ed_start, 0, 1)
        g.addWidget(field_label("Kết thúc"), 0, 2)
        g.addWidget(self.ed_end, 0, 3)
        g.addWidget(field_label("Câu gốc"), 0, 4)
        g.addWidget(self.ed_src, 0, 5)
        g.addWidget(field_label("Bản dịch"), 1, 0, Qt.AlignTop)
        g.addWidget(self.ed_dst, 1, 1, 1, 5)
        g.setColumnStretch(5, 1)
        btns = QVBoxLayout()
        btns.setSpacing(6)
        apply = button("Áp dụng", "check", "primary")
        apply.clicked.connect(self._apply)
        self.btn_ai = button("Dịch lại", "sparkles", None, "Nhờ AI dịch lại câu này (có ngữ cảnh các câu trước)")
        self.btn_ai.clicked.connect(self._retranslate)
        self.btn_voice = button("Nghe", "volume", None, "Đọc câu này bằng giọng đang chọn (câu đã sửa sẽ đọc lại)")
        self.btn_voice.clicked.connect(self._speak)
        add = button("Thêm dòng", "plus")
        add.clicked.connect(self._add_row)
        rm = button("Xóa dòng", "trash", "danger")
        rm.clicked.connect(self._del_row)
        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(apply, 1)
        top.addWidget(self.btn_voice)
        btns.addLayout(top)
        btns.addWidget(self.btn_ai)
        low = QHBoxLayout()
        low.setSpacing(6)
        low.addWidget(add)
        low.addWidget(rm)
        btns.addLayout(low)
        mg = button("Gộp câu sau", "merge", None, "Gộp câu đang chọn với câu kế tiếp")
        mg.clicked.connect(self._merge_next)
        sp = button("Tách câu", "split", None, "Tách tại đầu phát (nếu nằm trong câu) và tại con trỏ trong ô Bản dịch")
        sp.clicked.connect(self._split)
        ms_row = QHBoxLayout()
        ms_row.setSpacing(6)
        ms_row.addWidget(mg)
        ms_row.addWidget(sp)
        btns.addLayout(ms_row)
        g.addLayout(btns, 0, 6, 2, 1)
        c.add(g)
        return c

    # ---------------------------------------------------------------- player
    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_state(self, st):
        playing = st == QMediaPlayer.PlayingState
        self.play_btn.setIcon(icons.icon("pause" if playing else "play", "#FFFFFF", 16))

    def _on_pos(self, ms: int):
        if not self.seek.isSliderDown():
            self.seek.setValue(ms)
        self.time_lbl.setText(ms_to_tc(ms))
        self.timeline.set_position(ms, follow=self.player.playbackState() == QMediaPlayer.PlayingState)
        idx = next((i for i, c in enumerate(self.cues) if c.start <= ms <= c.end), -1)
        if idx != self._cur_cue:
            self._cur_cue = idx
            cue = self.cues[idx] if idx >= 0 else None
            self.vi_lbl.setText(cue.dst if cue else " ")
            self.zh_lbl.setText(cue.src if cue else " ")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space and not isinstance(self.focusWidget(), (QLineEdit, QPlainTextEdit)):
            self._toggle_play()
            return
        super().keyPressEvent(e)

    # ---------------------------------------------------------------- edit
    def _row(self) -> int:
        return self.table.currentIndex().row()

    def _row_changed(self, cur, _prev):
        r = cur.row()
        if hasattr(self, "timeline"):
            self.timeline.set_selected(r)
        if 0 <= r < len(self.cues):
            c = self.cues[r]
            self.ed_start.setText(ms_to_tc(c.start))
            self.ed_end.setText(ms_to_tc(c.end))
            self.ed_src.setText(c.src)
            self.ed_dst.setPlainText(c.dst)

    def _apply(self):
        r = self._row()
        if r < 0:
            return
        try:
            s, e = tc_to_ms(self.ed_start.text()), tc_to_ms(self.ed_end.text())
        except ValueError as ex:
            toast(self, str(ex), "err")
            return
        if e <= s:
            toast(self, "Thời gian kết thúc phải lớn hơn bắt đầu", "err")
            return
        c = self.cues[r]
        new = (s, e, self.ed_dst.toPlainText().strip())
        if (c.start, c.end, c.dst) == new:
            return
        self._snapshot()
        c.start, c.end, c.dst = new
        self.model.refresh_row(r)
        self.timeline.update()
        self._cur_cue = -2
        toast(self, f"Đã cập nhật câu #{r + 1}", "ok")

    def _speak(self):
        r = self._row()
        if r < 0:
            return
        # lấy luôn nội dung đang gõ trong ô Bản dịch (kể cả chưa bấm Áp dụng)
        cur = self.cues[r]
        typed = self.ed_dst.toPlainText().strip()
        cue = Cue(cur.start, cur.end, cur.src, typed or cur.dst)
        if not cue.dst:
            toast(self, "Câu này chưa có bản dịch để đọc", "warn")
            return
        from core import tts
        from core.tasks import run_async
        self.btn_voice.setEnabled(False)

        def done(e: dict, row=r):
            self.btn_voice.setEnabled(True)
            self.model.voice[row] = e
            self.model.refresh_row(row)
            self.voice_player.stop()
            self.voice_player.setSource(QUrl())     # ép nạp lại file (cùng tên nhưng nội dung mới)
            self.voice_player.setSource(QUrl.fromLocalFile(e["path"]))
            self.voice_player.play()
            text, color = self.model._voice_cell(row, self.cues[row])
            if color == C["red"]:
                toast(self, f"Câu #{row + 1}: {text}, nên rút gọn bản dịch", "warn")

        def failed(err: str):
            self.btn_voice.setEnabled(True)
            toast(self, f"Không đọc được: {err}", "err")

        toast(self, f"Đang đọc câu #{r + 1}…", "info")
        run_async(tts.synth_line, self.job.workdir, r, cue, self.cfg.get("voice", ""),
                  float(self.cfg.get("speed", 1.0)), float(self.cfg.get("pitch", 0)),
                  on_done=done, on_error=failed)

    def _retranslate(self):
        r = self._row()
        if r < 0 or not self.cues[r].src.strip():
            toast(self, "Câu này chưa có câu gốc để dịch", "warn")
            return
        from core import presets, translate
        from core.tasks import run_async
        items = presets.load()
        preset = next((p for p in items if p["name"] == self.cfg.get("preset")), items[0])
        srcs = [c.src for c in self.cues]
        dsts = [c.dst for c in self.cues]
        self.btn_ai.setEnabled(False)
        self.btn_ai.setText("Đang dịch…")

        def done(text: str, row=r):
            self.btn_ai.setEnabled(True)
            self.btn_ai.setText("Dịch lại")
            self._snapshot()
            self.cues[row].dst = text
            self.model.refresh_row(row)
            if self._row() == row:
                self.ed_dst.setPlainText(text)
            self._cur_cue = -2
            toast(self, f"Đã dịch lại câu #{row + 1}", "ok")

        def failed(err: str):
            self.btn_ai.setEnabled(True)
            self.btn_ai.setText("Dịch lại")
            toast(self, err, "err")

        sec = (self.cues[r].end - self.cues[r].start) / 1000
        run_async(translate.translate_one, srcs, dsts, r, preset, self.cfg, sec, on_done=done, on_error=failed)

    def _add_row(self):
        r = self._row()
        prev = self.cues[r] if r >= 0 else None
        start = prev.end + 100 if prev else 0
        self._snapshot()
        self.cues.insert(r + 1, Cue(start, start + 2000, "", ""))
        self.model.reset()
        self.table.selectRow(r + 1)
        self.count.setText(f"{len(self.cues)} câu")
        self.timeline.update()
        self.ed_dst.setFocus()

    def _del_row(self):
        r = self._row()
        if r < 0:
            return
        self._snapshot()
        self.cues.pop(r)
        self.model.reset()
        if self.cues:
            self.table.selectRow(min(r, len(self.cues) - 1))
        self.count.setText(f"{len(self.cues)} câu")
        self.timeline.update()

    def _find_next(self):
        q = self.find.text().strip().lower()
        if not q:
            return
        n = len(self.cues)
        start = self._row()
        for k in range(1, n + 1):
            i = (start + k) % n
            if q in self.cues[i].dst.lower() or q in self.cues[i].src.lower():
                self.table.selectRow(i)
                self.table.scrollTo(self.model.index(i, 0))
                return
        toast(self, "Không tìm thấy", "warn")

    def _replace_all(self):
        q, rep = self.find.text(), self.repl.text()
        if not q:
            return
        if not any(q in c.dst for c in self.cues):
            toast(self, "Không có chỗ nào để thay", "warn")
            return
        self._snapshot()
        n = 0
        for c in self.cues:
            if q in c.dst:
                n += c.dst.count(q)
                c.dst = c.dst.replace(q, rep)
        self.model.reset()
        self.timeline.update()
        toast(self, f"Đã thay {n} chỗ", "ok" if n else "warn")

    def _open_srt(self):
        f, _ = QFileDialog.getOpenFileName(self, "Mở phụ đề", "", "SubRip (*.srt)")
        if not f:
            return
        try:
            cues = parse_srt(Path(f).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as ex:
            toast(self, f"Không đọc được file: {ex}", "err")
            return
        self._snapshot()
        self.cues[:] = cues
        self.model.reset()
        self.timeline.update()
        self.count.setText(f"{len(cues)} câu")
        if cues:
            self.table.selectRow(0)

    def _save(self, silent: bool = False):
        self.srt_vi.write_text(write_srt(self.cues, "dst"), encoding="utf-8")
        self.srt_zh.write_text(write_srt(self.cues, "src"), encoding="utf-8")
        self._dirty = False
        if not silent:
            toast(self, "Đã lưu phụ đề", "ok")

    # ---------------------------------------------------------------- lifecycle
    def showEvent(self, e):
        super().showEvent(e)
        dark_titlebar(self)

    def done(self, r):
        if self._dirty:
            from PySide6.QtWidgets import QMessageBox
            ans = QMessageBox.question(self, "Chưa lưu", "Phụ đề có thay đổi chưa lưu. Lưu trước khi đóng?",
                                       QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if ans == QMessageBox.Cancel:
                return
            if ans == QMessageBox.Save:
                self._save(silent=True)
        self.player.stop()
        self.voice_player.stop()
        super().done(r)
