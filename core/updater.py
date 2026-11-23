"""Tự cập nhật: kiểm tra bản mới → tải bộ cài (kiểm tra toàn vẹn) → chạy cài đè → app tự mở lại.

Nguồn (core/version.py → UPDATE_SOURCE):
  "github:owner/repo"  → GitHub Releases (bản mới nhất; tag dạng v0.3.0; asset .exe; ghi chú = nội dung release)
  "https://…/latest.json" → manifest: {"version", "notes", "url", "size", "sha256"}
Không gửi thông tin cá nhân nào: chỉ một yêu cầu GET với User-Agent chung "DubStudio-updater".
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from .runtime import FROZEN, RES_DIR
from .version import UPDATE_SOURCE, VERSION

UA = {"User-Agent": "DubStudio-updater", "Accept": "application/json"}
# Biến môi trường ghi đè nguồn (để test bản .exe với máy chủ thử mà không sửa code)
UPDATE_SOURCE = os.environ.get("DUBSTUDIO_UPDATE_SOURCE") or UPDATE_SOURCE


class UpdateError(RuntimeError):
    pass


def parse_ver(v: str) -> tuple:
    nums = re.findall(r"\d+", str(v))
    return tuple(int(x) for x in nums[:4]) or (0,)


def is_newer(remote: str, local: str = VERSION) -> bool:
    return parse_ver(remote) > parse_ver(local)


def configured() -> bool:
    return bool(UPDATE_SOURCE.strip())


def _get_json(url: str, timeout: float):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise UpdateError("Chưa có bản phát hành nào (hoặc repo đang để Private)") from None
        if e.code == 403:
            raise UpdateError("Máy chủ tạm từ chối (giới hạn số lần kiểm tra), thử lại sau") from None
        raise UpdateError(f"Lỗi máy chủ cập nhật: HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise UpdateError(f"Không kết nối được máy chủ cập nhật: {e}") from None
    except ValueError:
        raise UpdateError("Dữ liệu cập nhật không đúng định dạng") from None


def fetch_latest(source: str | None = None, timeout: float = 15) -> dict:
    """Thông tin bản mới nhất: {"version", "notes", "url", "size", "sha256"}."""
    source = (UPDATE_SOURCE if source is None else source).strip()
    if not source:
        raise UpdateError("Chưa cấu hình nguồn cập nhật (core/version.py → UPDATE_SOURCE)")
    if source.startswith("github:"):
        repo = source.split(":", 1)[1].strip("/")
        base = os.environ.get("DUBSTUDIO_GITHUB_API", "https://api.github.com")   # đổi được để test
        data = _get_json(f"{base}/repos/{repo}/releases/latest", timeout)
        asset = next((a for a in data.get("assets", []) if str(a.get("name", "")).lower().endswith(".exe")), None)
        if not asset:
            raise UpdateError("Bản phát hành mới nhất không có file bộ cài .exe")
        digest = str(asset.get("digest") or "")
        return {"version": str(data.get("tag_name", "")).lstrip("vV"), "notes": data.get("body") or "",
                "url": asset["browser_download_url"], "size": int(asset.get("size") or 0),
                "sha256": digest.split(":", 1)[1] if digest.startswith("sha256:") else ""}
    data = _get_json(source, timeout)
    for k in ("version", "url"):
        if not data.get(k):
            raise UpdateError(f"Manifest thiếu trường “{k}”")
    return {"version": str(data["version"]).lstrip("vV"), "notes": data.get("notes", ""), "url": data["url"],
            "size": int(data.get("size") or 0), "sha256": str(data.get("sha256") or "").lower()}


def check(source: str | None = None) -> dict | None:
    """Có bản mới hơn bản đang chạy → trả thông tin; không có → None."""
    info = fetch_latest(source)
    return info if is_newer(info["version"]) else None


def download(info: dict, report=lambda done, total: None, should_stop=lambda: False,
             dest_dir: Path | None = None) -> Path | None:
    dest_dir = Path(dest_dir or tempfile.gettempdir()) / "DubStudio-update"
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^\w.\-]", "_", Path(urllib.request.urlparse(info["url"]).path).name or "DubStudio-Setup.exe")
    out, part = dest_dir / name, dest_dir / (name + ".part")
    h = hashlib.sha256()
    try:
        req = urllib.request.Request(info["url"], headers={"User-Agent": UA["User-Agent"]})
        with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length") or info.get("size") or 0)
            done = 0
            while True:
                if should_stop():
                    f.close()
                    part.unlink(missing_ok=True)
                    return None
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                report(done, total)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        part.unlink(missing_ok=True)
        raise UpdateError(f"Tải bản cập nhật bị lỗi: {e}") from None
    if info.get("size") and done != info["size"]:
        part.unlink(missing_ok=True)
        raise UpdateError(f"File tải về không đủ ({done} / {info['size']} byte), hãy thử lại")
    if info.get("sha256") and h.hexdigest().lower() != info["sha256"].lower():
        part.unlink(missing_ok=True)
        raise UpdateError("File tải về bị hỏng hoặc không khớp mã kiểm tra (SHA-256), đã hủy để an toàn")
    part.replace(out)
    return out


def launch_installer(path: Path) -> None:
    """Chạy bộ cài ở chế độ hiện tiến độ, không hỏi gì; bộ cài tự đóng app cũ và mở lại app mới khi xong."""
    flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0       # DETACHED_PROCESS | NEW_PROCESS_GROUP
    subprocess.Popen([str(path), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                     creationflags=flags, close_fds=True)


def can_self_install() -> bool:
    """Chỉ bản đã cài (.exe) mới tự cài đè được; chạy từ mã nguồn thì chỉ tải về."""
    return FROZEN


# ---------------------------------------------------------------------------- "Có gì mới"
def changelog_notes(version: str = VERSION) -> str:
    """Lấy mục `## <version>` trong CHANGELOG.md (đóng gói kèm app)."""
    f = RES_DIR / "CHANGELOG.md"
    try:
        text = f.read_text("utf-8")
    except OSError:
        return ""
    m = re.search(rf"^##\s*v?{re.escape(version)}\b.*?$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""
