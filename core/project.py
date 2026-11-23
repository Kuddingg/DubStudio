import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.paths import PROJECTS


@dataclass
class Job:
    path: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    status: str = "Chờ"          # Chờ | Đang xử lý | Hoàn thành | Đã dừng | Lỗi
    step: str = ""
    progress: float = 0.0       # 0..1
    checked: bool = True
    preview_t: float = 0.0      # giây đang xem trên canvas
    regions: list = field(default_factory=list)

    @property
    def name(self) -> str:
        return Path(self.path).name

    @property
    def workdir(self) -> Path:
        d = PROJECTS / self.id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def frame_path(self, t: float) -> Path:
        return self.workdir / f"frame_{int(t * 10):07d}.jpg"
