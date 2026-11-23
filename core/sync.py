"""Bước 3 · Căn khớp thời gian: ghép các câu giọng đọc thành MỘT track audio dài bằng video.

Với mỗi câu (theo thứ tự thời gian):
1. Khung được dùng = từ lúc câu bắt đầu (+ độ lệch) tới lúc câu kế tiếp bắt đầu → tự "mượn" khoảng lặng phía sau.
2. Vẫn thiếu chỗ → bắt đầu sớm hơn tối đa 0,3s nếu câu trước đã đọc xong.
3. Vẫn dài → tăng tốc (atempo) tối đa MAX_SPEED (Smart Voice). Quá mức đó → đánh dấu tràn để sửa tay.

Kết quả: voice.wav (mono 44.1kHz, dài bằng video) + sync.json (vị trí, tốc độ, độ tràn từng câu).
"""
from __future__ import annotations

import json
import subprocess
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from .log import log
from .media import NOWIN, which

SR = 44100
MAX_SPEED = 1.35
EARLY = 0.3      # được bắt đầu sớm hơn mốc phụ đề tối đa (giây)
GAP = 0.05       # chừa khoảng nghỉ tối thiểu giữa 2 câu


def plan(entries: list[dict], duration: float, lead: float = 0.0, smart: bool = True) -> list[dict]:
    """Tính vị trí + tốc độ cho từng câu. entries: từ tts/index.json (start, end, dur, file, text)."""
    items = sorted([e for e in entries if e.get("text") and e.get("dur")], key=lambda e: e["start"])
    out, prev_end = [], 0.0
    for k, e in enumerate(items):
        nxt = items[k + 1]["start"] + lead if k + 1 < len(items) else max(duration, e["end"] + 1.0)
        start = max(0.0, e["start"] + lead)
        # Không bao giờ đọc chồng lên câu trước: câu trước bị tràn thì câu này lùi lại cho đọc nối tiếp
        start = max(start, prev_end + GAP if out else 0.0)
        limit = max(nxt - GAP, start + 0.1)
        avail = limit - start
        if e["dur"] > avail:   # thiếu chỗ → thử bắt đầu sớm hơn một chút (nếu câu trước đã đọc xong)
            earliest = max(prev_end + GAP if out else 0.0, e["start"] + lead - EARLY, 0.0)
            start = max(earliest, min(start, limit - e["dur"]))
            avail = limit - start
        speed = 1.0
        if e["dur"] > avail > 0 and smart:
            speed = min(MAX_SPEED, e["dur"] / avail)
        play = e["dur"] / speed
        over = round(play - avail, 2) if play > avail + 0.02 else 0.0
        shift = round(start - (e["start"] + lead), 2)   # >0: bị lùi lại vì câu trước tràn
        out.append({**e, "t": round(start, 3), "speed": round(speed, 3), "play": round(play, 3),
                    "over": over, "shift": shift if shift > 0.02 else 0.0})
        prev_end = start + play
    return out


def _decode(path: Path, speed: float) -> np.ndarray:
    exe = which("ffmpeg")
    af = []
    if abs(speed - 1.0) > 0.005:
        af = ["-filter:a", f"atempo={speed:.4f}"]
    raw = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-i", str(path), *af,
                          "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, creationflags=NOWIN, timeout=120, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def build_track(workdir: Path, duration: float, lead_ms: float = 0, smart: bool = True,
                report=lambda p: None, should_stop=lambda: False) -> list[dict]:
    tdir = workdir / "tts"
    entries = json.loads((tdir / "index.json").read_text("utf-8"))
    placed = plan(entries, duration, lead_ms / 1000.0, smart)
    total = int((max(duration, max((p["t"] + p["play"] for p in placed), default=0)) + 0.5) * SR)
    track = np.zeros(total, np.float32)

    done = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [(p, pool.submit(_decode, tdir / p["file"], p["speed"])) for p in placed]
        for p, f in futs:
            if should_stop():
                pool.shutdown(cancel_futures=True)
                return placed
            pcm = f.result()
            i = int(p["t"] * SR)
            j = min(total, i + len(pcm))
            track[i:j] += pcm[: j - i]
            done += 1
            report(done / max(1, len(placed)))

    peak = float(np.max(np.abs(track))) if total else 0.0
    if peak > 0.99:   # chống vỡ tiếng khi 2 câu chồng nhau
        track *= 0.99 / peak
    with wave.open(str(workdir / "voice.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(track, -1, 1) * 32767).astype(np.int16).tobytes())
    (workdir / "sync.json").write_text(json.dumps(placed, ensure_ascii=False, indent=1), encoding="utf-8")
    sped = [p for p in placed if p["speed"] > 1.0]
    over = [p for p in placed if p["over"] > 0]
    shifted = [p for p in placed if p.get("shift", 0) > 0]
    msg = f"Căn khớp {len(placed)} câu: {len(sped)} câu tăng tốc"
    if over:
        msg += f", {len(over)} câu vẫn dài quá khung → {len(shifted)} câu sau được lùi lại để không đọc chồng " \
               f"(nên rút gọn câu #{', #'.join(str(p['i'] + 1) for p in over[:5])})"
    log(msg, "warn" if over else "ok")
    return placed
