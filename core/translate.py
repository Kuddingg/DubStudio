"""Dịch phụ đề bằng LLM (hiện hỗ trợ Gemini qua Google AI Studio API).

- Gửi theo lô (mặc định 40 câu) kèm vài câu trước làm ngữ cảnh → giữ xưng hô, mạch truyện nhất quán.
- Ép AI trả JSON đúng schema [{id, vi}] → kiểm tra đủ id, thiếu thì thử lại / chia nhỏ lô.
- Lỗi 503/500 (quá tải) → chờ rồi thử lại, sau đó chuyển model dự phòng.
- Lỗi 429/401/403 (hết quota, key sai) → chuyển sang key kế tiếp.
"""
from __future__ import annotations

import json
import random
import re
import time
import urllib.error
import urllib.request

from .log import log

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
# Thứ tự ưu tiên khi chọn "Tự động": chất lượng trước, model nhẹ làm dự phòng khi quá tải
GEMINI_AUTO = ["gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"]
GEMINI_MODELS = ["Tự động (khuyên dùng)"] + GEMINI_AUTO
REQUEST_TIMEOUT = 60  # giây; model quá tải đôi khi treo kết nối thay vì trả 503

# Nhớ model đang hết quota / quá tải (dùng chung cho mọi lần gọi trong phiên) → tạm bỏ qua, khỏi chờ vô ích
_cooldown: dict[str, float] = {}
QUOTA_COOLDOWN = 300
BUSY_COOLDOWN = 120


def _rest(model: str, seconds: float):
    _cooldown[model] = time.time() + seconds


def _ordered(models: list[str]) -> list[str]:
    now = time.time()
    ready = [m for m in models if _cooldown.get(m, 0) <= now]
    return ready + [m for m in models if m not in ready]

SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {"id": {"type": "INTEGER"}, "vi": {"type": "STRING"}},
        "required": ["id", "vi"],
    },
}


class TranslateError(RuntimeError):
    pass


class Stopped(Exception):
    pass


# ============================================================================ client
class GeminiClient:
    def __init__(self, keys: list[str], model: str = "", should_stop=lambda: False):
        self.keys = [k.strip() for k in keys if k.strip()]
        if not self.keys:
            raise TranslateError("Chưa có API key: vào tab Hệ thống → ô API key")
        self.models = [model] if model and model in GEMINI_AUTO else list(GEMINI_AUTO)
        self.key_i = 0
        self.should_stop = should_stop

    def _post(self, model: str, payload: dict, key: str) -> dict:
        req = urllib.request.Request(
            f"{GEMINI_BASE}/models/{model}:generateContent", data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": key})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
            return json.load(r)

    def _demote(self, model: str):
        """Model đang lỗi/quá tải → xếp xuống cuối, các lô sau thử model khác trước."""
        if model in self.models and len(self.models) > 1:
            self.models.remove(model)
            self.models.append(model)

    def _promote(self, model: str):
        if self.models[0] != model:
            self.models.remove(model)
            self.models.insert(0, model)
            log(f"Dùng model {model}")

    def _sleep(self, sec: float):
        end = time.time() + sec
        while time.time() < end:
            if self.should_stop():
                raise Stopped()
            time.sleep(0.2)

    def generate_json(self, system: str, user: str, schema: dict = SCHEMA):
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json",
                                 "responseSchema": schema},
        }
        rounds = 3
        for r in range(rounds):
            try:
                return self._round(payload)
            except _RoundFailed as f:
                if f.all_quota:
                    raise TranslateError("Tất cả model Gemini đều hết quota với key hiện tại: đợi vài phút, "
                                         "thêm key khác hoặc nâng gói trả phí") from None
                if r == rounds - 1:
                    raise TranslateError(f"Dịch thất bại sau {rounds} lượt thử: {f.last_err}") from None
                wait = 10 * (r + 1)
                log(f"Mọi model Gemini đều lỗi (mạng / quá tải), thử lại sau {wait}s…", "warn")
                self._sleep(wait)

    def _round(self, payload: dict):
        """Thử lần lượt các model một vòng. Thành công → (json, model); hết cách → _RoundFailed."""
        last_err = "không rõ"
        rotations = 0
        quota_models = 0
        for model in _ordered(self.models):
            cool, why = BUSY_COOLDOWN, "quá tải"
            for attempt in range(2):
                if self.should_stop():
                    raise Stopped()
                key = self.keys[self.key_i % len(self.keys)]
                try:
                    data = self._post(model, payload, key)
                except urllib.error.HTTPError as e:
                    msg = _err_msg(e)
                    last_err = f"{model}: HTTP {e.code} {msg}"
                    if e.code in (429, 401, 403) and rotations < len(self.keys) - 1:
                        log(f"Gemini key #{self.key_i % len(self.keys) + 1} lỗi {e.code}, đổi sang key kế tiếp", "warn")
                        self.key_i += 1
                        rotations += 1
                        continue
                    if e.code in (401, 403):
                        raise TranslateError(f"API key không dùng được: {msg}") from None
                    if e.code == 429:
                        cool, why = QUOTA_COOLDOWN, "hết quota"
                        quota_models += 1
                        break
                    if e.code == 404:
                        cool, why = 3600, "không có model này"
                        break
                    if e.code in (500, 502, 503, 504):
                        if attempt == 0:
                            self._sleep(2 + random.random())
                        continue
                    raise TranslateError(last_err) from None
                except (urllib.error.URLError, TimeoutError, OSError) as e:
                    last_err = f"{model}: không phản hồi / lỗi mạng ({e})"
                    if "timed out" in str(e).lower() or isinstance(e, TimeoutError):
                        why = f"không phản hồi sau {REQUEST_TIMEOUT}s"
                        break
                    self._sleep(3)
                    continue
                text = _extract_text(data)
                if text is None:
                    reason = (data.get("candidates") or [{}])[0].get("finishReason") or \
                        data.get("promptFeedback", {}).get("blockReason", "không có nội dung")
                    last_err = f"{model}: AI không trả kết quả ({reason})"
                    continue
                try:
                    parsed = json.loads(text)
                except ValueError:
                    last_err = f"{model}: JSON lỗi"
                    continue
                self._promote(model)
                return parsed, model
            _rest(model, cool)
            self._demote(model)
            log(f"Tạm bỏ qua {model} ({why}), thử model khác", "warn")
        raise _RoundFailed(last_err, quota_models == len(self.models))


class _RoundFailed(Exception):
    def __init__(self, last_err: str, all_quota: bool):
        super().__init__(last_err)
        self.last_err, self.all_quota = last_err, all_quota


def _err_msg(e: urllib.error.HTTPError) -> str:
    raw = e.read().decode("utf-8", "replace")
    try:
        return json.loads(raw)["error"]["message"][:200]
    except (ValueError, KeyError, TypeError):
        return raw[:200]


def _extract_text(data: dict) -> str | None:
    cands = data.get("candidates") or []
    if not cands:
        return None
    parts = cands[0].get("content", {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    return text or None


# ============================================================================ Ollama (chạy trên máy)
OLLAMA_URL = "http://localhost:11434"
OLLAMA_DEFAULT_MODEL = "qwen2.5:7b"
OLLAMA_SCHEMA = {   # JSON Schema chuẩn; bọc trong object vì model nhỏ làm theo mảng gốc kém ổn định hơn
    "type": "object",
    "properties": {"lines": {"type": "array", "items": {
        "type": "object", "properties": {"id": {"type": "integer"}, "vi": {"type": "string"}},
        "required": ["id", "vi"]}}},
    "required": ["lines"],
}


class OllamaClient:
    batch = 15   # model nhỏ hay bỏ sót câu khi lô dài

    def __init__(self, base_url: str = "", model: str = "", should_stop=lambda: False):
        self.base = (base_url or OLLAMA_URL).rstrip("/")
        self.model = (model or OLLAMA_DEFAULT_MODEL).strip()
        self.should_stop = should_stop

    def _req(self, path: str, payload: dict | None = None, timeout: float = 600):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base + path, data=data, method="POST" if data else "GET",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            msg = _err_msg(e)
            if e.code == 404 and "not found" in msg.lower():
                raise TranslateError(f"Ollama chưa có model “{self.model}”. Mở cmd và chạy: ollama pull {self.model}") from None
            raise TranslateError(f"Ollama lỗi HTTP {e.code}: {msg}") from None
        except (urllib.error.URLError, ConnectionError) as e:
            raise TranslateError(f"Không kết nối được Ollama tại {self.base}: hãy mở ứng dụng Ollama "
                                 f"(hoặc kiểm tra địa chỉ ở tab Hệ thống). Chi tiết: {e}") from None
        except TimeoutError:
            raise TranslateError(f"Ollama không trả lời sau {timeout:.0f}s (model quá nặng so với máy?)") from None

    def list_models(self) -> list[str]:
        return [m.get("name", "") for m in self._req("/api/tags", timeout=10).get("models", [])]

    def generate_json(self, system: str, user: str, schema: dict = SCHEMA):
        if self.should_stop():
            raise Stopped()
        lines_mode = schema is SCHEMA
        fmt = OLLAMA_SCHEMA if lines_mode else _to_json_schema(schema)
        hint = "\n\nTrả về JSON dạng {\"lines\": [{\"id\": ..., \"vi\": ...}]}." if lines_mode else "\n\nChỉ trả về JSON."
        payload = {"model": self.model, "stream": False, "format": fmt, "options": {"temperature": 0.3},
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user + hint}]}
        # lần đầu gọi, Ollama phải nạp model vào RAM/VRAM → có thể mất vài phút
        data = self._req("/api/chat", payload, timeout=600)
        text = (data.get("message") or {}).get("content", "")
        try:
            parsed = json.loads(text)
        except ValueError:
            raise TranslateError(f"Ollama ({self.model}) trả về không đúng JSON") from None
        if lines_mode and isinstance(parsed, dict):
            parsed = parsed.get("lines", [])
        return parsed, self.model


def _to_json_schema(s):
    """Schema kiểu Gemini (type viết HOA) → JSON Schema chuẩn cho Ollama."""
    if isinstance(s, dict):
        return {k: (v.lower() if k == "type" and isinstance(v, str) else _to_json_schema(v)) for k, v in s.items()}
    if isinstance(s, list):
        return [_to_json_schema(x) for x in s]
    return s


def make_client(cfg: dict, should_stop=lambda: False):
    llm = str(cfg.get("llm", "Gemini"))
    if llm.startswith("Ollama"):
        return OllamaClient(cfg.get("ollama_url", ""), cfg.get("ollama_model", ""), should_stop)
    if llm != "Gemini":
        raise TranslateError(f"AI dịch “{llm}” chưa hỗ trợ, hiện có Gemini và Ollama")
    keys = str(cfg.get("api_keys", "")).splitlines()
    model = cfg.get("gemini_model", "")
    return GeminiClient(keys, model, should_stop)


# ============================================================================ prompt
def _lang(v: str, fallback: str) -> str:
    return fallback if not v or v.startswith("Tự") else v.lower() if v.startswith("Tiếng") else v


def build_system(preset: dict, cfg: dict) -> str:
    src = _lang(cfg.get("src_lang", ""), "ngôn ngữ gốc (thường là tiếng Trung)")
    dst = _lang(cfg.get("dst_lang", ""), "tiếng Việt")
    lines = [
        f"Bạn là biên dịch viên phụ đề phim chuyên nghiệp, dịch từ {src} sang {dst}.",
        "",
        "Yêu cầu riêng của kịch bản:",
        preset.get("prompt", "").strip() or "Dịch tự nhiên, đúng ngữ cảnh.",
        "",
        "Quy tắc bắt buộc:",
        "- Dịch từng dòng trong `lines`, giữ nguyên `id`. Không gộp, không tách, không bỏ dòng nào.",
        "- `context` là các câu ngay trước đó (đã dịch) để giữ mạch truyện và xưng hô thống nhất. KHÔNG dịch lại phần context.",
        "- Phụ đề lấy bằng OCR nên có thể lỗi (chữ lặp, ký tự lạ): hãy dịch theo nghĩa đúng nhất trong ngữ cảnh.",
        "- Chỉ trả về bản dịch, không chú thích, không phiên âm, không đặt trong ngoặc kép.",
        "- Bản dịch sẽ được đọc lồng tiếng: `sec` là số giây câu đó hiện trên màn hình. Giọng đọc tiếng Việt "
        "khoảng 4–5 âm tiết/giây, nên giữ câu dịch không dài hơn khoảng 4,5 × sec âm tiết; "
        "câu gốc dài mà thời gian ngắn thì diễn đạt gọn lại nhưng giữ đủ ý.",
    ]
    gloss = [(a, b) for a, b in preset.get("glossary", []) if a and b]
    if gloss:
        lines += ["", "Thuật ngữ bắt buộc dịch đúng như sau:"] + [f"- {a} → {b}" for a, b in gloss]
    return "\n".join(lines)


# ============================================================================ filters
_SPLIT = re.compile(r"\s*(?:→|->|=>|-)\s*")


def parse_filters(text: str) -> list[tuple[str, str]]:
    pairs = []
    for item in re.split(r"[\n,]+", text or ""):
        item = item.strip()
        if not item:
            continue
        parts = _SPLIT.split(item, maxsplit=1)
        if len(parts) == 2 and parts[0]:
            pairs.append((parts[0], parts[1]))
    return pairs


def apply_filters(text: str, pairs: list[tuple[str, str]]) -> str:
    for a, b in pairs:
        text = re.sub(re.escape(a), b, text, flags=re.IGNORECASE)
    return text


# ============================================================================ translate
def _line(it: tuple) -> dict:
    d = {"id": it[0], "zh": it[1]}
    if len(it) > 2 and it[2]:
        d["sec"] = round(float(it[2]), 1)
    return d


def translate_lines(client: GeminiClient, system: str, items: list[tuple],
                    context: list[tuple[str, str]]) -> dict[int, str]:
    """Dịch một lô; items = (id, câu gốc[, số giây]). Trả về {id: bản dịch}.
    Thiếu id thì thử lại, vẫn thiếu thì chia đôi lô."""
    user = json.dumps({"context": [{"zh": z, "vi": v} for z, v in context],
                       "lines": [_line(it) for it in items]}, ensure_ascii=False)
    want = {it[0] for it in items}
    got: dict[int, str] = {}
    for _ in range(2):
        data, model = client.generate_json(system, user)
        if isinstance(data, list):
            for row in data:
                try:
                    i, vi = int(row["id"]), str(row["vi"]).strip()
                except (KeyError, TypeError, ValueError):
                    continue
                if i in want and vi:
                    got[i] = vi
        if want <= got.keys():
            return got
    missing = [it for it in items if it[0] not in got]
    if len(items) > 1 and missing:
        log(f"Thiếu {len(missing)} câu trong lô, chia nhỏ để dịch lại", "warn")
        mid = len(missing) // 2 or 1
        for part in (missing[:mid], missing[mid:]):
            if part:
                got.update(translate_lines(client, system, part, context))
        return got
    if missing:
        raise TranslateError(f"AI bỏ sót câu id={missing[0][0]}")
    return got


def translate_all(srcs: list[str], preset: dict, cfg: dict, report=lambda p: None,
                  should_stop=lambda: False, batch: int = 40, ctx_n: int = 6,
                  secs: list[float] | None = None) -> list[str]:
    """secs: số giây hiển thị của từng câu (để AI dịch vừa thời lượng lồng tiếng)."""
    client = make_client(cfg, should_stop)
    batch = min(batch, getattr(client, "batch", batch))
    system = build_system(preset, cfg)
    filters = parse_filters(preset.get("filters", ""))
    out = [""] * len(srcs)
    todo = [(i, s) for i, s in enumerate(srcs) if s.strip()]
    done = 0
    for b in range(0, len(todo), batch):
        if should_stop():
            raise Stopped()
        chunk = todo[b:b + batch]
        first = chunk[0][0]
        context = [(srcs[k], out[k]) for k in range(max(0, first - ctx_n), first) if out[k]]
        res = translate_lines(client, system, [(i + 1, s, secs[i] if secs else None) for i, s in chunk], context)
        for i, _ in chunk:
            out[i] = apply_filters(res.get(i + 1, ""), filters)
        done += len(chunk)
        report(done / max(1, len(todo)))
    return out


def translate_one(srcs: list[str], dsts: list[str], index: int, preset: dict, cfg: dict,
                  sec: float | None = None) -> str:
    """Dịch lại một câu (dùng trong cửa sổ Sửa phụ đề), có ngữ cảnh các câu trước."""
    client = make_client(cfg)
    context = [(srcs[k], dsts[k]) for k in range(max(0, index - 6), index) if dsts[k]]
    res = translate_lines(client, build_system(preset, cfg), [(index + 1, srcs[index], sec)], context)
    return apply_filters(res.get(index + 1, ""), parse_filters(preset.get("filters", "")))
