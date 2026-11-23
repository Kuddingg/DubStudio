"""Tạo giọng đọc từng câu phụ đề: Edge-TTS (miễn phí).

- Mỗi câu một file tts/0001.mp3 ...; đọc song song vài câu một lúc cho nhanh.
- Có cache: câu nào nội dung / giọng / tốc độ không đổi thì không đọc lại → sửa 1 câu chỉ đọc lại câu đó.
- Ghi tts/index.json: thời lượng audio từng câu so với khung thời gian của phụ đề (để bước Căn khớp xử lý
  và để cửa sổ Sửa phụ đề đánh dấu câu đọc bị tràn).

Lưu ý: Edge-TTS gọi dịch vụ đọc chữ của trình duyệt Microsoft Edge (không phải API chính thức).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from .log import log
from .media import NOWIN, which

EDGE_VOICES = {
    "HoaiMy · Nữ (Edge TTS)": "vi-VN-HoaiMyNeural",
    "NamMinh · Nam (Edge TTS)": "vi-VN-NamMinhNeural",
}
ALL_VOICES = dict(EDGE_VOICES)
VOICE_LABELS = list(ALL_VOICES)
CONCURRENCY = 2   # gửi nhiều hơn máy chủ Edge hay trả "No audio was received"
SAMPLE = "Xin chào, đây là giọng đọc thử của phần mềm lồng tiếng."

class TTSError(RuntimeError):
    pass


def warmup() -> None:
    """Nạp sẵn thư viện Edge-TTS (~1s trên máy yếu) để lần đọc đầu không phải chờ."""
    import edge_tts  # noqa: F401


def voice_id(label: str) -> str:
    v = ALL_VOICES.get(label)
    if not v:
        raise TTSError(f"Giọng “{label}” chưa hỗ trợ")
    return v


def rate_str(speed: float) -> str:
    pct = int(round((float(speed) - 1.0) * 100))
    return f"{pct:+d}%"


def duration(path: Path) -> float:
    exe = which("ffprobe")
    out = subprocess.run([exe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, creationflags=NOWIN, timeout=30)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


SYNTH_TIMEOUT = 30  # giây; dịch vụ đôi khi treo kết nối mà không báo lỗi


def pitch_str(hz: float) -> str:
    return f"{int(round(float(hz or 0))):+d}Hz"


async def _synth(text: str, voice: str, rate: str, out: Path, retries: int = 5, pitch: str = "+0Hz"):
    import edge_tts
    last = None
    for attempt in range(retries):
        # file tạm riêng cho từng lần thử: lần trước bị treo cũng không khóa file của lần sau
        tmp = out.with_name(f"{out.stem}.{os.getpid()}.{threading.get_ident()}.{attempt}.part")
        try:
            # câu dài cần nhiều thời gian hơn: 30s + 1s mỗi 10 ký tự
            await asyncio.wait_for(edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(tmp)),
                                   SYNTH_TIMEOUT + len(text) / 10)
            if tmp.stat().st_size < 200:
                raise TTSError("audio rỗng")
            tmp.replace(out)
            return
        except asyncio.TimeoutError:
            last = f"máy chủ không phản hồi sau {SYNTH_TIMEOUT}s"
            log(f"Tạo giọng bị treo, thử lại ({attempt + 1}/{retries})…", "warn")
        except Exception as e:  # noqa: BLE001 - lỗi mạng/dịch vụ → thử lại
            last = e
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        if attempt < retries - 1:
            await asyncio.sleep(min(8.0, 1.5 * 2 ** attempt))   # 1.5s, 3s, 6s, 8s
    raise TTSError(f"Không tạo được giọng: {last}. Kiểm tra kết nối mạng rồi thử lại")


def eff_pitch(voice: str, pitch_hz: float) -> str:
    return pitch_str(pitch_hz)


def synth_one(text: str, voice_label: str, speed: float, out: Path, pitch: float = 0) -> Path:
    """Đọc một câu (dùng cho Nghe thử và đọc lại 1 câu). Chạy đồng bộ, gọi từ thread nền."""
    out.parent.mkdir(parents=True, exist_ok=True)
    voice = voice_id(voice_label)
    asyncio.run(_synth(text, voice, rate_str(speed), out, pitch=eff_pitch(voice, pitch)))
    return out


def _key(text: str, voice: str, rate: str, pitch: str = "+0Hz") -> str:
    style = rate if pitch == "+0Hz" else f"{rate}|{pitch}"   # giữ nguyên khóa cũ khi không chỉnh cao độ
    return hashlib.sha1(f"{voice}|{style}|{text}".encode()).hexdigest()[:16]


def synth_all(cues, workdir: Path, voice_label: str, speed: float,
              report=lambda p: None, should_stop=lambda: False, pitch: float = 0) -> list[dict]:
    """cues: list Cue (start/end ms, dst = câu tiếng Việt). Trả về danh sách mục index."""
    voice, rate = voice_id(voice_label), rate_str(speed)
    pch = eff_pitch(voice, pitch)
    tdir = workdir / "tts"
    tdir.mkdir(parents=True, exist_ok=True)
    idx_file = tdir / "index.json"
    old = {}
    if idx_file.exists():
        try:
            old = {e["file"]: e for e in json.loads(idx_file.read_text("utf-8"))}
        except (ValueError, KeyError):
            old = {}

    entries, jobs = [], []
    for i, c in enumerate(cues):
        text = c.dst.strip()
        e = {"i": i, "start": c.start / 1000, "end": c.end / 1000, "text": text,
             "file": f"{i + 1:04d}.mp3", "key": _key(text, voice, rate, pch), "dur": 0.0}
        entries.append(e)
        if not text:
            continue
        prev = old.get(e["file"])
        if prev and prev.get("key") == e["key"] and (tdir / e["file"]).exists():
            e["dur"] = prev.get("dur", 0.0)
        else:
            jobs.append(e)

    reused = len([e for e in entries if e["text"]]) - len(jobs)
    if reused:
        log(f"Dùng lại {reused} câu đã đọc trước đó, đọc mới {len(jobs)} câu")

    for junk in tdir.glob("*.part"):          # dọn file tạm của lần chạy trước bị ngắt
        try:
            junk.unlink()
        except OSError:
            pass

    done = 0

    async def run(batch: list[dict], parallel: int) -> list[dict]:
        """Đọc một loạt câu; câu lỗi không làm hủy các câu khác. Trả về danh sách câu bị lỗi."""
        nonlocal done
        sem = asyncio.Semaphore(parallel)
        failed: list[dict] = []

        async def one(e):
            nonlocal done
            async with sem:
                if should_stop():
                    return
                try:
                    await _synth(e["text"], voice, rate, tdir / e["file"], pitch=pch)
                except TTSError as ex:
                    e["_err"] = str(ex)
                    failed.append(e)
                    return
                done += 1
                report(done / max(1, len(jobs)))

        await asyncio.gather(*(one(e) for e in batch))
        return failed

    if jobs:
        failed = asyncio.run(run(jobs, CONCURRENCY))
        if failed and not should_stop():
            # Máy chủ hay từ chối khi gửi dồn dập → nghỉ một chút rồi đọc lại lần lượt từng câu
            log(f"{len(failed)} câu tạo giọng lỗi, thử lại lần lượt từng câu…", "warn")
            time.sleep(3)
            failed = asyncio.run(run(failed, 1))
        if failed and not should_stop():
            nums = ", ".join(f"#{e['i'] + 1}" for e in failed[:8])
            raise TTSError(f"Không tạo được giọng cho {len(failed)} câu ({nums}): {failed[0].get('_err', '')}")
    if should_stop():
        return entries
    for e in jobs:
        e["dur"] = round(duration(tdir / e["file"]), 3)
    idx_file.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    report(1.0)
    return entries


def synth_line(workdir: Path, i: int, cue, voice_label: str, speed: float, pitch: float = 0) -> dict:
    """Đọc (lại) một câu và cập nhật index.json. Câu không đổi thì dùng lại file cũ."""
    voice, rate = voice_id(voice_label), rate_str(speed)
    pch = eff_pitch(voice, pitch)
    tdir = workdir / "tts"
    tdir.mkdir(parents=True, exist_ok=True)
    text = cue.dst.strip()
    if not text:
        raise TTSError("Câu này chưa có bản dịch để đọc")
    idx = load_index(workdir)
    e = {"i": i, "start": cue.start / 1000, "end": cue.end / 1000, "text": text,
         "file": f"{i + 1:04d}.mp3", "key": _key(text, voice, rate, pch), "dur": 0.0}
    prev = idx.get(i)
    if prev and prev.get("key") == e["key"] and (tdir / e["file"]).exists():
        e["dur"] = prev.get("dur", 0.0)
    else:
        asyncio.run(_synth(text, voice, rate, tdir / e["file"], pitch=pch))
        e["dur"] = round(duration(tdir / e["file"]), 3)
    idx[i] = e
    (tdir / "index.json").write_text(json.dumps([idx[k] for k in sorted(idx)], ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    e["path"] = str(tdir / e["file"])
    return e


def load_index(workdir: Path) -> dict[int, dict]:
    f = workdir / "tts" / "index.json"
    try:
        return {e["i"]: e for e in json.loads(f.read_text("utf-8"))}
    except (OSError, ValueError, KeyError):
        return {}


def overflow(e: dict) -> float:
    """Số giây giọng đọc dài hơn khung thời gian của câu (>0 là bị tràn)."""
    return round(e.get("dur", 0.0) - (e["end"] - e["start"]), 2)
