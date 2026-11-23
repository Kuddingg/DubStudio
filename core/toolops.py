"""Các công cụ lẻ (tab Công cụ): mỗi hàm nhận tham số + cấu hình, báo tiến độ report(p, msg), trả về
{"files": [đường dẫn kết quả], "message": "..."}. Tận dụng lại đúng các bước của quy trình chính."""
from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path

from . import asr, media, ocr, presets, render, separate, sync, translate, tts
from .log import log
from .media import NOWIN, which
from .srt import Cue, parse_srt, write_srt

DEFAULT_OCR_RECT = [0.10, 0.79, 0.80, 0.14]


def _workdir() -> Path:
    from app.paths import DATA
    d = DATA / "tools" / uuid.uuid4().hex[:10]
    d.mkdir(parents=True, exist_ok=True)
    return d


def _outdir(cfg: dict) -> Path:
    d = Path(cfg.get("output") or Path.home() / "Videos" / "DubStudio") / "Cong cu"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _preset(cfg: dict) -> dict:
    items = presets.load()
    return next((p for p in items if p["name"] == cfg.get("preset")), items[0])


def _job(video: str, wd: Path, regions=None) -> dict:
    info = media.probe(video)
    return {"id": wd.name, "name": Path(video).name, "path": video, "workdir": str(wd), "width": info["width"],
            "height": info["height"], "duration": info["duration"] or 1.0, "regions": regions or []}


# ---------------------------------------------------------------------------- 1. tách giọng / nhạc
def separate_audio(p: dict, cfg: dict, report, stop) -> dict:
    src = p["file"]
    if not render.has_audio(src):
        raise RuntimeError("File không có âm thanh")
    wd = _workdir()
    try:
        separate.separate(src, wd, cfg, True, lambda x, m=None: report(x, m or "Đang tách bằng Demucs…"), stop)
        if stop():
            return {}
        out, stem = _outdir(cfg), Path(src).stem
        files = []
        for name, label in (("vocals.wav", "giong"), ("accompaniment.wav", "nhac_nen")):
            dst = render.unique_path(out / f"{stem}_{label}.mp3")
            subprocess.run([which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(wd / name),
                            "-b:a", "192k", str(dst)], check=True, creationflags=NOWIN)
            files.append(str(dst))
        return {"files": files, "message": "Đã tách thành 2 file: giọng nói và nhạc nền"}
    finally:
        shutil.rmtree(wd, ignore_errors=True)


# ---------------------------------------------------------------------------- 2. trích phụ đề
def extract_subs(p: dict, cfg: dict, report, stop) -> dict:
    video, mode = p["file"], p.get("mode", "")
    wd = _workdir()
    try:
        job = _job(video, wd)
        if "OCR" in mode:
            cues = ocr.extract(video, DEFAULT_OCR_RECT, job["width"], job["height"], job["duration"],
                               ocr.OcrOptions.from_cfg(cfg), lambda x: report(x, "Đang đọc chữ trên hình…"), stop)
        else:
            audio = asr.extract_audio(video, wd / "a.wav")
            cues = asr.transcribe(audio, job["duration"], cfg, lambda x, m=None: report(x, m or "Đang nghe giọng nói…"), stop)
        if stop():
            return {}
        if not cues:
            raise RuntimeError("Không lấy được câu nào"
                               + (" (công cụ quét vùng 1/5 dưới khung hình; vị trí khác hãy dùng tab Biên tập)" if "OCR" in mode else ""))
        out = render.unique_path(_outdir(cfg) / f"{Path(video).stem}_goc.srt")
        out.write_text(write_srt([Cue(int(s * 1000), int(e * 1000), "", t) for s, e, t in cues], "dst"), "utf-8")
        return {"files": [str(out)], "message": f"Đã trích {len(cues)} câu"}
    finally:
        shutil.rmtree(wd, ignore_errors=True)


# ---------------------------------------------------------------------------- 3. dịch SRT
def translate_srt(p: dict, cfg: dict, report, stop) -> dict:
    src = Path(p["file"])
    cues = parse_srt(src.read_text("utf-8-sig"))
    if not cues:
        raise RuntimeError("File SRT trống hoặc sai định dạng")
    report(0.02, "Đang dịch…")
    vis = translate.translate_all([c.dst for c in cues], _preset(cfg), cfg, lambda x: report(x, "Đang dịch…"), stop,
                                  secs=[(c.end - c.start) / 1000 for c in cues])
    out = render.unique_path(_outdir(cfg) / f"{src.stem}_vi.srt")
    out.write_text(write_srt([Cue(c.start, c.end, "", v) for c, v in zip(cues, vis)], "dst"), "utf-8")
    return {"files": [str(out)], "message": f"Đã dịch {len(cues)} câu"}


# ---------------------------------------------------------------------------- 4. tạo giọng từ SRT
def voice_from_srt(p: dict, cfg: dict, report, stop) -> dict:
    src = Path(p["file"])
    cues = parse_srt(src.read_text("utf-8-sig"))
    if not cues:
        raise RuntimeError("File SRT trống hoặc sai định dạng")
    wd = _workdir()
    try:
        tts.synth_all(cues, wd, cfg.get("voice", ""), float(cfg.get("speed", 1.0)),
                      lambda x: report(0.85 * x, "Đang tạo giọng đọc…"), stop, pitch=float(cfg.get("pitch", 0)))
        if stop():
            return {}
        dur = max(c.end for c in cues) / 1000 + 1.0
        placed = sync.build_track(wd, dur, float(cfg.get("lead", 0)), bool(cfg.get("smart_voice", True)),
                                  lambda x: report(0.85 + 0.13 * x, "Đang căn khớp thời gian…"), stop)
        out = render.unique_path(_outdir(cfg) / f"{src.stem}_giong_doc.mp3")
        subprocess.run([which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(wd / "voice.wav"),
                        "-b:a", "192k", str(out)], check=True, creationflags=NOWIN)
        over = sum(1 for x in placed if x.get("over", 0) > 0)
        return {"files": [str(out)], "message": f"Đã đọc {len(placed)} câu, khớp thời gian phụ đề"
                + (f" ({over} câu đọc dài hơn khung)" if over else "")}
    finally:
        shutil.rmtree(wd, ignore_errors=True)


# ---------------------------------------------------------------------------- 5–6. ghép sub / đổi khung
def _render_only(video: str, cfg: dict, extra: dict, srt: str | None, report, stop, suffix: str) -> dict:
    wd = _workdir()
    try:
        job = _job(video, wd)
        if srt:
            vi = parse_srt(Path(srt).read_text("utf-8-sig"))
            (wd / "sub_vi.srt").write_text(write_srt(vi, "dst"), "utf-8")
        c = {**cfg, "do_dub": False, "do_sub": bool(srt), **extra,
             "output": str(_outdir(cfg))}
        out = render.render(job, c, wd, lambda x: report(x, "Đang xuất video…"), stop)
        if stop():
            return {}
        final = render.unique_path(out.with_name(f"{Path(video).stem}_{suffix}{out.suffix}"))
        out.replace(final)
        return {"files": [str(final)], "message": "Đã xuất video"}
    finally:
        shutil.rmtree(wd, ignore_errors=True)


def burn_subs(p: dict, cfg: dict, report, stop) -> dict:
    return _render_only(p["file"], cfg, {"ratio": "Giữ nguyên"}, p["srt"], report, stop, "co_phu_de")


def to_vertical(p: dict, cfg: dict, report, stop) -> dict:
    return _render_only(p["file"], cfg, {"ratio": p.get("ratio", "9:16 · TikTok / Shorts"), "bg": p.get("bg", "Nền mờ")},
                        p.get("srt") or None, report, stop, "doi_khung")


# ---------------------------------------------------------------------------- 7. nén / đổi định dạng
def compress(p: dict, cfg: dict, report, stop) -> dict:
    video, fmt, quality = p["file"], p.get("format", "MP4"), p.get("quality", "Cân bằng")
    info = media.probe(video)
    dur = info["duration"] or 1.0
    ext = {"MP4": ".mp4", "MKV": ".mkv", "WEBM": ".webm"}.get(fmt, ".mp4")
    out = render.unique_path(_outdir(cfg) / f"{Path(video).stem}_nen{ext}")
    q = render.QUALITY.get(quality, 1)
    if ext == ".webm":
        encs = [["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", str([30, 34, 38][q]), "-row-mt", "1", "-c:a", "libopus", "-b:a", "128k"]]
    else:
        a = ["-c:a", "aac", "-b:a", "160k"]
        encs = [render._encoder_args(cfg.get("encoder", "CPU"), quality) + a]
        if encs[0][1] != "libx264":
            encs.append(render._x264(quality) + a)
    scale = []
    if p.get("max_height") and p["max_height"] != "Giữ nguyên" and info["height"]:
        h = int(p["max_height"].rstrip("p"))
        if info["height"] > h:
            scale = ["-vf", f"scale=-2:{h}"]
    last = ""
    for enc in encs:
        proc = subprocess.Popen([which("ffmpeg"), "-hide_banner", "-y", "-loglevel", "error", "-progress", "pipe:1",
                                 "-nostats", "-i", video, *scale, *enc, str(out)], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, creationflags=NOWIN, encoding="utf-8", errors="replace")
        for line in proc.stdout:
            if stop():
                proc.kill()
                proc.wait()
                out.unlink(missing_ok=True)
                return {}
            if line.startswith("out_time_us="):
                try:
                    report(min(0.99, int(line.split("=")[1]) / 1e6 / dur), "Đang nén…")
                except ValueError:
                    pass
        proc.wait()
        if proc.returncode == 0:
            before, after = Path(video).stat().st_size, out.stat().st_size
            return {"files": [str(out)], "message": f"{before / 1e6:.1f} MB → {after / 1e6:.1f} MB "
                                                     f"({(1 - after / before) * 100:.0f}% nhỏ hơn)" if after < before
                    else f"Đã xuất ({after / 1e6:.1f} MB)"}
        last = (proc.stderr.read() or "").strip()[-300:]
        if enc is not encs[-1]:
            log(f"Encoder {enc[1]} không dùng được → chuyển sang CPU (x264)", "warn")
    raise RuntimeError(f"FFmpeg lỗi: {last}")


# ---------------------------------------------------------------------------- 8. tải video
class _QuietLogger:
    """Không in ra console (app chạy không có console); lỗi vẫn được báo qua exception."""
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def download(p: dict, cfg: dict, report, stop) -> dict:
    import yt_dlp
    url = p["url"].strip()
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("Link không hợp lệ (phải bắt đầu bằng http:// hoặc https://)")
    out_dir = _outdir(cfg)
    got: list[str] = []

    def hook(d):
        if stop():
            raise yt_dlp.utils.DownloadCancelled("Người dùng dừng")
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                report(min(0.99, d.get("downloaded_bytes", 0) / total), "Đang tải…")
        elif d.get("status") == "finished":
            got.append(d.get("filename", ""))

    opts = {"outtmpl": str(out_dir / "%(title).80s [%(id)s].%(ext)s"), "progress_hooks": [hook], "noplaylist": True,
            "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b", "merge_output_format": "mp4", "quiet": True,
            "no_warnings": True, "noprogress": True, "logger": _QuietLogger(), "ffmpeg_location": str(Path(which("ffmpeg")).parent) if which("ffmpeg") else None}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
    except yt_dlp.utils.DownloadCancelled:
        return {}
    except yt_dlp.utils.DownloadError as e:
        msg = str(e).replace("ERROR: ", "")
        msg = msg.split(": ", 1)[-1] if msg.startswith("[") else msg       # bỏ tiền tố [site] id:
        raise RuntimeError(f"Không tải được: {msg}") from None
    final = Path(path).with_suffix(".mp4") if Path(path).with_suffix(".mp4").exists() else Path(path)
    return {"files": [str(final)], "message": f"Đã tải: {info.get('title', final.name)}"}
