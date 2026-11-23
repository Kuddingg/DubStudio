"""Tab chính: thêm video, cấu hình, chọn vùng trên khung hình, chạy pipeline."""
import json
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QSlider, QSplitter, QStackedWidget,
                               QVBoxLayout, QWidget)

from core import media
from core.log import log
from core.pipeline import PipelineWorker
from core.project import Job
from core.tasks import run_async

from ..paths import DATA
from ..theme import C

JOBS_FILE = DATA / "jobs.json"
from ..widgets.canvas import VideoCanvas
from ..widgets.common import Card, button, chip, label, set_chip, toast
from .config_panel import ConfigPanel
from .job_list import DropZone, JobList, JobRow

VIDEO_EXT = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".m4v", ".ts"}


class EditorPage(QWidget):
    statusChanged = Signal(str, str)   # text, tone
    configChanged = Signal()

    def __init__(self, preset_names: list[str], get_system):
        super().__init__()
        self.get_system = get_system
        self.jobs: dict[str, Job] = {}
        self.rows: dict[str, JobRow] = {}
        self.current: Job | None = None
        self.worker: PipelineWorker | None = None
        self._done = 0
        self.setAcceptDrops(True)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)
        self.config = ConfigPanel(preset_names)
        self.config.changed.connect(self.configChanged)
        root.addWidget(self.config)

        center = QVBoxLayout()
        center.setSpacing(12)
        root.addLayout(center, 1)
        center.addWidget(self._toolbar())

        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        split.addWidget(self._list_card())
        split.addWidget(self._preview_card())
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 5)
        split.setSizes([250, 560])
        center.addWidget(split, 1)
        self._jobs_timer = QTimer(self, singleShot=True, interval=800, timeout=self.save_jobs)
        self._update_counts()
        self.restore_jobs()

    # ================================================================= UI
    def _toolbar(self):
        c = Card(padding=12)
        c.body.setContentsMargins(12, 10, 12, 10)
        h = QHBoxLayout()
        h.setSpacing(8)
        add = button("Thêm video", "plus", "primary")
        add.clicked.connect(self.browse)
        folder = button("Thư mục", "folder", None, "Thêm toàn bộ video trong một thư mục")
        folder.clicked.connect(self.browse_folder)
        h.addWidget(add)
        h.addWidget(folder)
        h.addStretch()
        open_out = button("Kết quả", "folder", "ghost", "Mở thư mục chứa video đã render")
        open_out.clicked.connect(self.open_output_dir)
        h.addWidget(open_out)
        self.btn_stop = button("Dừng", "stop", "danger")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_start = button("Bắt đầu", "play", "primary")
        self.btn_start.setMinimumWidth(120)
        self.btn_start.clicked.connect(self.start)
        h.addWidget(self.btn_stop)
        h.addWidget(self.btn_start)
        c.add(h)
        return c

    def _list_card(self):
        c = Card("Danh sách video", "film", C["accent"])
        self.count_chip = chip("0 video")
        c.header.addWidget(self.count_chip)
        c.header.addSpacing(6)
        self.summary = label("", "Dim")
        c.header.addWidget(self.summary)
        for ic, tip, fn in [("check", "Chọn tất cả", lambda: self._check_all(True)),
                            ("x", "Bỏ chọn tất cả", lambda: self._check_all(False))]:
            b = button("", ic, "ghost", tip, icon_size=14)
            b.setFixedSize(30, 28)
            b.setStyleSheet("padding: 0;")
            b.clicked.connect(fn)
            c.header.addWidget(b)
        self.btn_remove = button("", "trash", "ghost", "Xóa các video đang được tick", icon_color=C["red"], icon_size=14)
        self.btn_remove.setFixedSize(30, 28)
        self.btn_remove.setStyleSheet("padding: 0;")
        self.btn_remove.clicked.connect(self.remove_checked)
        c.header.addWidget(self.btn_remove)
        self.list_stack = QStackedWidget()
        drop = DropZone()
        drop.browse.connect(self.browse)
        self.joblist = JobList()
        self.list_stack.addWidget(drop)
        self.list_stack.addWidget(self.joblist)
        c.add(self.list_stack, 1)
        return c

    def _preview_card(self):
        c = Card("Xem trước & vùng xử lý", "scan", C["cyan"])
        self.preview_name = label("", "Dim")
        c.header.addWidget(self.preview_name)
        self.canvas = VideoCanvas()
        self.canvas.regionsChanged.connect(self._regions_changed)
        c.add(self.canvas, 1)

        seek = QHBoxLayout()
        seek.setSpacing(10)
        back = button("", "rewind", "tool", "Lùi 5 giây")
        back.clicked.connect(lambda: self._seek_rel(-5))
        fwd = button("", "forward", "tool", "Tới 5 giây")
        fwd.clicked.connect(lambda: self._seek_rel(5))
        self.scrub = QSlider(Qt.Horizontal)
        self.scrub.setRange(0, 1000)
        self.scrub.setCursor(Qt.PointingHandCursor)
        self.scrub.sliderReleased.connect(self._scrub_released)
        self.scrub.valueChanged.connect(self._scrub_moved)
        self.time_lbl = label("00:00 / 00:00", "Mono")
        self.time_lbl.setMinimumWidth(110)
        self.time_lbl.setAlignment(Qt.AlignCenter)
        seek.addWidget(back)
        seek.addWidget(self.scrub, 1)
        seek.addWidget(fwd)
        seek.addWidget(self.time_lbl)
        c.add(seek)

        tools = QHBoxLayout()
        tools.setSpacing(6)
        tools.addWidget(label("Thêm vùng", "FieldLabel"))
        for kind, text, ic, color, tip in [
            ("ocr", "OCR", "scan", C["cyan"], "Vùng chứa phụ đề gốc để đọc chữ"),
            ("blur", "Mờ", "droplet", C["red"], "Che / làm mờ phụ đề gốc"),
            ("sub", "Sub", "captions", C["green"], "Vị trí đặt phụ đề tiếng Việt"),
            ("logo", "Logo", "image", C["accent"], "Chèn logo kênh"),
            ("text", "Chữ", "type", C["amber"], "Chèn chữ / watermark (nhấp đúp để sửa)"),
        ]:
            b = button(text, ic, "tool", tip, icon_color=color)
            b.clicked.connect(lambda _=False, k=kind: self._add_region(k))
            tools.addWidget(b)
        tools.addStretch()
        apply_all = button("", "copy", "ghost", "Áp dụng bố cục vùng này cho tất cả video")
        apply_all.clicked.connect(self._apply_regions_all)
        tools.addWidget(apply_all)
        self.btn_subs = button("Sửa phụ đề", "edit", "primary")
        self.btn_subs.clicked.connect(self.open_sub_editor)
        tools.addWidget(self.btn_subs)
        c.add(tools)
        return c

    # ================================================================= jobs
    def browse(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn video", "", "Video (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.m4v *.ts);;Tất cả (*.*)")
        self.add_files(files)

    def browse_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa video")
        if d:
            self.add_files([str(p) for p in sorted(Path(d).iterdir()) if p.suffix.lower() in VIDEO_EXT])

    def _add_job(self, job: Job) -> JobRow:
        row = JobRow(job)
        row.clicked.connect(self.select_job)
        row.doubleClicked.connect(lambda jid: (self.select_job(jid), self.open_sub_editor()))
        row.checkToggled.connect(self._on_check)
        self.jobs[job.id], self.rows[job.id] = job, row
        self.joblist.add_row(row)
        return row

    # ---------------------------------------------------------------- lưu / khôi phục danh sách video
    def _jobs_dirty(self):
        self._jobs_timer.start()

    def save_jobs(self):
        items = []
        for j in self.jobs.values():
            d = asdict(j)
            if d["status"] == "Đang xử lý":          # đang chạy dở lúc tắt app → coi như chưa xử lý
                d["status"], d["step"], d["progress"] = "Chờ", "", 0.0
            items.append(d)
        tmp = JOBS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(JOBS_FILE)

    def restore_jobs(self):
        try:
            items = json.loads(JOBS_FILE.read_text("utf-8"))
        except (OSError, ValueError):
            return
        fields = set(Job.__dataclass_fields__)
        missing = 0
        for d in items:
            if not Path(d.get("path", "")).exists():
                missing += 1
                continue
            job = Job(**{k: v for k, v in d.items() if k in fields})
            row = self._add_job(job)
            frame = job.frame_path(job.preview_t)
            if frame.exists():
                row.set_thumb(QPixmap(str(frame)))
            row.refresh()
        if missing:
            log(f"Bỏ qua {missing} video trong danh sách cũ vì file không còn tồn tại", "warn")
        if self.jobs:
            log(f"Đã mở lại {len(self.jobs)} video từ lần trước")
            self.select_job(next(iter(self.jobs)))
        self._update_counts()

    def add_files(self, files: list[str]):
        existing = {j.path for j in self.jobs.values()}
        added = 0
        for f in files:
            if Path(f).suffix.lower() not in VIDEO_EXT or f in existing:
                continue
            job = Job(path=f, regions=self._default_regions())
            self._add_job(job)
            run_async(media.probe, f, on_done=lambda info, j=job: self._probed(j, info),
                      on_error=lambda err, j=job: self._probe_failed(j, err))
            added += 1
        if added:
            log(f"Đã thêm {added} video")
            toast(self, f"Đã thêm {added} video", "ok")
            if self.current is None:
                self.select_job(next(iter(self.jobs)))
        self._update_counts()

    def _default_regions(self) -> list[dict]:
        regions = [{"kind": "ocr", "rect": [0.10, 0.79, 0.80, 0.14], "text": ""}]
        sysc = self.get_system()
        if sysc.get("auto_layers"):
            if sysc.get("watermark"):
                regions.append({"kind": "text", "rect": [0.66, 0.05, 0.30, 0.07], "text": sysc["watermark"]})
            if sysc.get("logo_path"):
                regions.append({"kind": "logo", "rect": [0.03, 0.05, 0.09, 0.14], "text": ""})
        return regions

    def _probed(self, job: Job, info: dict):
        if job.id not in self.jobs:
            return
        job.duration, job.width, job.height, job.fps = info["duration"], info["width"], info["height"], info["fps"]
        self._jobs_dirty()
        job.preview_t = min(job.duration * 0.25, 30.0) if job.duration else 0.0
        self.rows[job.id].refresh()
        self._load_frame(job, thumb=True)
        if job is self.current:
            self.canvas.set_aspect(job.width, job.height)
            self._sync_time()

    def _probe_failed(self, job: Job, err: str):
        job.status, job.step = "Lỗi", err
        if job.id in self.rows:
            self.rows[job.id].refresh()
        log(f"Không đọc được {job.name}: {err}", "error")

    def _load_frame(self, job: Job, thumb: bool = False):
        t = job.preview_t
        out = job.frame_path(t)

        def done(_):
            pm = QPixmap(str(out))
            if thumb and job.id in self.rows:
                self.rows[job.id].set_thumb(pm)
            if job is self.current and abs(job.preview_t - t) < 0.05:
                self.canvas.set_frame(pm)

        if out.exists():
            done(None)
            return
        if job is self.current:
            self.canvas.set_frame(None, busy=True)
        run_async(media.grab_frame, job.path, t, str(out), on_done=done,
                  on_error=lambda e: log(f"Không cắt được khung hình: {e}", "error"))

    def select_job(self, jid: str):
        job = self.jobs.get(jid)
        if not job:
            return
        for k, r in self.rows.items():
            r.set_selected(k == jid)
        self.current = job
        self.preview_name.setText(job.name)
        self.canvas.set_aspect(job.width, job.height)
        self.canvas.set_regions(job.regions)
        self.canvas.set_logo(self.get_system().get("logo_path") or None)
        self._sync_time()
        frame = job.frame_path(job.preview_t)
        if frame.exists():
            self.canvas.set_frame(QPixmap(str(frame)))
        elif job.duration:
            self._load_frame(job)
        else:
            self.canvas.set_frame(None, busy=True)

    def _on_check(self, jid: str, v: bool):
        self.jobs[jid].checked = v
        self._update_counts()

    def _check_all(self, v: bool):
        for r in self.rows.values():
            r.chk.setChecked(v)

    def remove_checked(self):
        if self.worker and self.worker.isRunning():
            toast(self, "Đang xử lý, hãy dừng trước khi xóa", "warn")
            return
        ids = [j.id for j in self.jobs.values() if j.checked]
        if not ids:
            toast(self, "Chưa tick video nào để xóa", "warn")
            return
        for jid in ids:
            self.joblist.remove_row(self.rows.pop(jid))
            self.jobs.pop(jid)
        if self.current and self.current.id in ids:
            self.current = None
            self.canvas.set_regions([])
            self.canvas.set_frame(None)
            self.preview_name.setText("")
            if self.jobs:
                self.select_job(next(iter(self.jobs)))
        toast(self, f"Đã xóa {len(ids)} video", "info")
        self._update_counts()

    def _update_counts(self):
        if hasattr(self, "_jobs_timer"):
            self._jobs_dirty()
        n = len(self.jobs)
        checked = sum(j.checked for j in self.jobs.values())
        self.count_chip.setText(f"{n} video")
        self.summary.setText(f"đã chọn {checked}" if n else "")
        self.list_stack.setCurrentIndex(1 if n else 0)
        running = bool(self.worker and self.worker.isRunning())
        self.btn_start.setEnabled(bool(checked) and not running)
        self.btn_subs.setEnabled(self.current is not None)

    # ================================================================= canvas
    def _add_region(self, kind: str):
        if not self.current:
            toast(self, "Thêm một video trước đã", "warn")
            return
        text = self.get_system().get("watermark", "") if kind == "text" else ""
        self.canvas.add_region(kind, text)

    def _regions_changed(self):
        if self.current:
            self.current.regions = self.canvas.get_regions()
            self._jobs_dirty()

    def _apply_regions_all(self):
        if not self.current:
            return
        for j in self.jobs.values():
            j.regions = [dict(r) for r in self.current.regions]
        toast(self, f"Đã áp dụng bố cục vùng cho {len(self.jobs)} video", "ok")

    def _sync_time(self):
        j = self.current
        if not j or not j.duration:
            self.time_lbl.setText("00:00 / 00:00")
            return
        self.scrub.blockSignals(True)
        self.scrub.setValue(int(j.preview_t / j.duration * 1000))
        self.scrub.blockSignals(False)
        self.time_lbl.setText(f"{media.fmt_time(j.preview_t)} / {media.fmt_time(j.duration)}")

    def _scrub_moved(self, v: int):
        j = self.current
        if j and j.duration:
            self.time_lbl.setText(f"{media.fmt_time(v / 1000 * j.duration)} / {media.fmt_time(j.duration)}")
            if not self.scrub.isSliderDown():
                self._scrub_released()

    def _scrub_released(self):
        j = self.current
        if j and j.duration:
            j.preview_t = self.scrub.value() / 1000 * j.duration
            self._load_frame(j)

    def _seek_rel(self, d: float):
        j = self.current
        if j and j.duration:
            j.preview_t = min(max(0.0, j.preview_t + d), max(0.0, j.duration - 0.1))
            self._sync_time()
            self._load_frame(j)

    # ================================================================= pipeline
    def start(self):
        if self.worker and self.worker.isRunning():
            return
        jobs = [j for j in self.jobs.values() if j.checked]
        if not jobs:
            toast(self, "Chưa chọn video nào để xử lý", "warn")
            return
        for j in jobs:
            j.status, j.progress, j.step = "Chờ", 0.0, "Trong hàng đợi"
            self.rows[j.id].refresh()
        self._done, self._total = 0, len(jobs)
        payload = [{"id": j.id, "name": j.name, "path": j.path, "workdir": str(j.workdir),
                    "regions": j.regions, "width": j.width, "height": j.height,
                    "duration": j.duration} for j in jobs]
        self.worker = PipelineWorker(payload, {**self.get_system(), **self.config.values()})
        self.worker.progress.connect(self._on_progress)
        self.worker.jobFinished.connect(self._on_job_finished)
        self.worker.finished.connect(self._on_all_finished)
        self.worker.start()
        self.btn_stop.setEnabled(True)
        self._update_counts()
        self.statusChanged.emit(f"Đang xử lý 0/{self._total}", "run")

    def stop(self):
        if self.worker:
            self.worker.stop()
            self.btn_stop.setEnabled(False)
            self.statusChanged.emit("Đang dừng…", "warn")

    def _on_progress(self, jid: str, step: str, p: float):
        j = self.jobs.get(jid)
        if not j:
            return
        j.status, j.step, j.progress = "Đang xử lý", step, p
        self.rows[jid].refresh()

    def _on_job_finished(self, jid: str, result: str):
        j = self.jobs.get(jid)
        if not j:
            return
        self._jobs_dirty()
        if result == "done":
            out = self.worker.outputs.get(jid) if self.worker else None
            step = f"Đã xuất {Path(out).name} · nhấp đúp để xem phụ đề" if out else "Xong · nhấp đúp để xem phụ đề"
            j.status, j.step, j.progress = "Hoàn thành", step, 1.0
            self._done += 1
            self.statusChanged.emit(f"Đang xử lý {self._done}/{self._total}", "run")
        elif result == "stopped":
            j.status, j.step = "Đã dừng", "Người dùng dừng"
        else:
            j.status, j.step = "Lỗi", result.removeprefix("error:")
        self.rows[jid].refresh()

    def _on_all_finished(self):
        for j in self.jobs.values():
            if j.status in ("Chờ", "Đang xử lý") and j.step:
                j.status, j.step = "Chờ", ""
                self.rows[j.id].refresh()
        self.btn_stop.setEnabled(False)
        self._update_counts()
        self.statusChanged.emit("Sẵn sàng", "ok")
        toast(self, f"Xong {self._done}/{self._total} video", "ok" if self._done == self._total else "warn")

    def open_output_dir(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        d = Path(self.config.values().get("output") or Path.home() / "Videos" / "DubStudio")
        d.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))

    def is_running(self) -> bool:
        return bool(self.worker and self.worker.isRunning())

    # ================================================================= sub editor
    def open_sub_editor(self):
        if not self.current:
            return
        from ..dialogs.sub_editor import SubEditorDialog
        SubEditorDialog(self.current, self, {**self.get_system(), **self.config.values()}).exec()

    # ================================================================= drag & drop
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = []
        for u in e.mimeData().urls():
            p = Path(u.toLocalFile())
            if p.is_dir():
                files += [str(x) for x in sorted(p.iterdir()) if x.suffix.lower() in VIDEO_EXT]
            else:
                files.append(str(p))
        self.add_files(files)
