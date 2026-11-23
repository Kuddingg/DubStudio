"""Cấu hình chung cho bộ test.

- Mọi dữ liệu (settings, project, log, model) được chuyển vào thư mục tạm → không đụng dữ liệu thật.
- Video thử được TẠO bằng FFmpeg (không cần file mẫu nào trong repo).
- Test đánh dấu `slow` cần FFmpeg / model AI / mạng; chạy nhanh: pytest -m "not slow".
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FFMPEG = shutil.which("ffmpeg")
FONT = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "msyh.ttc"   # font có chữ Trung (Windows)


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: cần FFmpeg / model AI / mạng, chạy lâu")


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    """Dữ liệu app trỏ vào thư mục tạm cho từng test."""
    import app.paths as paths
    data = tmp_path / "data"
    for d in (data, data / "cache", data / "projects"):
        d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(paths, "DATA", data)
    monkeypatch.setattr(paths, "CACHE", data / "cache")
    monkeypatch.setattr(paths, "PROJECTS", data / "projects")
    monkeypatch.setattr(paths, "SETTINGS_FILE", data / "settings.json")
    monkeypatch.setattr(paths, "PRESETS_FILE", data / "presets.json")
    import core.project as project
    monkeypatch.setattr(project, "PROJECTS", data / "projects")
    import core.presets as presets
    monkeypatch.setattr(presets, "PRESETS_FILE", data / "presets.json")
    yield data


needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="cần FFmpeg trong PATH")

ZH_LINES = [(1.0, 3.2, "从前，在一个偏远的小山村里"), (3.6, 5.8, "住着一个名叫小林的少年"),
            (6.2, 8.4, "他每天都上山砍柴")]


@pytest.fixture(scope="session")
def zh_video(tmp_path_factory):
    """Video 10s 960x540 có phụ đề tiếng Trung in cứng ở dưới + đồng hồ ở góc trên (để test bỏ qua) + nhạc nền."""
    if FFMPEG is None or not FONT.exists():
        pytest.skip("cần FFmpeg và font Microsoft YaHei")
    d = tmp_path_factory.mktemp("media")
    font = FONT.as_posix().replace(":", r"\:")
    parts = []
    for i, (a, b, text) in enumerate(ZH_LINES):
        tf = d / f"l{i}.txt"
        tf.write_text(text, encoding="utf-8")
        parts.append(f"drawtext=fontfile='{font}':textfile='{tf.as_posix().replace(':', chr(92) + ':')}':fontsize=34:"
                     f"fontcolor=white:borderw=3:bordercolor=black:x=(w-text_w)/2:y=h-80:enable='between(t,{a},{b})'")
    vf = ",".join(parts)
    out = d / "zh.mp4"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=size=960x540:rate=25:duration=10", "-f", "lavfi", "-i", "sine=f=262:d=10",
                    "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)],
                   check=True)
    return out
