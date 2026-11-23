import re
from dataclasses import dataclass


@dataclass
class Cue:
    start: int  # ms
    end: int    # ms
    src: str = ""   # câu gốc (tiếng Trung)
    dst: str = ""   # bản dịch (tiếng Việt)


def ms_to_tc(ms: int) -> str:
    ms = max(0, int(ms))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


_TC = re.compile(r"(\d+):(\d{1,2}):(\d{1,2})[,.](\d{1,3})")


def tc_to_ms(tc: str) -> int:
    m = _TC.search(tc.strip())
    if not m:
        raise ValueError(f"Sai định dạng thời gian: {tc!r} (đúng: 00:00:01,500)")
    h, mi, s, ms = m.groups()
    return ((int(h) * 60 + int(mi)) * 60 + int(s)) * 1000 + int(ms.ljust(3, "0"))


def parse_srt(text: str) -> list[Cue]:
    cues = []
    for block in re.split(r"\r?\n\s*\r?\n", text.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        idx = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if idx is None:
            continue
        a, b = lines[idx].split("-->")
        cues.append(Cue(tc_to_ms(a), tc_to_ms(b), "", "\n".join(lines[idx + 1:])))
    return cues


def write_srt(cues: list[Cue], field: str = "dst") -> str:
    out = []
    for i, c in enumerate(cues, 1):
        out.append(f"{i}\n{ms_to_tc(c.start)} --> {ms_to_tc(c.end)}\n{getattr(c, field)}\n")
    return "\n".join(out)
