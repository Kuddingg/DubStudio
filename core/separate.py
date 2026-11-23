"""Tách giọng gốc / nhạc nền bằng Demucs (htdemucs, chế độ 2 nguồn: vocals + no_vocals).

Chạy Demucs ở process riêng (python -m demucs.separate) → không giữ RAM/VRAM của model trong app,
đọc tiến độ từ thanh tqdm của Demucs. Lần đầu Demucs tự tải model (~80MB) về máy.

Kết quả: accompaniment.wav (nhạc nền + hiệu ứng, không lời) và vocals.wav (giọng gốc) trong thư mục project.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .log import log
from .media import NOWIN, which

MODEL = "htdemucs"
_PCT = re.compile(r"(\d{1,3})%\|")
_SIZE = re.compile(r"\|\s*([\d.]+[kMG]?)/([\d.]+[kMG]?)\s*\[")     # tqdm: "| 36.1M/80.2M ["


class SeparateError(RuntimeError):
    pass


def available() -> bool:
    return importlib.util.find_spec("demucs") is not None and importlib.util.find_spec("torch") is not None


def _python() -> list[str]:
    from .runtime import python_cmd
    return python_cmd()


def _device(cfg: dict) -> list[str]:
    d = str(cfg.get("device", ""))
    if d.startswith("GPU"):
        return ["-d", "cuda"]
    if d == "CPU":
        return ["-d", "cpu"]
    return []                                    # tự động: Demucs dùng CUDA nếu có


def separate(video: str, workdir: Path, cfg: dict, has_audio: bool,
             report=lambda p, msg=None: None, should_stop=lambda: False) -> Path | None:
    acc, voc = workdir / "accompaniment.wav", workdir / "vocals.wav"
    meta = workdir / "separate.json"
    sig = {"video": video, "model": MODEL}
    if acc.exists() and meta.exists():
        try:
            if json.loads(meta.read_text("utf-8")) == sig:
                log("Dùng lại nhạc nền đã tách trước đó")
                report(1.0)
                return acc
        except ValueError:
            pass
    if not has_audio:
        log("Video không có âm thanh → bỏ qua bước tách nhạc")
        report(1.0)
        return None
    if not available():
        raise SeparateError("Chưa cài Demucs. Chạy: .venv\\Scripts\\pip install demucs soundfile "
                            "(và PyTorch phù hợp máy) rồi mở lại app")

    tmpdir = workdir / "sep_tmp"
    shutil.rmtree(tmpdir, ignore_errors=True)
    tmpdir.mkdir(parents=True)
    src = tmpdir / "input.wav"
    subprocess.run([which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", video, "-vn",
                    "-ac", "2", "-ar", "44100", str(src)], check=True, creationflags=NOWIN, timeout=600)
    report(0.03)

    cmd = [*_python(), "-m", "demucs.separate", "-n", MODEL, "--two-stems", "vocals",
           *_device(cfg), "-o", str(tmpdir / "out"), str(src)]
    log("Đang tách nhạc nền bằng Demucs…")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", creationflags=NOWIN, bufsize=1)
    tail: list[str] = []
    buf = ""
    downloading = False                          # lần đầu: Demucs (torch.hub) tải model trước khi tách
    while True:
        ch = proc.stdout.read(1)
        if not ch:
            break
        if should_stop():
            proc.kill()
            proc.wait()
            shutil.rmtree(tmpdir, ignore_errors=True)
            return None
        if ch in "\r\n":                         # tqdm cập nhật bằng \r
            if buf.strip():
                if "Downloading" in buf:
                    downloading = True
                    log("Tải model tách nhạc lần đầu (~80 MB)…")
                m = _PCT.search(buf)
                if m and downloading:
                    sz = _SIZE.search(buf)
                    extra = f" · {sz.group(1)}B / {sz.group(2)}B" if sz else ""
                    report(0.03, f"Tải model tách nhạc (lần đầu): {m.group(1)}%{extra}")
                    if int(m.group(1)) >= 100:
                        downloading = False
                        log("Đã tải xong model tách nhạc", "ok")
                elif m:
                    report(0.03 + 0.95 * int(m.group(1)) / 100)
                else:
                    tail = (tail + [buf.strip()])[-15:]
            buf = ""
        else:
            buf += ch
    proc.wait()
    out_dir = tmpdir / "out" / MODEL / "input"
    if proc.returncode != 0 or not (out_dir / "no_vocals.wav").exists():
        shutil.rmtree(tmpdir, ignore_errors=True)
        msg = "\n".join(tail[-6:])
        if "CUDA" in msg and "-d" in cmd and "cuda" in cmd:
            msg += "\n→ GPU không dùng được, chọn Thiết bị = CPU ở tab Hệ thống"
        raise SeparateError(f"Demucs lỗi: {msg or 'không rõ'}")
    shutil.move(str(out_dir / "no_vocals.wav"), acc)
    shutil.move(str(out_dir / "vocals.wav"), voc)
    shutil.rmtree(tmpdir, ignore_errors=True)
    meta.write_text(json.dumps(sig), encoding="utf-8")
    report(1.0)
    return acc
