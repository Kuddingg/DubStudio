"""Phát hành bản mới: kiểm tra → tính SHA-256 → (GitHub) tạo release + upload bộ cài / (khác) tạo latest.json.

Chạy qua publish.bat sau khi build.bat xong.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.updater import changelog_notes  # noqa: E402
from core.version import UPDATE_SOURCE, VERSION  # noqa: E402

OUT = ROOT / "build" / "installer"


def fail(msg: str):
    print(f"\n[LỖI] {msg}")
    sys.exit(1)


def main():
    exe = OUT / f"DubStudio-Setup-{VERSION}.exe"
    print(f"== Phát hành DubStudio {VERSION}")
    if not exe.exists():
        fail(f"Chưa có {exe.name}. Hãy chạy build.bat trước (sau khi đã tăng VERSION trong core/version.py).")
    notes = changelog_notes(VERSION)
    if not notes:
        fail(f"CHANGELOG.md chưa có mục '## {VERSION}'. Thêm danh sách thay đổi của bản này lên đầu file rồi chạy lại.")
    print("   Đang tính SHA-256…")
    h = hashlib.sha256()
    with open(exe, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    sha, size = h.hexdigest(), exe.stat().st_size
    notes_file = OUT / f"notes-{VERSION}.md"
    notes_file.write_text(notes + "\n", encoding="utf-8")

    if UPDATE_SOURCE.startswith("github:"):
        repo = UPDATE_SOURCE.split(":", 1)[1].strip("/")
        url = f"https://github.com/{repo}/releases/download/v{VERSION}/{exe.name}"
    else:
        url = "<DÁN LINK TẢI TRỰC TIẾP CỦA FILE BỘ CÀI VÀO ĐÂY>"
    manifest = {"version": VERSION, "notes": notes, "url": url, "size": size, "sha256": sha}
    (OUT / "latest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   Bộ cài: {exe.name} · {size / 1e6:.0f} MB · SHA-256 {sha[:16]}…")

    if not UPDATE_SOURCE.startswith("github:"):
        print("\nUPDATE_SOURCE không phải GitHub → tự đăng thủ công:")
        print(f"  1. Upload {exe.name} lên chỗ bạn chọn, lấy LINK TẢI TRỰC TIẾP.")
        print(f"  2. Mở {OUT / 'latest.json'}, thay dòng url bằng link đó.")
        print(f"  3. Upload latest.json đè lên đúng địa chỉ trong UPDATE_SOURCE ({UPDATE_SOURCE or 'chưa đặt'}).")
        return

    gh = shutil.which("gh")
    if not gh:
        fail("Chưa có GitHub CLI. Cài: winget install GitHub.cli → mở cmd mới → gh auth login → chạy lại publish.bat")
    if subprocess.run([gh, "auth", "status"], capture_output=True).returncode != 0:
        fail("Chưa đăng nhập GitHub. Mở cmd chạy: gh auth login (chọn GitHub.com → HTTPS → Login with a web browser)")
    tag = f"v{VERSION}"
    if subprocess.run([gh, "release", "view", tag, "-R", repo], capture_output=True).returncode == 0:
        fail(f"Bản {tag} đã được đăng trên {repo}. Muốn đăng bản mới hãy tăng VERSION trong core/version.py.")
    print(f"   Đang tạo release {tag} trên github.com/{repo} và upload bộ cài (có thể mất vài phút)…")
    r = subprocess.run([gh, "release", "create", tag, str(exe), str(OUT / "latest.json"), "-R", repo,
                        "--title", f"DubStudio {VERSION}", "--notes-file", str(notes_file), "--latest"])
    if r.returncode != 0:
        fail("Tạo release thất bại (xem thông báo ở trên).")
    print(f"\n✓ Đã phát hành {VERSION}. Người dùng mở app sẽ thấy thông báo cập nhật.")
    print(f"  Trang tải: https://github.com/{repo}/releases/latest")


if __name__ == "__main__":
    main()
