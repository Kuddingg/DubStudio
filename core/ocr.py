"""Trích phụ đề cứng (chữ trên hình) bằng RapidOCR.

Cách làm:
1. FFmpeg cắt sẵn vùng OCR và lấy mẫu N khung/giây → đọc thẳng raw frame qua pipe (nhanh, không ghi file).
2. Khung nào gần như không đổi so với khung đã OCR trước đó → dùng lại kết quả cũ (bỏ qua OCR).
3. Gộp các khung liên tiếp có chữ giống nhau thành một câu; lọc nhiễu, nối khoảng nghỉ ngắn, thêm đệm thời gian.
"""
from __future__ import annotations

import subprocess
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import cv2
import numpy as np

from .log import log
from .media import NOWIN, which

_engine = None
_engine_gpu = None


def get_engine(use_gpu: bool = False):
    """Khởi tạo RapidOCR một lần (mất ~1–2 giây). GPU cần cài onnxruntime-gpu, lỗi thì tự về CPU."""
    global _engine, _engine_gpu
    if _engine is not None and _engine_gpu == use_gpu:
        return _engine
    from rapidocr_onnxruntime import RapidOCR
    if use_gpu:
        try:
            _engine = RapidOCR(det_use_cuda=True, cls_use_cuda=True, rec_use_cuda=True)
            _engine_gpu = True
            return _engine
        except Exception as e:  # noqa: BLE001
            log(f"OCR GPU không khả dụng, chuyển sang CPU: {e}", "warn")
    _engine = RapidOCR()
    _engine_gpu = use_gpu
    return _engine


@dataclass
class OcrOptions:
    fps: float = 5.0          # số khung lấy mẫu mỗi giây
    conf: float = 0.75        # bỏ dòng chữ có độ tin cậy thấp hơn
    sens: float = 0.25        # tỉ lệ pixel chữ thay đổi (0..1) để coi là câu mới
    merge: float = 0.75       # độ giống nhau để gộp thành cùng một câu
    gap: float = 0.3          # nối 2 câu giống nhau cách nhau ít hơn (giây)
    pad: float = 0.1          # kéo dài cuối câu thêm (giây)
    max_chars: int = 100      # câu dài hơn thì tách
    use_gpu: bool = False

    @classmethod
    def from_cfg(cls, cfg: dict) -> "OcrOptions":
        return cls(fps=float(cfg.get("ocr_fps", 5)), conf=float(cfg.get("ocr_conf", 0.75)),
                   sens=float(cfg.get("ocr_sens", 0.25)), merge=float(cfg.get("ocr_merge", 0.75)),
                   gap=float(cfg.get("ocr_gap", 0.3)), pad=float(cfg.get("ocr_pad", 0.1)),
                   max_chars=int(cfg.get("ocr_max", 100)), use_gpu=cfg.get("device") == "GPU (CUDA)")


@dataclass
class _Seg:
    start: float
    end: float
    texts: Counter = field(default_factory=Counter)
    scores: dict = field(default_factory=dict)   # biến thể chữ → độ tin cậy cao nhất từng gặp

    def add(self, text: str, score: float, count: int = 1):
        self.texts[text] += count
        self.scores[text] = max(score, self.scores.get(text, 0.0))

    @property
    def text(self) -> str:
        # Chọn bản OCR tin cậy nhất (bản đọc lỗi thường điểm thấp hơn), hòa thì lấy bản gặp nhiều hơn
        if not self.texts:
            return ""
        return max(self.texts, key=lambda k: (round(self.scores.get(k, 0.0), 3), self.texts[k]))


def similar(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _crop_box(rect, width: int, height: int):
    x, y, w, h = rect
    px = max(0, int(x * width)) // 2 * 2
    py = max(0, int(y * height)) // 2 * 2
    pw = min(width - px, int(w * width)) // 2 * 2
    ph = min(height - py, int(h * height)) // 2 * 2
    if pw < 16 or ph < 8:
        raise RuntimeError("Vùng OCR quá nhỏ")
    return px, py, pw, ph


_KERNEL = np.ones((3, 3), np.uint8)
MASK_W = 320


def text_mask(img: np.ndarray, mask_h: int) -> np.ndarray:
    """Mặt nạ 'pixel giống chữ phụ đề': sáng (trắng/vàng) và nằm sát viền tối.

    Nền chuyển động không có viền tối bao quanh nên ít ảnh hưởng → chỉ OCR lại khi chữ thật sự đổi.
    """
    gray = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (MASK_W, mask_h), interpolation=cv2.INTER_AREA)
    bright = gray > 175
    dark = cv2.dilate((gray < 80).astype(np.uint8), _KERNEL, iterations=2).astype(bool)
    return bright & dark


def read_text(engine, img: np.ndarray, conf: float) -> tuple[str, float]:
    """OCR một ảnh → (chữ đã sắp theo dòng trên→dưới, trái→phải; độ tin cậy trung bình)."""
    result, _ = engine(img)
    if not result:
        return "", 0.0
    items, scores = [], []
    for box, text, score in result:
        if float(score) < conf or not text.strip():
            continue
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append(((min(ys) + max(ys)) / 2, min(xs), max(ys) - min(ys), text.strip()))
        scores.append(float(score))
    if not items:
        return "", 0.0
    items.sort()
    lines, cur, cur_y, cur_h = [], [], None, 0
    for cy, x, h, text in items:
        if cur_y is not None and abs(cy - cur_y) > max(cur_h, h) * 0.6:
            lines.append(cur)
            cur = []
        if not cur:
            cur_y, cur_h = cy, h
        cur.append((x, text))
    lines.append(cur)
    text = " ".join("".join(t for _, t in sorted(line)) for line in lines)
    return text, sum(scores) / len(scores)


def build_cues(samples: list[tuple[float, str, float]], step: float, o: OcrOptions) -> list[tuple[float, float, str]]:
    segs: list[_Seg] = []
    cur: _Seg | None = None
    for t, text, score in samples:
        if not text:
            cur = None
            continue
        if cur is not None and similar(text, cur.text) >= o.merge and t - cur.end <= step * 1.5:
            cur.end = t + step
            cur.add(text, score)
        else:
            cur = _Seg(t, t + step)
            cur.add(text, score)
            segs.append(cur)

    # nối 2 đoạn giống nhau bị ngắt quãng ngắn (chữ nhấp nháy, OCR sót 1 khung)
    merged: list[_Seg] = []
    for s in segs:
        if merged and s.start - merged[-1].end <= o.gap and similar(s.text, merged[-1].text) >= o.merge:
            merged[-1].end = s.end
            for k, n in s.texts.items():
                merged[-1].add(k, s.scores.get(k, 0.0), n)
        else:
            merged.append(s)

    # bỏ nhiễu: chỉ xuất hiện 1 khung và quá ngắn chữ
    merged = [s for s in merged if not (s.end - s.start <= step * 1.01 and len(s.text) <= 2)]

    out: list[tuple[float, float, str]] = []
    for i, s in enumerate(merged):
        nxt = merged[i + 1].start if i + 1 < len(merged) else None
        end = s.end + o.pad
        if nxt is not None:
            end = min(end, nxt - 0.01)
        out += _split_long(s.start, max(end, s.start + 0.2), s.text, o.max_chars)
    return out


def _split_long(start: float, end: float, text: str, max_chars: int):
    if len(text) <= max_chars:
        return [(start, end, text)]
    parts, buf = [], ""
    for ch in text:
        buf += ch
        if len(buf) >= max_chars or (ch in "，。！？；,.!?;" and len(buf) >= max_chars * 0.5):
            parts.append(buf.strip())
            buf = ""
    if buf.strip():
        parts.append(buf.strip())
    total = sum(len(p) for p in parts) or 1
    out, t = [], start
    for p in parts:
        d = (end - start) * len(p) / total
        out.append((t, t + d, p))
        t += d
    return out


def extract(path: str, rect, width: int, height: int, duration: float, o: OcrOptions,
            report=lambda p: None, should_stop=lambda: False) -> list[tuple[float, float, str]]:
    exe = which("ffmpeg")
    if not exe:
        raise RuntimeError("Không tìm thấy FFmpeg")
    if not (width and height):
        raise RuntimeError("Chưa đọc được kích thước video")
    x, y, w, h = _crop_box(rect, width, height)
    engine = get_engine(o.use_gpu)
    fps = max(0.5, o.fps)
    step = 1.0 / fps
    total = max(1, int(duration * fps))
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-i", path,
           "-vf", f"fps={fps:g},crop={w}:{h}:{x}:{y}", "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NOWIN)
    frame_bytes = w * h * 3
    mask_h = max(8, int(MASK_W * h / w))
    ocr_scale = min(1.0, 960 / w)  # ảnh quá rộng thì thu nhỏ trước khi OCR cho nhanh
    samples: list[tuple[float, str]] = []
    prev_mask, prev_text, prev_score, ocr_calls, i = None, "", 0.0, 0, 0
    since_ocr, recheck = 0, max(2, int(round(fps)))
    try:
        while True:
            buf = proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            if should_stop():
                return []
            t = i * step
            i += 1
            img = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            mask = text_mask(img, mask_h)
            unchanged = (prev_mask is not None and since_ocr < recheck and
                         np.count_nonzero(mask ^ prev_mask) / max(1, np.count_nonzero(mask | prev_mask)) < o.sens)
            if mask.mean() < 0.002:
                text, score = "", 0.0          # không có gì giống chữ → khỏi OCR
                prev_mask, prev_text, prev_score = mask, "", 0.0
            elif unchanged:
                text, score = prev_text, prev_score  # chữ không đổi so với lần OCR trước
                since_ocr += 1
            else:
                # OCR lại khi chữ đổi, và định kỳ ~1 giây/lần để có thêm bản đọc mà chọn bản tin cậy nhất
                src = cv2.resize(img, None, fx=ocr_scale, fy=ocr_scale, interpolation=cv2.INTER_AREA) if ocr_scale < 1 else img
                text, score = read_text(engine, src, o.conf)
                prev_mask, prev_text, prev_score, since_ocr = mask, text, score, 0
                ocr_calls += 1
            samples.append((t, text, score))
            report(min(1.0, i / total))
    finally:
        if proc.poll() is None:
            proc.kill()
        err = proc.stderr.read().decode("utf-8", "replace").strip() if proc.stderr else ""
        proc.wait()
    if not samples and err:
        raise RuntimeError(f"FFmpeg lỗi: {err[:300]}")
    cues = build_cues(samples, step, o)
    log(f"OCR: {i} khung, chạy OCR {ocr_calls} lần, ra {len(cues)} câu")
    return cues
