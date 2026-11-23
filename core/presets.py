"""Preset 'kịch bản dịch': prompt + thuật ngữ + bộ lọc từ."""
import json

from app.paths import PRESETS_FILE

_BASE = ("Dịch phụ đề sang tiếng Việt tự nhiên, đúng ngữ cảnh. Giữ nguyên số câu và ID. "
         "Mỗi câu dịch không dài hơn câu gốc quá 30% số âm tiết để khớp thời lượng lồng tiếng.")

DEFAULTS = [
    {"name": "Mặc định", "prompt": _BASE, "glossary": [], "filters": ""},
    {"name": "Review phim", "prompt": _BASE + " Giọng kể review phim: cuốn hút, nhịp nhanh, "
     "dùng ngôi kể thứ ba, nhấn vào cao trào và tình tiết bất ngờ.", "glossary": [], "filters": ""},
    {"name": "Kể chuyện", "prompt": _BASE + " Giọng điệu lôi cuốn, ngắt nghỉ hợp lý, dẫn dắt "
     "tạo sự tò mò. Phù hợp video hoạt hình kể chuyện ngắn.", "glossary": [], "filters": ""},
    {"name": "Tiên hiệp / Tu tiên", "prompt": _BASE + " Văn phong cổ trang tiên hiệp, dùng từ Hán Việt "
     "phù hợp (ta, ngươi, tại hạ, sư tôn...). Giữ tên cảnh giới, công pháp theo âm Hán Việt.",
     "glossary": [["师兄", "sư huynh"], ["师妹", "sư muội"], ["师尊", "sư tôn"], ["宗门", "tông môn"],
                  ["灵石", "linh thạch"], ["筑基", "Trúc Cơ"], ["金丹", "Kim Đan"]], "filters": ""},
    {"name": "Đô thị / Tổng tài", "prompt": _BASE + " Văn phong hiện đại, đời thường, xưng hô anh/em, "
     "tôi/cô theo quan hệ nhân vật.", "glossary": [], "filters": ""},
    {"name": "Hoạt hình", "prompt": _BASE + " Câu ngắn, dễ hiểu, vui tươi, phù hợp mọi lứa tuổi.",
     "glossary": [], "filters": ""},
    {"name": "Hài hước", "prompt": _BASE + " Dịch thoáng, giữ chất hài, được dùng từ lóng phổ biến "
     "của người Việt nếu hợp ngữ cảnh.", "glossary": [], "filters": ""},
    {"name": "Khoa học", "prompt": _BASE + " Văn phong khoa học phổ thông, chính xác thuật ngữ, rõ ràng.",
     "glossary": [], "filters": ""},
    {"name": "Shorts tối giản", "prompt": _BASE + " Rút gọn tối đa, mỗi câu càng ngắn càng tốt "
     "nhưng đủ ý, hợp video dọc 60 giây.", "glossary": [], "filters": ""},
]


def load() -> list[dict]:
    try:
        data = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            return data
    except (OSError, ValueError):
        pass
    return [dict(p) for p in DEFAULTS]


def save(items: list[dict]) -> None:
    PRESETS_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
