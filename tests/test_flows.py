"""Test luồng xử lý (nhanh, không cần mạng thật): giữ bản dịch sửa tay, tự cập nhật qua máy chủ giả lập."""
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from core import pipeline, translate, updater
from core.srt import Cue, parse_srt, write_srt


# ---------------------------------------------------------------------------- giữ bản dịch đã sửa tay
@pytest.fixture
def fake_translate(monkeypatch):
    calls = []

    def fake(srcs, preset, cfg, report=lambda p: None, should_stop=lambda: False, *a, **k):
        calls.append(list(srcs))
        return [f"DỊCH({s})" for s in srcs]

    monkeypatch.setattr(translate, "translate_all", fake)
    return calls


def _prepare(wd: Path):
    zh = ["从前", "少年", "砍柴", "有一天"]
    (wd / "sub_zh.srt").write_text(write_srt([Cue(i * 2000, i * 2000 + 1800, "", t) for i, t in enumerate(zh)], "dst"), "utf-8")
    vi = [Cue(0, 1500, "", "Ngày xưa"), Cue(2000, 3800, "", "SỬA TAY"), Cue(4000, 5800, "", ""), Cue(6000, 7800, "", "Một hôm")]
    (wd / "sub_vi.srt").write_text(write_srt(vi, "dst"), "utf-8")


def test_rerun_keeps_manual_edits_and_timing(tmp_path, fake_translate):
    _prepare(tmp_path)
    pipeline.PipelineWorker([], {"keep_translation": True}).step_translate({"workdir": str(tmp_path)}, lambda p, m=None: None)
    assert fake_translate == [["砍柴"]]                                  # chỉ dịch câu còn trống
    out = parse_srt((tmp_path / "sub_vi.srt").read_text("utf-8"))
    assert [c.dst for c in out] == ["Ngày xưa", "SỬA TAY", "DỊCH(砍柴)", "Một hôm"]
    assert out[0].end == 1500                                            # giữ thời gian đã chỉnh tay


def test_rerun_translates_all_when_keep_off(tmp_path, fake_translate):
    _prepare(tmp_path)
    pipeline.PipelineWorker([], {"keep_translation": False}).step_translate({"workdir": str(tmp_path)}, lambda p, m=None: None)
    assert len(fake_translate[0]) == 4


# ---------------------------------------------------------------------------- tự cập nhật
BLOB = b"MZ" + bytes(range(256)) * 400
SHA = hashlib.sha256(BLOB).hexdigest()


@pytest.fixture
def release_server(monkeypatch):
    state = {"digest": "sha256:" + SHA}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            port = self.server.server_address[1]
            if self.path == "/repos/me/app/releases/latest":
                body = json.dumps({"tag_name": "v9.9.9", "body": "- Mới", "assets": [
                    {"name": "Setup.exe", "size": len(BLOB), "digest": state["digest"],
                     "browser_download_url": f"http://127.0.0.1:{port}/Setup.exe"}]}).encode()
            elif self.path == "/latest.json":
                body = json.dumps({"version": "9.9.9", "notes": "n", "url": f"http://127.0.0.1:{port}/Setup.exe",
                                   "size": len(BLOB), "sha256": SHA}).encode()
            elif self.path == "/Setup.exe":
                body = BLOB
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    monkeypatch.setenv("DUBSTUDIO_GITHUB_API", base)
    yield base, state
    srv.shutdown()


def test_update_from_github_release(release_server, tmp_path):
    info = updater.check("github:me/app")
    assert info["version"] == "9.9.9" and info["sha256"] == SHA
    path = updater.download(info, dest_dir=tmp_path)
    assert path.read_bytes() == BLOB


def test_update_from_manifest(release_server):
    base, _ = release_server
    assert updater.check(f"{base}/latest.json")["version"] == "9.9.9"


def test_corrupted_download_is_rejected(release_server, tmp_path):
    _, state = release_server
    state["digest"] = "sha256:" + "0" * 64
    with pytest.raises(updater.UpdateError, match="SHA-256"):
        updater.download(updater.check("github:me/app"), dest_dir=tmp_path)
    assert not list(tmp_path.rglob("*.part"))                           # không để lại file dở


def test_missing_repo_gives_clear_error(release_server):
    with pytest.raises(updater.UpdateError, match="Chưa có bản phát hành"):
        updater.check("github:khong/co")


def test_no_update_when_same_version(monkeypatch):
    monkeypatch.setattr(updater, "fetch_latest", lambda source=None: {"version": "0.0.1"})
    assert updater.check("github:x/y") is None
