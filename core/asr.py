"""Nhận giọng nói → phụ đề (dùng cho video KHÔNG có phụ đề cứng), bằng faster-whisper.

- Lần đầu tự tải model về data/models/whisper (small ≈ 480MB, medium ≈ 1.5GB, large-v3 ≈ 3GB).
- GPU NVIDIA (CUDA) → float16, rất nhanh; CPU → int8.
- Bật VAD để bỏ đoạn không có tiếng nói; câu dài tự tách theo dấu câu.
"""
from __future__ import annotations

import os
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


# Tắt các cảnh báo kỹ thuật của Hugging Face (symlink, HF_TOKEN, Xet…) cho nhật ký gọn
for _k, _v in {"HF_HUB_DISABLE_SYMLINKS_WARNING": "1", "HF_HUB_DISABLE_PROGRESS_BARS": "1",
               "HF_HUB_VERBOSITY": "error", "HF_HUB_DISABLE_XET": "1", "HF_HUB_DISABLE_TELEMETRY": "1"}.items():
    os.environ.setdefault(_k, _v)

FILES = ["config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.*"]


def _root() -> Path:
    from app.paths import DATA
    r = DATA / "models" / "whisper"
    r.mkdir(parents=True, exist_ok=True)
    return r


def _dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def ensure_model(name: str, report=lambda p, msg=None: None, should_stop=lambda: False) -> str:
    """Trả về thư mục model trên máy; chưa có thì tải về, báo tiến độ theo MB."""
    import fnmatch
    import threading

    from faster_whisper.utils import _MODELS, download_model
    root = _root()
    try:
        return download_model(name, cache_dir=str(root), local_files_only=True)   # đã có sẵn → khỏi tải
    except Exception:  # noqa: BLE001
        pass
    repo = _MODELS.get(name, name)
    total = 0
    try:
        from huggingface_hub import HfApi
        info = HfApi().model_info(repo, files_metadata=True)
        total = sum(s.size or 0 for s in info.siblings if any(fnmatch.fnmatch(s.rfilename, f) for f in FILES))
    except Exception:  # noqa: BLE001 - không lấy được tổng dung lượng → vẫn tải, chỉ báo MB đã tải
        pass
    log(f"Tải model nhận giọng nói “{name}” lần đầu ({total / 1e6:.0f} MB)…" if total else
        f"Tải model nhận giọng nói “{name}” lần đầu…")
    base = _dir_size(root)
    res: dict = {}

    def work():
        try:
            res["path"] = download_model(name, cache_dir=str(root))
        except Exception as e:  # noqa: BLE001
            res["err"] = e

    th = threading.Thread(target=work, daemon=True)
    th.start()
    while th.is_alive():
        th.join(0.5)
        done = max(0, _dir_size(root) - base)
        msg = (f"Tải model nhận giọng nói {name} (lần đầu): {done / 1e6:.0f} / {total / 1e6:.0f} MB" if total
               else f"Tải model nhận giọng nói {name} (lần đầu): {done / 1e6:.0f} MB")
        report(min(0.99, done / total) if total else 0.0, msg)
        if should_stop():
            return ""                                  # luồng tải chạy nốt ở nền, lần sau dùng tiếp
    if "err" in res:
        raise RuntimeError(f"Không tải được model nhận giọng nói: {res['err']}. Kiểm tra mạng rồi thử lại")
    log(f"Đã tải xong model “{name}”", "ok")
    return res["path"]


def get_model(name: str, cfg: dict, report=lambda p, msg=None: None, should_stop=lambda: False):
    from faster_whisper import WhisperModel
    device, ctype = _device(cfg)
    key = (name, device)
    if key not in _cache:
        path = ensure_model(name, report, should_stop)
        if not path:
            return None
        log(f"Nạp model nhận giọng nói “{name}” ({'GPU' if device == 'cuda' else 'CPU'})")
        _cache.clear()
        _cache[key] = WhisperModel(path, device=device, compute_type=ctype)
    return _cache[key]


def extract_audio(video: str, out: Path) -> Path:
    subprocess.run([which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", video, "-vn",
                    "-ac", "1", "-ar", "16000", str(out)], check=True, creationflags=NOWIN, timeout=900)
    return out


def transcribe(audio: Path, duration: float, cfg: dict, report=lambda p: None,
               should_stop=lambda: False) -> list[tuple[float, float, str]]:
    name = cfg.get("asr_model") or "small"
    lang = LANG.get(str(cfg.get("src_lang", "")))
    model = get_model(name, cfg, lambda p, m=None: report(0.0, m), should_stop)
    if model is None:
        return []
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
