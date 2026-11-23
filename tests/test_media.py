"""Test trên video thật (tạo bằng FFmpeg): tự dò vùng sub, OCR, render, xem thử. Chạy lâu → đánh dấu slow."""
import subprocess
import wave
from difflib import SequenceMatcher

import numpy as np
import pytest

from conftest import FFMPEG, ZH_LINES
from core import media, ocr, render
from core.srt import Cue, write_srt

pytestmark = pytest.mark.slow


def _dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout)


def test_probe(zh_video):
    info = media.probe(str(zh_video))
    assert (info["width"], info["height"]) == (960, 540) and abs(info["duration"] - 10) < 0.2


def test_detect_subtitle_region_ignores_corner_clock(zh_video):
    x, y, w, h = ocr.detect_region(str(zh_video), 960, 540, 10.0, samples=10)
    assert 0.75 < y < 0.92 and y + h > 0.92                 # dải phụ đề ở dưới, không phải đồng hồ góc trên
    assert abs((x + w / 2) - 0.5) < 0.05                    # căn giữa


def test_ocr_reads_chinese_with_correct_timing(zh_video):
    cues = ocr.extract(str(zh_video), [0.1, 0.78, 0.8, 0.2], 960, 540, 10.0, ocr.OcrOptions())
    assert len(cues) == len(ZH_LINES)
    for (s, e, text), (a, b, want) in zip(cues, ZH_LINES):
        assert abs(s - a) <= 0.3 and abs(e - b) <= 0.4
        assert SequenceMatcher(None, text, want).ratio() >= 0.8, (text, want)


def _voice_wav(path, start, end, total=10.0, sr=44100):
    t = np.arange(int(total * sr)) / sr
    v = np.where((t >= start) & (t < end), 0.5 * np.sin(2 * np.pi * 1000 * t), 0).astype(np.float32)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((v * 32767).astype(np.int16).tobytes())


def _mean_db(path, a, b):
    o = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-ss", str(a), "-to", str(b), "-i", str(path),
                        "-af", "highpass=f=800,volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float([ln.split(":")[1].split()[0] for ln in o.splitlines() if "mean_volume" in ln][0])


@pytest.fixture
def job(zh_video, tmp_path):
    (tmp_path / "sub_vi.srt").write_text(write_srt([Cue(1000, 3000, "", "Câu một"), Cue(6000, 8000, "", "Câu hai")], "dst"),
                                         "utf-8")
    _voice_wav(tmp_path / "voice.wav", 6.0, 8.0)
    return {"id": "t", "name": "zh", "path": str(zh_video), "width": 960, "height": 540, "duration": 10.0,
            "regions": [{"kind": "blur", "rect": [0.1, 0.78, 0.8, 0.2], "text": ""},
                        {"kind": "text", "rect": [0.7, 0.05, 0.25, 0.07], "text": "@kenh"}]}


CFG = {"do_sub": True, "do_dub": True, "encoder": "CPU · x264", "ratio": "Giữ nguyên", "keep_music": False,
       "vol_ai": 100, "fx_norm": False}


def test_full_render(job, tmp_path):
    out = render.render(job, {**CFG, "output": str(tmp_path / "out")}, tmp_path)
    assert out.exists() and abs(_dur(out) - 10) < 0.2
    assert _mean_db(out, 6.2, 7.8) > _mean_db(out, 3.5, 5.5) + 20        # giọng đúng chỗ, chỗ khác im


def test_preview_10s_shifts_subtitles_and_voice(job, tmp_path):
    out = render.render(job, {**CFG, "output": str(tmp_path / "out")}, tmp_path, preview=(5.0, 4.0))
    assert out.name == "preview.mp4" and abs(_dur(out) - 4) < 0.2
    ass = (tmp_path / "sub_vi.ass").read_text("utf-8-sig")
    dialog = [ln for ln in ass.splitlines() if ln.startswith("Dialogue")]
    assert len(dialog) == 1 and "0:00:01.00,0:00:03.00" in dialog[0]   # câu 6–8s gốc → 1–3s bản xem thử
    assert _mean_db(out, 1.2, 2.8) > _mean_db(out, 0.1, 0.8) + 20


def test_vertical_916_puts_subtitles_in_empty_area(job, tmp_path, monkeypatch):
    monkeypatch.setattr(render, "_target_size", lambda r, W, H: (540, 960))
    out = render.render(job, {**CFG, "do_dub": False, "ratio": "9:16 · TikTok / Shorts", "bg": "Nền mờ",
                              "output": str(tmp_path / "out")}, tmp_path)
    info = media.probe(str(out))
    assert (info["width"], info["height"]) == (540, 960)
    ass = (tmp_path / "sub_vi.ass").read_text("utf-8-sig")
    assert "PlayResY: 960" in ass                                         # phụ đề vẽ theo khung mới
