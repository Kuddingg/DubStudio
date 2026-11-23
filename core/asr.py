"""Nhận giọng nói → phụ đề (dùng cho video KHÔNG có phụ đề cứng), bằng faster-whisper.

- Lần đầu tự tải model về data/models/whisper (small ≈ 480MB, medium ≈ 1.5GB, large-v3 ≈ 3GB).
- GPU NVIDIA (CUDA) → float16, rất nhanh; CPU → int8.
- Bật VAD để bỏ đoạn không có tiếng nói; câu dài tự tách theo dấu câu.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .log import log
from .media import NOWIN, which
from .ocr import _split_long

MODELS = ["small", "medium", "large-v3"]
LANG = {"Tiếng Trung": "zh", "Tiếng Anh": "en", "Tiếng Hàn": "ko", "Tiếng Nhật": "ja"}
PROMPT = {"zh": "以下是普通话的句子，使用简体中文和标点符号。"}   # gợi ý Whisper ra chữ giản thể + có dấu câu
MAX_CHARS = {"zh": 28, "ja": 28, "ko": 40}
_cache: dict = {}


def _device(cfg: dict) -> tuple[str, str]:
    d = str(cfg.get("device", ""))
    if d == "CPU":
        return "cpu", "int8"
    try:
        import ctranslate2
        has_cuda = ctranslate2.get_cuda_device_count() > 0
    except Exception:  # noqa: BLE001
        has_cuda = False
    if d.startswith("GPU") and not has_cuda:
        log("Chọn GPU nhưng CTranslate2 không thấy CUDA → nhận giọng nói chạy CPU", "warn")
    return ("cuda", "float16") if has_cuda else ("cpu", "int8")


def get_model(name: str, cfg: dict):
    from faster_whisper import WhisperModel

    from app.paths import DATA
    device, ctype = _device(cfg)
    key = (name, device)
    if key not in _cache:
        root = DATA / "models" / "whisper"
        root.mkdir(parents=True, exist_ok=True)
        log(f"Nạp model nhận giọng nói “{name}” ({device}); lần đầu sẽ tải về máy, có thể mất vài phút…")
        _cache.clear()
        _cache[key] = WhisperModel(name, device=device, compute_type=ctype, download_root=str(root))
    return _cache[key]


def extract_audio(video: str, out: Path) -> Path:
    subprocess.run([which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", video, "-vn",
                    "-ac", "1", "-ar", "16000", str(out)], check=True, creationflags=NOWIN, timeout=900)
    return out


def transcribe(audio: Path, duration: float, cfg: dict, report=lambda p: None,
               should_stop=lambda: False) -> list[tuple[float, float, str]]:
    name = cfg.get("asr_model") or "small"
    lang = LANG.get(str(cfg.get("src_lang", "")))
    model = get_model(name, cfg)
    segments, info = model.transcribe(str(audio), language=lang, vad_filter=True, beam_size=5, word_timestamps=True,
                                      initial_prompt=PROMPT.get(lang or "", None), condition_on_previous_text=False)
    if not lang:
        log(f"Tự nhận diện ngôn ngữ: {info.language} ({info.language_probability:.0%})")
        lang = info.language
    limit = MAX_CHARS.get(lang, 60)
    cues: list[tuple[float, float, str]] = []
    for seg in segments:                       # generator: nhận dần từng đoạn → báo tiến độ được
        if should_stop():
            return []
        if seg.words:
            cues += _group_words(seg.words, limit)
        elif seg.text.strip():
            cues += _split_long(seg.start, seg.end, seg.text.strip(), limit)
        report(min(0.99, seg.end / max(duration, 1.0)))
    report(1.0)
    if lang == "zh":   # Whisper hay ra dấu câu nửa độ rộng cho tiếng Trung → đổi về dấu chuẩn
        tbl = str.maketrans({",": "，", "?": "？", "!": "！", ";": "；", ":": "："})
        cues = [(s, e, t.translate(tbl)) for s, e, t in cues]
    return cues


_END = tuple("。！？!?.")
_SOFT = tuple("，,；;：:")
PAUSE = 0.6   # khoảng lặng giữa 2 chữ (giây) → coi là sang câu mới


def _group_words(words, limit: int) -> list[tuple[float, float, str]]:
    """Ghép từng chữ (có thời gian chính xác) thành câu phụ đề: ngắt khi gặp khoảng lặng, dấu câu, hoặc quá dài."""
    out, buf = [], []

    def flush():
        text = "".join(w.word for w in buf).strip()
        if text:
            out.append((round(buf[0].start, 2), round(buf[-1].end, 2), text))
        buf.clear()

    for w in words:
        if buf and w.start - buf[-1].end > PAUSE:
            flush()
        buf.append(w)
        text = "".join(x.word for x in buf).strip()
        if text.endswith(_END) or len(text) >= limit or (text.endswith(_SOFT) and len(text) >= limit * 0.6):
            flush()
    flush()
    return out
