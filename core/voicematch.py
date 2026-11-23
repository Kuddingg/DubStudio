"""Tìm giọng có sẵn (Edge) giống giọng trong video mẫu nhất, kèm cao độ + tốc độ gợi ý.

1. Cắt đoạn mẫu → tách giọng khỏi nhạc (Demucs, nếu có) → nhận giọng nói (Whisper) lấy nội dung + số âm tiết.
2. Đo giọng mẫu: cao độ trung vị (F0), độ lên xuống (bán cung), tốc độ nói (âm tiết/giây).
3. Mỗi giọng: đọc đúng nội dung đó → đo → dò cao độ (Hz) cho F0 khớp → tính tốc độ cho khớp nhịp nói.
4. Xếp hạng theo độ lệch cao độ + độ lên xuống.

Chỉ đo được cao độ / nhịp / tốc độ; màu giọng và giọng vùng miền vẫn cần người nghe so sánh.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import numpy as np

from . import asr, separate, tts
from .log import log
from .media import NOWIN, which

FALLBACK_TEXT = ("Xin chào các bạn, hôm nay chúng ta sẽ cùng nhau tìm hiểu một câu chuyện rất thú vị "
                 "đã xảy ra ở một ngôi làng nhỏ ven sông.")


def load_pcm(path: Path, sr: int = 16000) -> np.ndarray:
    raw = subprocess.run([which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", str(path), "-ac", "1",
                          "-ar", str(sr), "-f", "s16le", "-"], capture_output=True, check=True,
                         creationflags=NOWIN).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def pitch_stats(x: np.ndarray, sr: int = 16000) -> dict:
    """F0 trung vị (Hz) + độ lên xuống (bán cung p10–p90), ước lượng bằng tự tương quan từng khung 40ms."""
    fl, hop = int(0.04 * sr), int(0.01 * sr)
    win = np.hanning(fl)
    f0s = []
    lo, hi = sr // 400, sr // 70                       # 70–400 Hz
    for i in range(0, len(x) - fl, hop):
        fr = x[i:i + fl] * win
        if float(np.sqrt(np.mean(fr ** 2))) < 0.01:
            continue
        ac = np.correlate(fr, fr, "full")[fl - 1:]
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] / (ac[0] + 1e-9) > 0.45:
            f0s.append(sr / k)
    if len(f0s) < 20:
        raise RuntimeError("Đoạn mẫu quá ít tiếng nói để đo, hãy chọn đoạn có người nói rõ")
    f0 = np.array(f0s)
    f0 = f0[(f0 > np.percentile(f0, 5)) & (f0 < np.percentile(f0, 95))]
    semis = 12 * np.log2(f0 / np.median(f0))
    return {"f0": float(np.median(f0)), "range": float(np.percentile(semis, 90) - np.percentile(semis, 10))}


def active_time(x: np.ndarray, sr: int = 16000) -> float:
    """Thời gian thực sự có tiếng nói (bỏ khoảng lặng đầu/cuối và chỗ ngắt nghỉ) → đo tốc độ nói công bằng."""
    hop = int(0.02 * sr)
    rms = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2)) for i in range(0, len(x) - hop, hop)])
    if not len(rms):
        return 0.0
    thr = max(0.01, float(np.percentile(rms, 95)) * 0.1)
    return float(np.sum(rms > thr)) * 0.02


def syllables(text: str) -> int:
    return len(re.findall(r"\w+", text))


def match(video: str, start: float, length: float, workdir: Path, cfg: dict,
          report=lambda p, msg="": None, should_stop=lambda: False) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    clip = workdir / "sample.wav"
    subprocess.run([which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.2f}",
                    "-t", f"{length:.2f}", "-i", video, "-vn", "-ac", "2", "-ar", "44100", str(clip)],
                   check=True, creationflags=NOWIN, timeout=300)
    report(0.03, "Tách giọng khỏi nhạc nền…")
    voice_wav = clip
    if separate.available():
        separate.separate(str(clip), workdir, cfg, True, lambda p, m=None: report(0.03 + 0.37 * p, m or "Tách giọng khỏi nhạc nền…"),
                          should_stop)
        if (workdir / "vocals.wav").exists():
            voice_wav = workdir / "vocals.wav"
    if should_stop():
        return {}

    report(0.42, "Nghe nội dung giọng mẫu…")
    cues = asr.transcribe(asr.extract_audio(str(voice_wav), workdir / "asr.wav"), length,
                          {**cfg, "src_lang": "Tự nhận diện"}, lambda p, m=None: report(0.42 + 0.18 * p, m or "Nghe nội dung giọng mẫu…"),
                          should_stop)
    text = " ".join(t for _, _, t in cues).strip()
    talk = sum(e - s for s, e, _ in cues)
    viet = bool(re.search(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", text.lower()))
    pcm = load_pcm(voice_wav)
    target = pitch_stats(pcm)
    act = active_time(pcm)
    target["rate"] = syllables(text) / act if (viet and talk > 2 and act > 2) else None
    ref = text if viet and len(text) > 20 else FALLBACK_TEXT
    if len(ref) > 160:                                 # đủ để đo, đọc nhanh hơn, ít lỗi mạng hơn
        ref = ref[:160].rsplit(" ", 1)[0]
    log(f"Giọng mẫu: cao độ {target['f0']:.0f} Hz, lên xuống {target['range']:.1f} bán cung"
        + (f", tốc độ {target['rate']:.2f} âm tiết/giây" if target["rate"] else " (mẫu không phải tiếng Việt → không so tốc độ)"))

    results = []
    voices = list(tts.EDGE_VOICES)
    for vi_, label in enumerate(voices):
        if should_stop():
            return {}
        base = 0.62 + 0.36 * vi_ / len(voices)
        report(base, f"Thử giọng {label.split(' ·')[0]}…")
        p0 = workdir / f"{tts.voice_id(label)}_0.mp3"
        tts.synth_one(ref, label, 1.0, p0)
        s0 = pitch_stats(load_pcm(p0))
        # Edge: +1 Hz trong tham số ≈ +1.3 Hz cao độ thực (đo thực nghiệm) → ước lượng rồi đo lại 1 lần
        hz = int(round(max(-50, min(50, (target["f0"] - s0["f0"]) / 1.3)) / 5) * 5)
        best = (hz, s0)
        if hz:
            p1 = workdir / f"{tts.voice_id(label)}_{hz}.mp3"
            tts.synth_one(ref, label, 1.0, p1, hz)
            s1 = pitch_stats(load_pcm(p1))
            best = (hz, s1)
            if abs(s1["f0"] - target["f0"]) > 5 and abs(s1["f0"] - s0["f0"]) > 1:   # chỉnh thêm 1 lần cho sát
                k = (s1["f0"] - s0["f0"]) / hz
                hz2 = int(round(max(-50, min(50, hz + (target["f0"] - s1["f0"]) / k)) / 5) * 5)
                if hz2 != hz:
                    p2 = workdir / f"{tts.voice_id(label)}_{hz2}.mp3"
                    tts.synth_one(ref, label, 1.0, p2, hz2)
                    s2 = pitch_stats(load_pcm(p2))
                    if abs(s2["f0"] - target["f0"]) < abs(s1["f0"] - target["f0"]):
                        best = (hz2, s2)
        hz, st = best
        sample = workdir / f"{tts.voice_id(label)}_{hz}.mp3" if hz else p0
        speed = 1.0
        if target["rate"]:
            rate = syllables(ref) / max(0.5, active_time(load_pcm(sample)))
            speed = round(max(0.8, min(1.3, target["rate"] / rate)) / 0.05) * 0.05
        diff = abs(12 * np.log2(st["f0"] / target["f0"])) + 0.5 * abs(st["range"] - target["range"])
        results.append({"voice": label, "pitch": hz, "speed": round(speed, 2), "f0": round(st["f0"], 1),
                        "range": round(st["range"], 1), "score": round(float(diff), 2), "sample": str(sample)})
    results.sort(key=lambda r: r["score"])
    out_sample = workdir / "mau_giong_goc.mp3"
    subprocess.run([which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(voice_wav), "-b:a", "128k",
                    str(out_sample)], creationflags=NOWIN)
    report(1.0, "Xong")
    return {"target": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in target.items()},
            "text": ref, "results": results, "sample": str(out_sample)}


def cleanup(workdir: Path):
    shutil.rmtree(workdir, ignore_errors=True)
