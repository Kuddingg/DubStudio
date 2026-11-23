"""Tiện ích FFmpeg/ffprobe."""
import json
import os
import shutil
import subprocess

NOWIN = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def which(name: str):
    return shutil.which(name)


def probe(path: str) -> dict:
    exe = which("ffprobe")
    if not exe:
        raise RuntimeError("Không tìm thấy ffprobe (cài FFmpeg và thêm vào PATH)")
    out = subprocess.run(
        [exe, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate:format=duration", "-of", "json", path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=NOWIN, timeout=30,
    )
    data = json.loads(out.stdout or "{}")
    stream = (data.get("streams") or [{}])[0]
    fps = 0.0
    try:
        num, den = stream.get("r_frame_rate", "0/1").split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except ValueError:
        pass
    return {
        "duration": float(data.get("format", {}).get("duration", 0) or 0),
        "width": int(stream.get("width", 0) or 0),
        "height": int(stream.get("height", 0) or 0),
        "fps": round(fps, 2),
    }


def grab_frame(path: str, t: float, out: str) -> str:
    exe = which("ffmpeg")
    if not exe:
        raise RuntimeError("Không tìm thấy FFmpeg")
    subprocess.run(
        [exe, "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, t):.2f}", "-i", path,
         "-frames:v", "1", "-q:v", "3", "-y", out],
        capture_output=True, creationflags=NOWIN, timeout=60, check=True,
    )
    return out


def fmt_time(sec: float) -> str:
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
