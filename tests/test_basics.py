"""Test nhanh (không cần mạng / model): phụ đề SRT, căn khớp thời gian, bộ lọc từ, phiên bản, mã hóa key."""
import sys

import pytest

from core import secret, sync, translate, updater
from core.metadata import _no_accent
from core.srt import Cue, ms_to_tc, parse_srt, tc_to_ms, write_srt


# ---------------------------------------------------------------------------- SRT
def test_timecode_roundtrip():
    assert ms_to_tc(3_723_045) == "01:02:03,045"
    assert tc_to_ms("01:02:03,045") == 3_723_045
    assert tc_to_ms("00:00:01.5") == 1500


def test_srt_roundtrip_keeps_multiline():
    cues = [Cue(0, 1500, "", "Dòng một"), Cue(2000, 3000, "", "Hai\ndòng")]
    back = parse_srt(write_srt(cues, "dst"))
    assert [(c.start, c.end, c.dst) for c in back] == [(0, 1500, "Dòng một"), (2000, 3000, "Hai\ndòng")]


def test_parse_srt_bad_time_raises():
    with pytest.raises(ValueError):
        tc_to_ms("abc")


# ---------------------------------------------------------------------------- căn khớp thời gian
def E(s, e, d):
    return {"start": s, "end": e, "dur": d, "text": "x", "file": "f"}


def test_sync_fits_and_borrows_silence():
    p = sync.plan([E(1, 2, 2.5), E(5, 6, 1.0)], 10)
    assert p[0]["speed"] == 1.0 and p[0]["over"] == 0     # mượn khoảng lặng tới câu sau
    assert p[1]["t"] == 5.0


def test_sync_speeds_up_within_limit():
    p = sync.plan([E(1, 3, 2.8), E(3.1, 5, 1.0)], 10)
    assert 1.0 < p[0]["speed"] <= sync.MAX_SPEED and p[0]["over"] == 0


def test_sync_never_overlaps_next_line():
    p = sync.plan([E(1, 2, 3.0), E(2.1, 4, 1.0), E(4.5, 6, 1.0)], 10)
    for a, b in zip(p, p[1:]):
        assert a["t"] + a["play"] <= b["t"] + 1e-6          # không đọc chồng
    assert p[0]["over"] > 0 and p[1]["shift"] > 0            # câu tràn → câu sau lùi lại


# ---------------------------------------------------------------------------- dịch
def test_filters_parse_and_apply():
    pairs = translate.parse_filters("chết → chít, giết-tiêu diệt\nđâm => chọc")
    assert pairs == [("chết", "chít"), ("giết", "tiêu diệt"), ("đâm", "chọc")]
    assert translate.apply_filters("Hắn chết rồi, Chết thật", pairs) == "Hắn chít rồi, chít thật"


def test_gemini_chosen_model_first_then_fallbacks():
    c = translate.GeminiClient(["k"], "gemini-3.5-flash-lite")
    assert c.models[0] == "gemini-3.5-flash-lite" and len(c.models) == len(translate.GEMINI_AUTO)


def test_translate_lines_retries_missing_ids():
    class Fake:
        calls = 0

        def generate_json(self, system, user, schema=None):
            Fake.calls += 1
            import json
            lines = json.loads(user)["lines"]
            if Fake.calls == 1:
                lines = lines[:-1]                            # lần đầu bỏ sót 1 câu
            return [{"id": x["id"], "vi": "VI" + x["zh"]} for x in lines], "fake"

    out = translate.translate_lines(Fake(), "sys", [(1, "一"), (2, "二"), (3, "三")], [])
    assert out == {1: "VI一", 2: "VI二", 3: "VI三"} and Fake.calls == 2


def test_ollama_schema_conversion():
    s = translate._to_json_schema({"type": "OBJECT", "properties": {"a": {"type": "ARRAY", "items": {"type": "STRING"}}}})
    assert s == {"type": "object", "properties": {"a": {"type": "array", "items": {"type": "string"}}}}


def test_hashtag_accents_removed():
    assert _no_accent("TiếnHiệpĐỉnh") == "TienHiepDinh"


# ---------------------------------------------------------------------------- cập nhật
@pytest.mark.parametrize("remote,local,newer", [("0.3.0", "0.2.0", True), ("0.2.0", "0.2.0", False),
                                                ("0.10.0", "0.9.9", True), ("v0.2.1", "0.2.0", True),
                                                ("0.1.9", "0.2.0", False)])
def test_version_compare(remote, local, newer):
    assert updater.is_newer(remote, local) is newer


def test_changelog_has_current_version():
    from core.version import VERSION
    assert updater.changelog_notes(VERSION), f"CHANGELOG.md thiếu mục ## {VERSION}"


# ---------------------------------------------------------------------------- bảo mật key
@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI chỉ có trên Windows")
def test_dpapi_roundtrip_and_legacy_plaintext():
    enc = secret.protect("AIzaTEST\nAQ.SECOND")
    assert enc.startswith("dpapi:") and "AIzaTEST" not in enc
    assert secret.unprotect(enc) == "AIzaTEST\nAQ.SECOND"
    assert secret.unprotect("AIza_old_plain") == "AIza_old_plain"     # key cũ chưa mã hóa vẫn đọc được
    assert secret.unprotect("dpapi:QUJD") == ""                        # rác / máy khác → rỗng, không lỗi
    sec = secret.encrypt_section({"api_keys": "k1", "device": "CPU"})
    assert sec["device"] == "CPU" and secret.decrypt_section(sec)["api_keys"] == "k1"
