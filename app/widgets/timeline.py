"""Dòng thời gian phụ đề: sóng âm + các khối câu; kéo khối để dời câu, kéo mép để chỉnh bắt đầu / kết thúc.

- Bấm vào chỗ trống → tua video tới đó.  Bấm vào khối → chọn câu.
- Lăn chuột → cuộn ngang;  Ctrl + lăn → phóng to / thu nhỏ (3 giây … 5 phút trên màn hình).
- Câu không được kéo chồng lên câu bên cạnh, dài tối thiểu 0,2 giây.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .. import theme
from ..theme import C

EDGE = 6          # px: vùng bấm để kéo mép
MIN_LEN = 200     # ms: câu ngắn nhất


def waveform_peaks(path: str, rate: int = 100) -> np.ndarray:
    """Biên độ đỉnh của âm thanh, `rate` điểm mỗi giây (0..1). Chạy ở luồng nền."""
    import subprocess

    from core.media import NOWIN, which
    sr = 8000
    raw = subprocess.run([which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", path, "-vn", "-ac", "1",
                          "-ar", str(sr), "-f", "s16le", "-"], capture_output=True, creationflags=NOWIN, timeout=600).stdout
    x = np.abs(np.frombuffer(raw, np.int16).astype(np.float32)) / 32768
    step = sr // rate
    n = len(x) // step
    if n == 0:
        return np.zeros(0, np.float32)
    peaks = x[: n * step].reshape(n, step).max(axis=1)
    top = float(np.percentile(peaks, 99)) or 1.0
    return np.clip(peaks / top, 0, 1)


class Timeline(QWidget):
    seek = Signal(int)              # ms
    cueSelected = Signal(int)
    editStarted = Signal()          # trước khi kéo (để lưu bước hoàn tác)
    cueChanged = Signal(int)        # sau khi kéo xong

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(96)
        self.setMouseTracking(True)
        self.setCursor(Qt.ArrowCursor)
        self.cues: list = []
        self.peaks = np.zeros(0, np.float32)
        self.peak_rate = 100
        self.duration = 0
        self.pos_ms = 0
        self.span = 20000           # ms hiển thị
        self.view_start = 0
        self.selected = -1
        self._drag = None           # (mode, idx, x0, start0, end0)

    # ---------------------------------------------------------------- dữ liệu
    def set_cues(self, cues: list):
        self.cues = cues
        self.update()

    def set_peaks(self, peaks: np.ndarray, rate: int = 100):
        self.peaks, self.peak_rate = peaks, rate
        self.update()

    def set_duration(self, ms: int):
        self.duration = max(ms, 1)
        self.update()

    def set_position(self, ms: int, follow: bool = True):
        self.pos_ms = ms
        if follow and self._drag is None and not (self.view_start <= ms <= self.view_start + self.span * 0.9):
            self.view_start = max(0, ms - self.span // 5)
        self.update()

    def set_selected(self, i: int, center: bool = True):
        self.selected = i
        if center and 0 <= i < len(self.cues):
            c = self.cues[i]
            if not (self.view_start <= c.start and c.end <= self.view_start + self.span):
                self.view_start = max(0, c.start - self.span // 4)
        self.update()

    # ---------------------------------------------------------------- toạ độ
    def _x(self, ms: float) -> float:
        return (ms - self.view_start) / self.span * self.width()

    def _ms(self, x: float) -> int:
        return int(self.view_start + x / max(1, self.width()) * self.span)

    def _hit(self, x: float, y: float):
        top, bot = self._cue_band()
        if not (top <= y <= bot):
            return None
        for i, c in enumerate(self.cues):
            x0, x1 = self._x(c.start), self._x(c.end)
            if x0 - EDGE <= x <= x1 + EDGE:
                if abs(x - x0) <= EDGE:
                    return "left", i
                if abs(x - x1) <= EDGE:
                    return "right", i
                if x0 <= x <= x1:
                    return "move", i
        return None

    def _cue_band(self):
        return 22.0, self.height() - 8.0

    # ---------------------------------------------------------------- vẽ
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#07090D"))
        f = QFont(theme.FONT)
        f.setPixelSize(10)
        p.setFont(f)
        # thước thời gian
        step = next(s for s in (500, 1000, 2000, 5000, 10000, 30000, 60000) if self.span / s <= 14)
        t = (self.view_start // step) * step
        while t <= self.view_start + self.span:
            x = self._x(t)
            p.setPen(QPen(QColor(255, 255, 255, 24)))
            p.drawLine(QPointF(x, 16), QPointF(x, h))
            p.setPen(QColor(C["dim"]))
            s = t // 1000
            p.drawText(QPointF(x + 3, 11), f"{s // 60}:{s % 60:02d}" + (f".{(t % 1000) // 100}" if step < 1000 else ""))
            t += step
        top, bot = self._cue_band()
        mid = (top + bot) / 2
        # sóng âm
        if len(self.peaks):
            p.setPen(QPen(QColor(124, 92, 255, 110), 1))
            for x in range(w):
                a, b = self._ms(x), self._ms(x + 1)
                i0, i1 = int(a * self.peak_rate / 1000), max(int(a * self.peak_rate / 1000) + 1, int(b * self.peak_rate / 1000))
                if i0 >= len(self.peaks) or i1 <= 0:
                    continue
                v = float(self.peaks[max(0, i0):min(len(self.peaks), i1)].max())
                hh = v * (bot - top) / 2
                p.drawLine(QPointF(x + 0.5, mid - hh), QPointF(x + 0.5, mid + hh))
        # các câu
        fm = QFontMetrics(f)
        for i, c in enumerate(self.cues):
            x0, x1 = self._x(c.start), self._x(c.end)
            if x1 < 0 or x0 > w:
                continue
            sel = i == self.selected
            col = QColor(C["amber"] if sel else C["cyan"])
            fill = QColor(col)
            fill.setAlpha(90 if sel else 45)
            r = QRectF(x0, top + 6, max(2.0, x1 - x0), bot - top - 12)
            p.setPen(QPen(col, 2 if sel else 1))
            p.setBrush(fill)
            p.drawRoundedRect(r, 4, 4)
            p.setPen(QColor("#FFFFFF"))
            txt = (c.dst or c.src or "").replace("\n", " ")
            p.drawText(r.adjusted(5, 2, -4, -2), Qt.AlignLeft | Qt.AlignVCenter,
                       fm.elidedText(f"{i + 1}. {txt}", Qt.ElideRight, int(r.width()) - 8))
        # đầu phát
        x = self._x(self.pos_ms)
        p.setPen(QPen(QColor(C["red"]), 2))
        p.drawLine(QPointF(x, 14), QPointF(x, h))

    # ---------------------------------------------------------------- chuột
    def mouseMoveEvent(self, e):
        x = e.position().x()
        if self._drag:
            mode, i, x0, s0, e0 = self._drag
            d = int((x - x0) / max(1, self.width()) * self.span)
            prev_end = self.cues[i - 1].end if i > 0 else 0
            next_start = self.cues[i + 1].start if i + 1 < len(self.cues) else (self.duration or 10 ** 9)
            c = self.cues[i]
            if mode == "move":
                d = max(prev_end - s0, min(next_start - e0, d))
                c.start, c.end = s0 + d, e0 + d
            elif mode == "left":
                c.start = max(prev_end, min(e0 - MIN_LEN, s0 + d))
            else:
                c.end = min(next_start, max(s0 + MIN_LEN, e0 + d))
            c.start, c.end = int(c.start) // 10 * 10, int(c.end) // 10 * 10
            self.update()
            return
        hit = self._hit(x, e.position().y())
        self.setCursor(Qt.SizeHorCursor if hit and hit[0] != "move" else
                       Qt.OpenHandCursor if hit else Qt.PointingHandCursor)

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        x = e.position().x()
        hit = self._hit(x, e.position().y())
        if hit:
            mode, i = hit
            self.selected = i
            self.cueSelected.emit(i)
            self.editStarted.emit()
            c = self.cues[i]
            self._drag = (mode, i, x, c.start, c.end)
            if mode == "move":
                self.setCursor(Qt.ClosedHandCursor)
        else:
            self.seek.emit(max(0, self._ms(x)))
        self.update()

    def mouseReleaseEvent(self, e):
        if self._drag:
            mode, i, _x, s0, e0 = self._drag
            self._drag = None
            c = self.cues[i]
            if (c.start, c.end) != (s0, e0):
                self.cueChanged.emit(i)
            self.setCursor(Qt.OpenHandCursor)

    def wheelEvent(self, e):
        dy = e.angleDelta().y()
        if e.modifiers() & Qt.ControlModifier:           # phóng to / thu nhỏ quanh vị trí chuột
            anchor = self._ms(e.position().x())
            frac = e.position().x() / max(1, self.width())
            self.span = int(min(300000, max(3000, self.span * (0.8 if dy > 0 else 1.25))))
            self.view_start = max(0, int(anchor - frac * self.span))
        else:                                            # cuộn ngang
            self.view_start = max(0, int(self.view_start - dy / 120 * self.span * 0.15))
        self.update()
