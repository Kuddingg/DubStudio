import json
from pathlib import Path


class Settings:
    """Lưu cấu hình theo từng section vào một file JSON."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.data: dict = {}
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}

    def section(self, name: str) -> dict:
        return dict(self.data.get(name, {}))

    def set_section(self, name: str, value: dict) -> None:
        self.data[name] = value

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
