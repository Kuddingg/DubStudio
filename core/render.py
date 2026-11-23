"""Bước 4 · Render: dựng một lệnh FFmpeg duy nhất cho toàn bộ video.

Hình: làm mờ vùng sub gốc → chèn logo → chữ/watermark → phụ đề tiếng Việt (ASS) → đổi khung hình (9:16, 16:9, 1:1).
Tiếng: giọng AI (voice.wav, qua EQ / high-pass / compressor) + nền (nhạc tách riêng, hoặc âm gốc vặn nhỏ) → chuẩn hóa âm lượng.
Encoder NVENC / QSV / AMF lỗi (máy không có GPU tương ứng) → tự chuyển sang CPU x264.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .log import log
from .media import NOWIN, which
from .srt import parse_srt

QUALITY = {"Cao": 0, "Cân bằng": 1, "Nhanh": 2}


class RenderError(RuntimeError):
    pass


# ============================================================================ helpers
def has_audio(path: str) -> bool:
    out = subprocess.run([which("ffprobe"), "-v", "error", "-select_streams", "a", "-show_entries",
                          "stream=index", "-of", "csv=p=0", path],
                         capture_output=True, text=True, creationflags=NOWIN, timeout=30)
    return bool(out.stdout.strip())


def _ass_color(hex_color: str, alpha: int = 0) -> str:
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _px(rect, W: int, H: int):
    x, y, w, h = rect
    px, py = max(0, int(x * W)), max(0, int(y * H))
    pw, ph = min(W - px, max(2, int(w * W))), min(H - py, max(2, int(h * H)))
    return px // 2 * 2, py // 2 * 2, max(2, pw // 2 * 2), max(2, ph // 2 * 2)


def _find_font() -> str | None:
    for f in ("segoeuib.ttf", "segoeui.ttf", "arialbd.ttf", "arial.ttf"):
        p = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / f
        if p.exists():
            return p.as_posix().replace(":", r"\:")
    return None


def _new_frame_margin(cfg: dict, W: int, H: int, tgt) -> int | None:
    """Có in phụ đề vào vùng trống của khung mới không; có thì trả về MarginV (px, tính từ đáy khung mới)."""
    mode = cfg.get("sub_place", "Tự động")
    if mode.startswith("Trên video") or not tgt:
        return None
    TW, TH = tgt
    size = float(cfg.get("sub_size", 48)) * min(TW, TH) / 1080
    if cfg.get("bg", "Nền mờ").startswith("Phóng"):      # cắt lấp đầy: không có vùng trống
        return int(TH * 0.12) if mode.startswith("Vùng trống") else None
    s = min(TW / W, TH / H)
    free = (TH - H * s) / 2                                # chiều cao vùng trống dưới video
    if free < size * 2.2:                                  # vùng trống quá hẹp (vd 16:9 → 16:9)
        return int(TH * 0.06) if mode.startswith("Vùng trống") else None
    return int(max(TH * 0.04, free / 2 - size / 2))        # giữa vùng trống phía dưới


def write_ass(srt: Path, out: Path, cfg: dict, W: int, H: int, sub_rect=None, margin_v: int | None = None,
              offset_ms: int = 0) -> None:
    scale = min(W, H) / 1080       # cỡ chữ theo cạnh ngắn → khung dọc 1080×1920 không bị chữ quá to
    size = max(10, int(float(cfg.get("sub_size", 48)) * scale))
    outline = float(cfg.get("sub_outline_w", 3)) * scale
    box = bool(cfg.get("sub_box"))
    if sub_rect:
        x, y, w, h = sub_rect
        ml, mr, mv = int(x * W), int((1 - x - w) * W), int((1 - y - h) * H)
    else:
        ml = mr = int(W * 0.05)
        mv = int(H * 0.06) if margin_v is None else int(margin_v)
    style = ",".join(str(v) for v in [
        "Default", cfg.get("sub_font") or "Arial", size,
        _ass_color(cfg.get("sub_color", "#FFE14D")), _ass_color(cfg.get("sub_color", "#FFE14D")),
        _ass_color(cfg.get("sub_outline", "#000000")),
        _ass_color(cfg.get("sub_box_color", "#000000"), 0x50 if box else 0x80),
        -1 if cfg.get("sub_bold", True) else 0, 0, 0, 0, 100, 100, 0, 0,
        3 if box else 1, f"{outline:.1f}", 0, 2, ml, mr, mv, 1])
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: {style}", "",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    def tc(ms: int) -> str:
        cs = ms // 10
        return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"

    for c in parse_srt(srt.read_text("utf-8")):
        c.start, c.end = c.start - offset_ms, c.end - offset_ms      # xem thử: dời phụ đề theo điểm bắt đầu
        if c.end <= 0:
            continue
        c.start = max(0, c.start)
        text = c.dst.strip().replace("{", "(").replace("}", ")").replace("\n", r"\N")
        if text:
            lines.append(f"Dialogue: 0,{tc(c.start)},{tc(c.end)},Default,,0,0,0,,{text}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def _target_size(ratio: str, W: int, H: int):
    big = max(W, H) >= 1080 or min(W, H) >= 720
    if ratio.startswith("9:16"):
        return (1080, 1920) if big else (720, 1280)
    if ratio.startswith("16:9"):
        return (1920, 1080) if big else (1280, 720)
    if ratio.startswith("1:1"):
        return (1080, 1080) if big else (720, 720)
    return None


def _encoder_args(encoder: str, quality: str) -> list[str]:
    q = QUALITY.get(quality, 1)
    if encoder.startswith("NVIDIA"):
        return ["-c:v", "h264_nvenc", "-preset", ["p6", "p5", "p3"][q], "-rc", "vbr",
                "-cq", str([19, 23, 28][q]), "-b:v", "0"]
    if encoder.startswith("Intel"):
        return ["-c:v", "h264_qsv", "-global_quality", str([20, 23, 28][q])]
    if encoder.startswith("AMD"):
        qp = str([20, 24, 28][q])
        return ["-c:v", "h264_amf", "-rc", "cqp", "-qp_i", qp, "-qp_p", qp]
    return _x264(quality)


def _x264(quality: str) -> list[str]:
    q = QUALITY.get(quality, 1)
    # Giới hạn luồng + lookahead: mặc định x264 mở rất nhiều luồng, mỗi luồng giữ bộ đệm khung hình
    # → máy ít RAM (8GB, đang mở nhiều app) bị "malloc failed" khi xuất 1080×1920.
    threads = str(max(2, min(6, os.cpu_count() or 4)))
    return ["-c:v", "libx264", "-preset", ["slow", "medium", "veryfast"][q], "-crf", str([18, 21, 25][q]),
            "-threads", threads, "-x264-params", "rc-lookahead=20"]


def unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    for i in range(2, 1000):
        q = p.with_name(f"{p.stem}_{i}{p.suffix}")
        if not q.exists():
            return q
    return p


# ============================================================================ build
def build_command(job: dict, cfg: dict, workdir: Path, out: Path, preview: tuple | None = None):
    """Trả về (danh sách tham số FFmpeg sau phần encoder, encoder_args). Chạy với cwd=workdir."""
    W, H = int(job["width"]), int(job["height"])
    regions = job.get("regions", [])
    seek = ["-ss", f"{preview[0]:.3f}"] if preview else []          # xem thử: tua mọi nguồn tới cùng một điểm
    off = int(preview[0] * 1000) if preview else 0
    inputs = [*seek, "-i", job["path"]]
    n_in = 1
    vf: list[str] = []
    cur, k = "[0:v]", 0

    def lab():
        nonlocal k
        k += 1
        return f"[v{k}]"

    # 1) làm mờ phụ đề gốc
    for r in [r for r in regions if r["kind"] == "blur"]:
        x, y, w, h = _px(r["rect"], W, H)
        a, b, c, o = lab(), lab(), lab(), lab()
        rad = max(2, min(20, min(w, h) // 2 - 1))
        vf.append(f"{cur}split{a}{b};{b}crop={w}:{h}:{x}:{y},boxblur={rad}:2{c};{a}{c}overlay={x}:{y}{o}")
        cur = o

    # 2) logo
    logo = cfg.get("logo_path") or ""
    for r in [r for r in regions if r["kind"] == "logo"]:
        if not logo or not Path(logo).exists():
            log("Có vùng Logo nhưng chưa chọn file logo (tab Hệ thống) → bỏ qua", "warn")
            break
        x, y, w, h = _px(r["rect"], W, H)
        inputs += ["-i", logo]
        lg, o = lab(), lab()
        vf.append(f"[{n_in}:v]scale={w}:{h}:force_original_aspect_ratio=decrease{lg};"
                  f"{cur}{lg}overlay=x={x}+({w}-overlay_w)/2:y={y}+({h}-overlay_h)/2{o}")
        n_in += 1
        cur = o

    # 3) chữ / watermark
    font = _find_font()
    for i, r in enumerate([r for r in regions if r["kind"] == "text" and r.get("text", "").strip()]):
        x, y, w, h = _px(r["rect"], W, H)
        (workdir / f"wm_{i}.txt").write_text(r["text"].strip(), encoding="utf-8")
        o = lab()
        ff = f"fontfile='{font}':" if font else ""
        vf.append(f"{cur}drawtext={ff}textfile=wm_{i}.txt:fontsize={max(10, int(h * 0.62))}:fontcolor=white:"
                  f"borderw=2:bordercolor=black@0.8:x={x}+({w}-text_w)/2:y={y}+({h}-text_h)/2{o}")
        cur = o

    # 4) phụ đề tiếng Việt: in trên video gốc, hoặc (khi đổi khung) in vào vùng trống của khung mới
    vi = workdir / "sub_vi.srt"
    tgt = _target_size(cfg.get("ratio", "Giữ nguyên"), W, H)
    sub_on = cfg.get("do_sub", True) and vi.exists()
    if cfg.get("do_sub", True) and not vi.exists():
        log("Bật Phụ đề nhưng chưa có bản dịch → video không có phụ đề", "warn")
    new_frame_mv = _new_frame_margin(cfg, W, H, tgt) if (sub_on and tgt) else None
    if sub_on and new_frame_mv is None:
        sub_rect = next((r["rect"] for r in regions if r["kind"] == "sub"), None)
        write_ass(vi, workdir / "sub_vi.ass", cfg, W, H, sub_rect, offset_ms=off)
        o = lab()
        vf.append(f"{cur}subtitles=sub_vi.ass{o}")
        cur = o

    # 5) đổi khung hình
    if tgt:
        TW, TH = tgt
        bg = cfg.get("bg", "Nền mờ")
        o = lab()
        if bg.startswith("Phóng"):
            vf.append(f"{cur}scale={TW}:{TH}:force_original_aspect_ratio=increase,crop={TW}:{TH}{o}")
        elif bg.startswith("Nền đen"):
            vf.append(f"{cur}scale={TW}:{TH}:force_original_aspect_ratio=decrease,"
                      f"pad={TW}:{TH}:(ow-iw)/2:(oh-ih)/2:black{o}")
        else:
            f1, f2, g, fg = lab(), lab(), lab(), lab()
            vf.append(f"{cur}split{f1}{f2};{f2}scale={TW}:{TH}:force_original_aspect_ratio=increase,"
                      f"crop={TW}:{TH},boxblur=30:5{g};{f1}scale={TW}:{TH}:force_original_aspect_ratio=decrease{fg};"
                      f"{g}{fg}overlay=(W-w)/2:(H-h)/2{o}")
        cur = o
        if new_frame_mv is not None:   # phụ đề in sau khi đổi khung → nằm ở vùng trống, cỡ chữ theo khung mới
            write_ass(vi, workdir / "sub_vi.ass", cfg, TW, TH, None, margin_v=new_frame_mv, offset_ms=off)
            o = lab()
            vf.append(f"{cur}subtitles=sub_vi.ass{o}")
            cur = o
    vf.append(f"{cur}format=yuv420p[vout]")

    # ---- audio
    af: list[str] = []
    amap = None
    orig_audio = has_audio(job["path"])
    voice = workdir / "voice.wav"
    if cfg.get("do_dub", True) and voice.exists():
        inputs += [*seek, "-i", str(voice)]
        vi_idx = n_in
        n_in += 1
        chain = [f"volume={float(cfg.get('vol_ai', 120)) / 100:.2f}"]
        if cfg.get("fx_hp", True):
            chain.append("highpass=f=80")
        if cfg.get("fx_eq", True):
            chain.append("equalizer=f=3000:t=q:w=1:g=3")
        if cfg.get("fx_comp", True):
            chain.append("acompressor=threshold=0.125:ratio=3:attack=5:release=60")
        af.append(f"[{vi_idx}:a]{','.join(chain)}[va]")
        mix = ["[va]"]

        acc = workdir / "accompaniment.wav"
        bg_vol = 0.0
        bg_src = None
        if cfg.get("keep_music", True) and acc.exists():
            inputs += [*seek, "-i", str(acc)]
            bg_src, bg_vol = f"[{n_in}:a]", float(cfg.get("vol_music", 100)) / 100
            n_in += 1
        elif orig_audio:
            if cfg.get("keep_music", True):
                # chưa có nhạc tách riêng → dùng âm gốc vặn nhỏ để giữ không khí (giọng gốc vẫn nghe lẫn)
                bg_vol = float(cfg.get("vol_music", 100)) / 100 * 0.2
                if bg_vol > 0:
                    log("Chưa tách nhạc nền → dùng âm thanh gốc vặn nhỏ làm nền", "warn")
            bg_vol = max(bg_vol, float(cfg.get("vol_orig", 0)) / 100)
            bg_src = "[0:a]" if bg_vol > 0 else None
        if bg_src:
            af.append(f"{bg_src}volume={bg_vol:.2f}[ba]")
            mix.append("[ba]")
        # Giọng gốc đã tách riêng → trộn theo thanh "Giọng gốc" (mặc định 0% = tắt hẳn)
        voc = workdir / "vocals.wav"
        orig_vol = float(cfg.get("vol_orig", 0)) / 100
        if bg_src and bg_src != "[0:a]" and voc.exists() and orig_vol > 0:
            inputs += [*seek, "-i", str(voc)]
            af.append(f"[{n_in}:a]volume={orig_vol:.2f}[oa]")
            n_in += 1
            mix.append("[oa]")
        tail = "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000" if cfg.get("fx_norm", True) else "aresample=48000"
        if len(mix) > 1:
            af.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0,{tail}[aout]")
        else:
            af.append(f"[va]{tail}[aout]")
        amap = "[aout]"
    elif orig_audio:
        amap = "0:a:0"

    graph = ";".join(vf + af)
    args = [*inputs, "-filter_complex", graph, "-map", "[vout]"]
    if amap:
        args += ["-map", amap, "-c:a", "aac", "-b:a", "192k"]
    length = preview[1] if preview else float(job["duration"])
    args += ["-t", f"{length:.3f}", "-movflags", "+faststart"]
    return args


def render(job: dict, cfg: dict, workdir: Path, report=lambda p: None, should_stop=lambda: False,
           preview: tuple | None = None) -> Path:
    """preview=(giây bắt đầu, số giây) → xuất nhanh một đoạn ngắn vào thư mục project (preview.mp4)."""
    exe = which("ffmpeg")
    if not exe:
        raise RenderError("Không tìm thấy FFmpeg")
    out_dir = Path(cfg.get("output") or Path.home() / "Videos" / "DubStudio")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = workdir / "preview.mp4" if preview else unique_path(out_dir / f"{Path(job['path']).stem}_vi.mp4")
    args = build_command(job, cfg, workdir, out, preview)
    (workdir / "render_cmd.json").write_text(json.dumps(args, ensure_ascii=False, indent=1), encoding="utf-8")

    encoders = [_encoder_args(cfg.get("encoder", "CPU"), "Nhanh" if preview else cfg.get("quality", "Cân bằng"))]
    if encoders[0][1] != "libx264":
        encoders.append(_x264("Nhanh" if preview else cfg.get("quality", "Cân bằng")))
    duration = (preview[1] if preview else float(job["duration"])) or 1.0
    last_err = ""
    for enc in encoders:
        tmp = out.with_name(out.stem + ".part.mp4")
        cmd = [exe, "-hide_banner", "-y", "-loglevel", "error", "-progress", "pipe:1", "-nostats",
               "-filter_complex_threads", "2", *args, *enc, str(tmp)]
        err_file = workdir / "render.log"
        with open(err_file, "w", encoding="utf-8", errors="replace") as ef:
            proc = subprocess.Popen(cmd, cwd=str(workdir), stdout=subprocess.PIPE, stderr=ef,
                                    text=True, encoding="utf-8", errors="replace", creationflags=NOWIN)
            for line in proc.stdout:
                if should_stop():
                    proc.kill()
                    proc.wait()
                    tmp.unlink(missing_ok=True)
                    return out
                if line.startswith("out_time_us="):
                    try:
                        report(min(0.99, int(line.split("=")[1]) / 1e6 / duration))
                    except ValueError:
                        pass
            proc.wait()
        if proc.returncode == 0 and tmp.exists():
            tmp.replace(out)
            report(1.0)
            return out
        tmp.unlink(missing_ok=True)
        last_err = err_file.read_text("utf-8", errors="replace").strip()[-600:]
        if enc is not encoders[-1]:
            log(f"Encoder {enc[1]} không dùng được trên máy này → chuyển sang CPU (x264)", "warn")
    raise RenderError(f"FFmpeg lỗi: {last_err or 'không rõ'}")
