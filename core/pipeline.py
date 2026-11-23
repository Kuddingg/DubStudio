"""Pipeline xử lý: chạy tuần tự từng video, từng bước, báo tiến độ về UI.

Hiện các bước là STUB (giả lập tiến độ) để dựng và test UI.
Thay nội dung các hàm step_* bằng xử lý thật, giữ nguyên chữ ký (job, report).
"""
import hashlib
import json
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from . import asr, metadata, ocr, presets, render, separate, sync, translate, tts
from .log import log
from .srt import Cue, parse_srt, write_srt

# (key, nhãn hiển thị, trọng số trong thanh tiến độ)
STEPS = [
    ("extract", "Trích xuất phụ đề", 0.22),
    ("translate", "Dịch bằng AI", 0.13),
    ("separate", "Tách giọng / nhạc nền", 0.15),
    ("tts", "Tạo giọng đọc", 0.22),
    ("sync", "Căn khớp thời gian", 0.06),
    ("render", "Render video", 0.22),
]


# Các bước đã làm thật; còn lại đang giả lập tiến độ
REAL_STEPS = {"extract", "translate", "separate", "tts", "sync", "render"}


def plan(cfg: dict) -> list:
    steps = []
    for key, label, w in STEPS:
        if key in ("separate", "tts", "sync") and not cfg.get("do_dub", True):
            continue
        if key == "render" and not cfg.get("do_render", True):
            continue
        steps.append((key, label if key in REAL_STEPS else f"{label} · giả lập", w))
    return steps


class PipelineWorker(QThread):
    progress = Signal(str, str, float)   # job_id, nhãn bước, 0..1
    jobFinished = Signal(str, str)       # job_id, "done" | "stopped" | "error:<msg>"

    def __init__(self, jobs: list[dict], cfg: dict):
        super().__init__()
        self.jobs, self.cfg = jobs, cfg
        self._stop = False
        self.outputs: dict[str, str] = {}   # job_id → file video đã xuất

    def stop(self):
        self._stop = True

    def run(self):
        steps = plan(self.cfg)
        total = sum(w for *_, w in steps) or 1.0
        for job in self.jobs:
            if self._stop:
                break
            done = 0.0
            log(f"Bắt đầu: {job['name']}")
            try:
                for key, label, w in steps:
                    def report(p, msg=None, _label=label, _done=done, _w=w, _id=job["id"]):
                        # msg: dòng trạng thái riêng (vd "Tải model … 120/480 MB"), không có thì hiện tên bước
                        self.progress.emit(_id, msg or _label, (_done + _w * min(1.0, p)) / total)

                    report(0)
                    getattr(self, f"step_{key}")(job, report)
                    if self._stop:
                        self.jobFinished.emit(job["id"], "stopped")
                        log(f"Đã dừng: {job['name']}", "warn")
                        return
                    done += w
            except Exception as e:  # noqa: BLE001
                self.jobFinished.emit(job["id"], f"error:{e}")
                log(f"Lỗi {job['name']}: {e}", "error")
                continue
            self.jobFinished.emit(job["id"], "done")
            log(f"Hoàn thành: {job['name']}", "ok")

    # ------------------------------------------------------------------ steps
    def _simulate(self, report, seconds: float):
        n = max(1, int(seconds * 20))
        for i in range(n):
            if self._stop:
                return
            time.sleep(0.05)
            report((i + 1) / n)

    def _save_extracted(self, job, cues, sig: str):
        wd = Path(job["workdir"])
        (wd / "sub_zh.srt").write_text(
            write_srt([Cue(int(s * 1000), int(e * 1000), t, "") for s, e, t in cues], "src"), encoding="utf-8")
        (wd / "extract.json").write_text(json.dumps({"sig": sig}), encoding="utf-8")
        (wd / "sub_vi.srt").unlink(missing_ok=True)  # phụ đề gốc mới → bản dịch cũ hết hợp lệ
        log(f"Đã lưu {len(cues)} câu → {wd / 'sub_zh.srt'}", "ok")

    def _cached_extract(self, job, sig: str) -> bool:
        wd = Path(job["workdir"])
        meta = wd / "extract.json"
        if (wd / "sub_zh.srt").exists() and meta.exists() and json.loads(meta.read_text("utf-8")).get("sig") == sig:
            log(f"Dùng lại phụ đề đã trích trước đó (thiết lập không đổi): {job['name']}")
            return True
        return False

    def step_extract_asr(self, job, report):
        wd = Path(job["workdir"])
        sig = hashlib.sha1(json.dumps(["asr", job["path"], self.cfg.get("asr_model", "small"),
                                       self.cfg.get("src_lang", "")]).encode()).hexdigest()
        if self._cached_extract(job, sig):
            report(1.0)
            return
        has_audio = render.has_audio(job["path"])
        if not has_audio:
            raise RuntimeError("Video không có âm thanh, không nhận giọng nói được, hãy chọn Hình (OCR)")
        # Có nhạc nền → tách giọng trước (Demucs) rồi mới nghe: nhận chữ chính xác hơn nhiều
        audio = None
        if self.cfg.get("keep_music", True) and separate.available():
            separate.separate(job["path"], wd, self.cfg, True, lambda p, m=None: report(0.4 * p, m), lambda: self._stop)
            if self._stop:
                return
            if (wd / "vocals.wav").exists():
                audio = wd / "vocals.wav"
        if audio is None:
            audio = asr.extract_audio(job["path"], wd / "asr_input.wav")
        base = 0.4 if audio.name == "vocals.wav" else 0.05
        cues = asr.transcribe(audio, float(job["duration"]), self.cfg,
                              lambda p, m=None: report(base + (1 - base) * p, m), lambda: self._stop)
        if self._stop:
            return
        if not cues:
            raise RuntimeError("Không nghe được câu nào: video có lời thoại không? thử đổi Ngôn ngữ nguồn")
        self._save_extracted(job, cues, sig)

    def step_extract(self, job, report):
        if "ASR" in str(self.cfg.get("extract", "")):
            return self.step_extract_asr(job, report)
        rect = next((r["rect"] for r in job.get("regions", []) if r.get("kind") == "ocr"), None)
        if rect is None:
            raise RuntimeError("Chưa có vùng OCR, hãy thêm vùng OCR trên khung xem trước")
        opts = ocr.OcrOptions.from_cfg(self.cfg)
        # Cùng video + cùng vùng + cùng thiết lập OCR mà đã có kết quả → dùng lại, khỏi OCR lại
        sig = hashlib.sha1(json.dumps([job["path"], rect, opts.__dict__], sort_keys=True).encode()).hexdigest()
        if self._cached_extract(job, sig):
            report(1.0)
            return
        cues = ocr.extract(job["path"], rect, job["width"], job["height"], job["duration"],
                           opts, report, lambda: self._stop)
        if self._stop:
            return
        if not cues:
            raise RuntimeError("Không đọc được câu nào, kiểm tra lại vị trí vùng OCR")
        self._save_extracted(job, cues, sig)

    def step_translate(self, job, report):
        src_file = Path(job["workdir"]) / "sub_zh.srt"
        if not src_file.exists():
            raise RuntimeError("Chưa có phụ đề gốc để dịch (bước trích xuất chưa chạy)")
        cues = parse_srt(src_file.read_text(encoding="utf-8"))  # parse_srt để chữ ở .dst
        srcs = [c.dst for c in cues]
        preset = next((p for p in presets.load() if p["name"] == self.cfg.get("preset")), presets.load()[0])
        llm = self.cfg.get("llm", "Gemini")
        if str(llm).startswith("Ollama"):
            llm = f"Ollama ({self.cfg.get('ollama_model') or translate.OLLAMA_DEFAULT_MODEL})"
        out = Path(job["workdir"]) / "sub_vi.srt"
        # Giữ bản dịch đã có (kể cả câu đã sửa tay / chỉnh thời gian trong Sửa phụ đề):
        # cùng số câu với phụ đề gốc → giữ nguyên câu đã dịch, chỉ dịch câu còn trống.
        keep = None
        if self.cfg.get("keep_translation", True) and out.exists():
            old = parse_srt(out.read_text(encoding="utf-8"))
            if len(old) == len(cues):
                keep = old
        if keep is not None:
            cues = [Cue(o.start, o.end) for o in keep]          # giữ cả thời gian đã chỉnh tay
            todo = [i for i, o in enumerate(keep) if not o.dst.strip() and srcs[i].strip()]
            if not todo:
                log(f"Giữ nguyên bản dịch đã có ({len(keep)} câu), không dịch lại")
                report(1.0)
                return
            log(f"Giữ {len(keep) - len(todo)} câu đã dịch, dịch {len(todo)} câu còn trống bằng {llm}")
        else:
            todo = list(range(len(srcs)))
            log(f"Dịch {len(srcs)} câu bằng {llm} · kịch bản “{preset['name']}”")
        t0 = time.time()
        try:
            part = translate.translate_all([srcs[i] for i in todo], preset, self.cfg, report, lambda: self._stop,
                                           secs=[(cues[i].end - cues[i].start) / 1000 for i in todo])
        except translate.Stopped:
            return
        vis = [o.dst for o in keep] if keep is not None else [""] * len(srcs)
        for i, v in zip(todo, part):
            vis[i] = v
        out.write_text(write_srt([Cue(c.start, c.end, s, v) for c, s, v in zip(cues, srcs, vis)], "dst"),
                       encoding="utf-8")
        log(f"Đã dịch {len(todo)} câu trong {time.time() - t0:.0f}s → {out}", "ok")

    def step_separate(self, job, report):
        if not self.cfg.get("keep_music", True):
            report(1.0)
            return                                   # không giữ nhạc nền → khỏi tách
        t0 = time.time()
        acc = separate.separate(job["path"], Path(job["workdir"]), self.cfg, render.has_audio(job["path"]),
                                report, lambda: self._stop)
        if acc and not self._stop:
            log(f"Đã tách nhạc nền trong {time.time() - t0:.0f}s", "ok")

    def step_tts(self, job, report):
        vi_file = Path(job["workdir"]) / "sub_vi.srt"
        if not vi_file.exists():
            raise RuntimeError("Chưa có phụ đề tiếng Việt để đọc (bước dịch chưa chạy)")
        cues = parse_srt(vi_file.read_text(encoding="utf-8"))
        t0 = time.time()
        entries = tts.synth_all(cues, Path(job["workdir"]), self.cfg.get("voice", ""),
                                float(self.cfg.get("speed", 1.0)), report, lambda: self._stop,
                                pitch=float(self.cfg.get("pitch", 0)))
        if self._stop:
            return
        over = [e for e in entries if e["text"] and tts.overflow(e) > 0.05]
        log(f"Đã tạo giọng {len([e for e in entries if e['text']])} câu trong {time.time() - t0:.0f}s", "ok")
        if over:
            log(f"{len(over)} câu đọc dài hơn khung thời gian (sẽ xử lý ở bước Căn khớp), "
                f"ví dụ câu #{over[0]['i'] + 1} dư {tts.overflow(over[0]):.1f}s", "warn")

    def step_sync(self, job, report):
        wd = Path(job["workdir"])
        if not (wd / "tts" / "index.json").exists():
            raise RuntimeError("Chưa có giọng đọc để căn khớp (bước tạo giọng chưa chạy)")
        sync.build_track(wd, float(job["duration"]), float(self.cfg.get("lead", 0)),
                         bool(self.cfg.get("smart_voice", True)), report, lambda: self._stop)

    def step_render(self, job, report):
        t0 = time.time()
        out = render.render(job, self.cfg, Path(job["workdir"]), report, lambda: self._stop)
        if not self._stop:
            log(f"Đã xuất video trong {time.time() - t0:.0f}s → {out}", "ok")
            self.outputs[job["id"]] = str(out)
            vi = Path(job["workdir"]) / "sub_vi.srt"
            if self.cfg.get("creative_meta", True) and vi.exists():
                metadata.write_for(Path(out), vi, self.cfg)
