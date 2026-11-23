"""Tự sinh tiêu đề / mô tả / hashtag cho video đã lồng tiếng, từ nội dung phụ đề tiếng Việt."""
from __future__ import annotations

import unicodedata
from pathlib import Path

from . import translate
from .log import log
from .srt import parse_srt

GEMINI_META_SCHEMA = {
    "type": "OBJECT",
    "properties": {"title": {"type": "STRING"}, "description": {"type": "STRING"},
                   "tags": {"type": "ARRAY", "items": {"type": "STRING"}}},
    "required": ["title", "description", "tags"],
}


def _no_accent(s: str) -> str:
    """Bỏ dấu tiếng Việt (hashtag có dấu nhiều nền tảng không nhận)."""
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


def _platform(cfg: dict) -> str:
    r = str(cfg.get("ratio", ""))
    if r.startswith("9:16"):
        return "TikTok / YouTube Shorts / Reels (video dọc ngắn)"
    if r.startswith("1:1"):
        return "Facebook / Instagram (video vuông)"
    return "YouTube (video ngang)"


def generate(vi_srt: Path, cfg: dict, video_name: str) -> dict:
    lines = [c.dst.replace("\n", " ").strip() for c in parse_srt(vi_srt.read_text("utf-8"))]
    text = " ".join(t for t in lines if t)
    if len(text) < 20:
        raise RuntimeError("Phụ đề quá ít nội dung để viết tiêu đề")
    text = text[:6000]
    system = (
        "Bạn là người viết nội dung cho mạng xã hội Việt Nam. Dựa trên lời thoại của video (đã dịch sang tiếng Việt), "
        f"viết thông tin đăng video cho nền tảng {_platform(cfg)}.\n"
        "- title: tiêu đề tiếng Việt hấp dẫn, tối đa 90 ký tự, đúng với nội dung, không giật tít sai sự thật.\n"
        "- description: mô tả 2–4 câu tóm tắt nội dung, gợi tò mò, có thể kèm 1 câu kêu gọi theo dõi.\n"
        "- tags: 10–15 hashtag liên quan (tiếng Việt không dấu hoặc tiếng Anh phổ biến), mỗi tag bắt đầu bằng #, "
        "không có khoảng trắng.")
    client = translate.make_client(cfg)
    if isinstance(client, translate.OllamaClient):
        data, _ = client.generate_json(system, f"Lời thoại video:\n{text}", schema=GEMINI_META_SCHEMA)
    else:
        data, _ = client.generate_json(system, f"Lời thoại video:\n{text}", GEMINI_META_SCHEMA)
    if not isinstance(data, dict) or not data.get("title"):
        raise RuntimeError("AI không trả về đúng định dạng")
    tags = []
    for t in data.get("tags", []):
        t = "#" + _no_accent(str(t).strip().lstrip("#").replace(" ", "")).lower()
        if len(t) > 1 and t not in tags:
            tags.append(t)
    return {"title": str(data["title"]).strip(), "description": str(data.get("description", "")).strip(), "tags": tags}


def write_for(video_out: Path, vi_srt: Path, cfg: dict) -> Path | None:
    try:
        meta = generate(vi_srt, cfg, video_out.name)
    except Exception as e:  # noqa: BLE001 - không làm hỏng video đã xuất
        log(f"Không tự sinh được tiêu đề / mô tả: {e}", "warn")
        return None
    out = video_out.with_suffix(".txt")
    out.write_text(f"TIÊU ĐỀ:\n{meta['title']}\n\nMÔ TẢ:\n{meta['description']}\n\nHASHTAG:\n{' '.join(meta['tags'])}\n",
                   encoding="utf-8")
    log(f"Đã tạo tiêu đề / mô tả / hashtag → {out.name}: “{meta['title']}”", "ok")
    return out
