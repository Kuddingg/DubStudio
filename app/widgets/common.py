"""Các widget dùng chung: toggle, card, segmented, slider, color swatch, toast..."""
from __future__ import annotations

import sys

from PySide6.QtCore import (Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt,
                            QTimer, Signal)
from PySide6.QtGui import (QColor, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPixmap,
                           QRadialGradient)
from PySide6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QButtonGroup, QColorDialog,
                               QComboBox, QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout,
                               QLabel, QListView, QPushButton, QSizePolicy, QSlider, QVBoxLayout,
                               QWidget)

from .. import icons
from ..theme import C, mix


def dpr() -> float:
    s = QGuiApplication.primaryScreen()
    return s.devicePixelRatio() if s else 1.0


def set_prop(w: QWidget, name: str, value) -> None:
    w.setProperty(name, value)
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def button(text: str = "", icon_name: str | None = None, variant: str | None = None,
           tip: str | None = None, icon_color: str | None = None, icon_size: int = 16) -> QPushButton:
    b = QPushButton(text)
    if icon_name:
        color = icon_color or {"primary": C["on_primary"], "danger": C["danger_text"], "ghost": C["muted"]}.get(variant, C["text"])
        b.setIcon(icons.icon(icon_name, color, icon_size))
        b.setIconSize(QSize(icon_size, icon_size))
    if variant:
        b.setProperty("variant", variant)
    if tip:
        b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    return b


def shrinkable(c: QComboBox) -> QComboBox:
    """Không để combobox đòi rộng theo item dài nhất (gây tràn layout)."""
    c.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    c.setMinimumContentsLength(4)
    c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return c


def round_popup(c: QComboBox) -> None:
    """Danh sách xổ xuống bo tròn thật (bỏ khung vuông + bóng của Windows quanh góc bo)."""
    w = c.view().window()
    w.setWindowFlags(w.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
    w.setAttribute(Qt.WA_TranslucentBackground)


class GlassBackground(QWidget):
    """Nền cửa sổ: màu nền + vài quầng sáng mờ để các thẻ kính trong suốt phía trên trông 'bóng'."""

    def paintEvent(self, e):
        from .. import theme
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C["bg"]))
        if theme.MODE not in theme.GLASS:
            return
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        for key, cx, cy, rad in (("glow1", 0.88, 0.02, 0.62), ("glow2", 0.10, 1.0, 0.65), ("glow3", 0.45, 0.45, 0.45)):
            r, g, b, a = (int(x) for x in C[key].split(","))
            radius = max(w, h) * rad
            grad = QRadialGradient(QPointF(w * cx, h * cy), radius)
            grad.setColorAt(0, QColor(r, g, b, a))
            grad.setColorAt(1, QColor(r, g, b, 0))
            p.fillRect(self.rect(), grad)


def combo(items: list[str], current: str | None = None) -> QComboBox:
    c = QComboBox()
    c.setView(QListView())  # để QSS item hoạt động trên Windows
    round_popup(c)
    shrinkable(c)
    c.addItems(items)
    c.setCursor(Qt.PointingHandCursor)
    if current:
        i = c.findText(current)
        if i >= 0:
            c.setCurrentIndex(i)
    return c


def no_buttons(spin: QAbstractSpinBox) -> QAbstractSpinBox:
    spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
    spin.setAlignment(Qt.AlignCenter)
    return spin


def chip(text: str, tone: str | None = None) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName("Chip")
    lb.setProperty("tone", tone or "")
    return lb


def set_chip(lb: QLabel, text: str, tone: str | None) -> None:
    lb.setText(text)
    set_prop(lb, "tone", tone or "")


def field_label(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName("FieldLabel")
    return lb


def label(text: str, name: str | None = None, wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


def divider() -> QFrame:
    f = QFrame()
    f.setObjectName("Divider")
    f.setFixedHeight(1)
    return f


def form_grid() -> QGridLayout:
    g = QGridLayout()
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(10)
    g.setVerticalSpacing(8)
    g.setColumnStretch(1, 1)
    return g


def dot_pixmap(color: str, d: int = 8) -> QPixmap:
    r = dpr()
    pm = QPixmap(int(d * r), int(d * r))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(QRectF(0, 0, d * r, d * r))
    p.end()
    pm.setDevicePixelRatio(r)
    return pm


def rounded_pixmap(src: QPixmap, w: int, h: int, radius: int = 8) -> QPixmap:
    r = dpr()
    W, H = int(w * r), int(h * r)
    scaled = src.scaled(W, H, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x, y = (scaled.width() - W) // 2, (scaled.height() - H) // 2
    out = QPixmap(W, H)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, W, H), radius * r, radius * r)
    p.setClipPath(path)
    p.drawPixmap(0, 0, scaled, x, y, W, H)
    p.end()
    out.setDevicePixelRatio(r)
    return out


def brand_mark(size: int = 34) -> QPixmap:
    r = dpr()
    S = int(size * r)
    pm = QPixmap(S, S)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, S, S)
    g.setColorAt(0, QColor(C["accent"]))
    g.setColorAt(1, QColor(C["cyan"]))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(QRectF(0, 0, S, S), S * 0.28, S * 0.28)
    ic = icons.pixmap("wave", "#FFFFFF", int(size * 0.6), 2.4)
    off = (S - ic.width()) / 2
    p.drawPixmap(int(off), int(off), ic)
    p.end()
    pm.setDevicePixelRatio(r)
    return pm


def dark_titlebar(widget: QWidget) -> None:
    """Thanh tiêu đề Windows cùng màu nền app (tối hoặc sáng)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = int(widget.winId())
        from .. import theme
        on = ctypes.c_int(1 if theme.is_dark() else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), ctypes.sizeof(on))
        bg = QColor(C["bg"])
        colorref = ctypes.c_int(bg.red() | (bg.green() << 8) | (bg.blue() << 16))
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(colorref), ctypes.sizeof(colorref))
    except Exception:  # noqa: BLE001 - Windows cũ không hỗ trợ thì thôi
        pass


# --------------------------------------------------------------------------- widgets
class ElidedLabel(QLabel):
    """Label tự rút gọn chữ dài bằng dấu '…'."""

    def __init__(self, text: str = "", mode=Qt.ElideMiddle):
        super().__init__(text)
        self._full, self._mode = text, mode
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def setText(self, text: str) -> None:
        self._full = text
        super().setText(text)
        self.setToolTip(text)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setPen(self.palette().color(self.foregroundRole()))
        p.setFont(self.font())
        t = self.fontMetrics().elidedText(self._full, self._mode, self.width())
        p.drawText(self.rect(), Qt.AlignLeft | Qt.AlignVCenter, t)


class ToggleSwitch(QAbstractButton):
    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(36, 20)
        self._offset = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _animate(self, on: bool):
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def _get(self):
        return self._offset

    def _set(self, v):
        self._offset = v
        self.update()

    offset = Property(float, _get, _set)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        track = mix(C["switch_off"], C["accent"], self._offset)
        if not self.isEnabled():
            track.setAlpha(110)
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - 6 - d) * self._offset
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))


class LabeledToggle(QWidget):
    toggled = Signal(bool)

    def __init__(self, text: str, checked: bool = False, tip: str | None = None):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        self.switch = ToggleSwitch(checked)
        self.label = QLabel(text)
        self.label.setCursor(Qt.PointingHandCursor)
        h.addWidget(self.switch)
        h.addWidget(self.label)
        h.addStretch()
        self.switch.toggled.connect(self.toggled)
        self.label.mousePressEvent = lambda e: self.switch.toggle()
        if tip:
            self.setToolTip(tip)

    def isChecked(self) -> bool:
        return self.switch.isChecked()

    def setChecked(self, v: bool) -> None:
        self.switch.setChecked(bool(v))


class Card(QFrame):
    def __init__(self, title: str | None = None, icon_name: str | None = None,
                 icon_color: str | None = None, padding: int = 16, spacing: int = 10):
        super().__init__()
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, 14, padding, padding)
        self.body.setSpacing(spacing)
        self.header = None
        if title:
            self.header = QHBoxLayout()
            self.header.setSpacing(8)
            if icon_name:
                ic = QLabel()
                ic.setPixmap(icons.pixmap(icon_name, icon_color or C["accent"], 15))
                self.header.addWidget(ic)
            t = QLabel(title.upper())
            t.setObjectName("CardTitle")
            self.header.addWidget(t)
            self.header.addStretch()
            self.body.addLayout(self.header)

    def add(self, item, stretch: int = 0):
        if isinstance(item, QWidget):
            self.body.addWidget(item, stretch)
        else:
            self.body.addLayout(item, stretch)
        return item


class Segmented(QWidget):
    changed = Signal(int)

    def __init__(self, options: list[str], current: int = 0):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.options = options
        for i, text in enumerate(options):
            b = QPushButton(text)
            b.setObjectName("Seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setProperty("pos", "first" if i == 0 else ("last" if i == len(options) - 1 else "mid"))
            self.group.addButton(b, i)
            h.addWidget(b)
        self.group.button(current).setChecked(True)
        self.group.idClicked.connect(self.changed)

    def value(self) -> str:
        return self.options[self.group.checkedId()]

    def setValue(self, v) -> None:
        if v in self.options:
            self.group.button(self.options.index(v)).setChecked(True)


class SliderRow(QWidget):
    valueChanged = Signal(float)

    def __init__(self, text: str, minimum: float, maximum: float, value: float,
                 step: float = 1.0, decimals: int = 0, suffix: str = "", label_width: int = 78):
        super().__init__()
        self._scale = 1.0 / step
        self._dec, self._suffix = decimals, suffix
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        lb = field_label(text)
        lb.setFixedWidth(label_width)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(round(minimum * self._scale), round(maximum * self._scale))
        self.slider.setCursor(Qt.PointingHandCursor)
        self.val = QLabel()
        self.val.setObjectName("Value")
        self.val.setFixedWidth(52)
        self.val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(lb)
        h.addWidget(self.slider, 1)
        h.addWidget(self.val)
        self.slider.valueChanged.connect(self._changed)
        self.setValue(value)
        self._changed()

    def _changed(self, *_):
        v = self.value()
        self.val.setText(f"{v:.{self._dec}f}{self._suffix}")
        self.valueChanged.emit(v)

    def value(self) -> float:
        v = self.slider.value() / self._scale
        return round(v, self._dec) if self._dec else int(round(v))

    def setValue(self, v: float) -> None:
        self.slider.setValue(round(float(v) * self._scale))


class ColorSwatch(QPushButton):
    colorChanged = Signal(str)

    def __init__(self, color: str = "#FFFFFF", tip: str = "Chọn màu"):
        super().__init__()
        self._color = color
        self.setFixedSize(34, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tip)
        self.clicked.connect(self._pick)

    def color(self) -> str:
        return self._color

    def setColor(self, c: str) -> None:
        self._color = c
        self.update()
        self.colorChanged.emit(c)

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._color), self, "Chọn màu")
        if c.isValid():
            self.setColor(c.name().upper())

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QColor(C["border2"] if not self.underMouse() else C["accent"]))
        p.setBrush(QColor(C["input"]))
        p.drawRoundedRect(r, 8, 8)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self._color))
        p.drawRoundedRect(r.adjusted(5, 5, -5, -5), 4, 4)


class Toast(QFrame):
    _active: list = []
    TONES = {"info": (C["cyan"], "sparkles"), "ok": (C["green"], "check"),
             "warn": (C["amber"], "help"), "err": (C["red"], "x")}

    def __init__(self, host: QWidget, text: str, tone: str = "info"):
        super().__init__(host)
        color, ic = self.TONES.get(tone, self.TONES["info"])
        self.setObjectName("Toast")
        self.setStyleSheet(
            f"#Toast {{ background: {C['card2']}; border: 1px solid {C['border2']}; "
            f"border-left: 3px solid {color}; border-radius: 10px; }} QLabel {{ background: transparent; }}")
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 10, 16, 10)
        h.setSpacing(10)
        i = QLabel()
        i.setPixmap(icons.pixmap(ic, color, 16))
        h.addWidget(i)
        lb = QLabel(text)
        lb.setWordWrap(True)
        lb.setMaximumWidth(380)
        h.addWidget(lb)
        self.adjustSize()
        self.eff = QGraphicsOpacityEffect(self)
        self.eff.setOpacity(0.0)
        self.setGraphicsEffect(self.eff)
        Toast._active.append(self)
        self._place()
        self.show()
        self.raise_()
        self._fade(1.0)
        QTimer.singleShot(2800, self._close)

    def _place(self):
        host = self.parentWidget()
        y = 76
        for t in Toast._active:
            if t is self:
                break
            y += t.height() + 8
        self.move(host.width() - self.width() - 24, y)

    def _fade(self, to: float, done=None):
        a = QPropertyAnimation(self.eff, b"opacity", self)
        a.setDuration(180)
        a.setStartValue(self.eff.opacity())
        a.setEndValue(to)
        if done:
            a.finished.connect(done)
        a.start()
        self._anim = a

    def _close(self):
        self._fade(0.0, self._remove)

    def _remove(self):
        if self in Toast._active:
            Toast._active.remove(self)
        self.deleteLater()


def toast(widget: QWidget, text: str, tone: str = "info") -> None:
    Toast(widget.window(), text, tone)
