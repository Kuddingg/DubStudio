"""Danh sách video + vùng kéo thả khi trống."""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QProgressBar, QScrollArea,
                               QVBoxLayout, QWidget)

from core.media import fmt_time
from core.project import Job

from .. import icons
from ..theme import C
from ..widgets.common import ElidedLabel, button, chip, dpr, label, rounded_pixmap, set_chip, set_prop

STATUS_TONE = {"Chờ": None, "Đang xử lý": "run", "Hoàn thành": "ok", "Đã dừng": "warn", "Lỗi": "err"}
THUMB = QSize(108, 61)


def _thumb_placeholder() -> QPixmap:
    r = dpr()
    pm = QPixmap(int(THUMB.width() * r), int(THUMB.height() * r))
    pm.fill(QColor(C["input"]))
    p = QPainter(pm)
    ic = icons.pixmap("film", C["dim"], 22, 1.6)
    p.drawPixmap(int((pm.width() - ic.width()) / 2), int((pm.height() - ic.height()) / 2), ic)
    p.end()
    pm.setDevicePixelRatio(r)
    return pm


class JobRow(QFrame):
    clicked = Signal(str)
    doubleClicked = Signal(str)
    checkToggled = Signal(str, bool)

    def __init__(self, job: Job):
        super().__init__()
        self.job = job
        self.setObjectName("JobRow")
        self.setProperty("selected", "false")
        self.setCursor(Qt.PointingHandCursor)
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 10, 14, 10)
        h.setSpacing(12)

        self.chk = QCheckBox()
        self.chk.setChecked(job.checked)
        self.chk.toggled.connect(lambda v: self.checkToggled.emit(job.id, v))
        h.addWidget(self.chk)

        self.thumb = QLabel()
        self.thumb.setFixedSize(THUMB)
        self.thumb.setPixmap(rounded_pixmap(_thumb_placeholder(), THUMB.width(), THUMB.height(), 8))
        h.addWidget(self.thumb)

        mid = QVBoxLayout()
        mid.setSpacing(5)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.name = ElidedLabel(job.name)
        self.name.setStyleSheet("font-weight: 600; font-size: 13px;")
        top.addWidget(self.name, 1)
        self.status = chip("Chờ")
        top.addWidget(self.status)
        mid.addLayout(top)
        self.meta = label("Đang đọc thông tin…", "Dim")
        mid.addWidget(self.meta)
        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        bar.addWidget(self.bar, 1)
        self.pct = label("0%", "Value")
        self.pct.setFixedWidth(38)
        self.pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bar.addWidget(self.pct)
        mid.addLayout(bar)
        self.step = label("", "Dim")
        mid.addWidget(self.step)
        h.addLayout(mid, 1)
        self.refresh()

    def set_thumb(self, pm: QPixmap):
        self.thumb.setPixmap(rounded_pixmap(pm, THUMB.width(), THUMB.height(), 8))

    def set_selected(self, on: bool):
        set_prop(self, "selected", "true" if on else "false")

    def refresh(self):
        j = self.job
        if j.duration:
            parts = [fmt_time(j.duration)]
            if j.width:
                parts.append(f"{j.width}×{j.height}")
            if j.fps:
                parts.append(f"{j.fps:g} fps")
            self.meta.setText("  •  ".join(parts))
        self.bar.setValue(int(j.progress * 1000))
        self.pct.setText(f"{int(j.progress * 100)}%")
        set_chip(self.status, j.status, STATUS_TONE.get(j.status))
        self.step.setText(j.step)
        self.step.setVisible(bool(j.step))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.job.id)

    def mouseDoubleClickEvent(self, e):
        self.doubleClicked.emit(self.job.id)


class JobList(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        w = QWidget()
        self.v = QVBoxLayout(w)
        self.v.setContentsMargins(0, 0, 6, 0)
        self.v.setSpacing(8)
        self.v.addStretch()
        self.setWidget(w)

    def add_row(self, row: JobRow):
        self.v.insertWidget(self.v.count() - 1, row)

    def remove_row(self, row: JobRow):
        self.v.removeWidget(row)
        row.deleteLater()


class DropZone(QFrame):
    browse = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("DropZone")
        v = QVBoxLayout(self)
        v.setAlignment(Qt.AlignCenter)
        v.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(icons.pixmap("upload", C["accent"], 30, 1.8))
        ic.setAlignment(Qt.AlignCenter)
        v.addWidget(ic)
        t = label("Kéo thả video vào đây", "H2")
        t.setAlignment(Qt.AlignCenter)
        v.addWidget(t)
        s = label("MP4 · MKV · MOV · AVI · WEBM  —  có thể thả nhiều file cùng lúc", "Muted")
        s.setAlignment(Qt.AlignCenter)
        v.addWidget(s)
        b = button("Chọn video", "plus", "primary")
        b.clicked.connect(self.browse)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(b)
        row.addStretch()
        v.addSpacing(6)
        v.addLayout(row)
