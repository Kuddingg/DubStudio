"""Dọn file thừa trong thư mục dự án (tự chạy sau build.bat và publish.bat).

    python packaging/clean.py          dọn file tạm: build/work, build/dist, __pycache__, .pytest_cache
    python packaging/clean.py --all    dọn thêm build/installer (bộ cài + zip đã đăng lên GitHub)

KHÔNG BAO GIỜ đụng tới: data/ (API key, cấu hình, model AI, nhật ký, video đang làm), .venv/, mã nguồn.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".venv", ".git", "data"}


def _size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def _targets(everything: bool) -> list[Path]:
    out = [ROOT / "build" / "work", ROOT / "build" / "dist", ROOT / ".pytest_cache"]
    if everything:
        out.append(ROOT / "build")
    for top in ROOT.iterdir():                          # __pycache__ trong mã nguồn (không vào .venv / data)
        if top.name in SKIP or not top.is_dir():
            continue
        out += [top] if top.name == "__pycache__" else list(top.rglob("__pycache__"))
    return [p for p in dict.fromkeys(out) if p.exists()]


def clean(everything: bool = False) -> int:
    freed = 0
    for p in _targets(everything):
        try:
            freed += _size(p)
            shutil.rmtree(p) if p.is_dir() else p.unlink()
        except OSError as e:                            # file đang mở (vd app đang chạy) → bỏ qua
            print(f"   Bỏ qua {p.relative_to(ROOT)}: {e.strerror}")
    print(f"   Đã dọn file thừa: {freed / 1e6:.0f} MB")
    return freed


if __name__ == "__main__":
    clean("--all" in sys.argv)
