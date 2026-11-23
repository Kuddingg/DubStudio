"""Khung xem trước video + các vùng (OCR, vị trí sub, blur, logo, chữ) kéo thả / resize được.

Tọa độ vùng lưu dạng chuẩn hóa 0..1 theo khung hình → không phụ thuộc độ phân giải hay kích thước cửa sổ.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import (QFrame, QGraphicsItem, QGraphicsObject, QGraphicsPixmapItem,
                               QGraphicsScene, QGraphicsView, QInputDialog, QMenu)

from .. import icons
from .. import theme
from ..theme import C
from .common import dpr

KINDS = {
    "ocr": ("Vùng quét OCR", C["cyan"]),
    "sub": ("Vị trí phụ đề", C["green"]),
    "blur": ("Làm mờ", C["red"]),
    "logo": ("Logo", C["accent"]),
    "text": ("Chữ", C["amber"]),
}
DEFAULTS = {
    "ocr": (0.10, 0.79, 0.80, 0.14),
    "sub": (0.10, 0.80, 0.80, 0.12),
    "blur": (0.10, 0.79, 0.80, 0.14),
    "logo": (0.03, 0.05, 0.09, 0.14),
    "text": (0.66, 0.05, 0.30, 0.07),
}
GRAB, HANDLE, MIN_SIZE = 9.0, 7.0, 14.0


def _corners(r: QRectF):
    return [r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()]


class RegionItem(QGraphicsObject):
    changed = Signal()

    def __init__(self, kind: str, norm, text: str = "", logo: QPixmap | None = None):
        super().__init__()
        self.kind, self.norm, self.text, self.logo = kind, list(norm), text, logo
        self.bounds = QRectF(0, 0, 1, 1)
        self._rect = QRectF()
        self._mode = None
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

    # -- geometry
    def set_bounds(self, b: QRectF):
        self.prepareGeometryChange()
        self.bounds = QRectF(b)
        x, y, w, h = self.norm
        self._rect = QRectF(b.x() + x * b.width(), b.y() + y * b.height(), w * b.width(), h * b.height())
        self.update()

    def _sync(self):
        b, r = self.bounds, self._rect
        self.norm = [(r.x() - b.x()) / b.width(), (r.y() - b.y()) / b.height(),
                     r.width() / b.width(), r.height() / b.height()]

    def to_dict(self) -> dict:
        return {"kind": self.kind, "rect": [round(v, 4) for v in self.norm], "text": self.text}

    def boundingRect(self) -> QRectF:
        r = self._rect
        return QRectF(r.left() - HANDLE, r.top() - 26, max(r.width(), 150) + 2 * HANDLE, r.height() + 26 + HANDLE)

    def _corner_at(self, pos: QPointF) -> int:
        for i, c in enumerate(_corners(self._rect)):
            if abs(pos.x() - c.x()) <= GRAB and abs(pos.y() - c.y()) <= GRAB:
                return i
        return -1

    # -- interaction
    def hoverMoveEvent(self, e):
        c = self._corner_at(e.pos())
        if c in (0, 2):
            self.setCursor(Qt.SizeFDiagCursor)
        elif c in (1, 3):
            self.setCursor(Qt.SizeBDiagCursor)
        else:
            self.setCursor(Qt.SizeAllCursor)

    def hoverLeaveEvent(self, e):
        self.unsetCursor()

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            e.ignore()
            return
        self.scene().clearSelection()
        self.setSelected(True)
        c = self._corner_at(e.pos())
        self._mode = c if c >= 0 else "move"
        self._press, self._start = e.pos(), QRectF(self._rect)
        e.accept()

    def mouseMoveEvent(self, e):
        if self._mode is None:
            return
        d = e.pos() - self._press
        b, s = self.bounds, self._start
        if self._mode == "move":
            r = s.translated(d)
            if r.left() < b.left():
                r.moveLeft(b.left())
            if r.right() > b.right():
                r.moveRight(b.right())
            if r.top() < b.top():
                r.moveTop(b.top())
            if r.bottom() > b.bottom():
                r.moveBottom(b.bottom())
        else:
            p = _corners(s)[self._mode] + d
            p.setX(min(max(p.x(), b.left()), b.right()))
            p.setY(min(max(p.y(), b.top()), b.bottom()))
            r = QRectF(p, _corners(s)[(self._mode + 2) % 4]).normalized()
            if r.width() < MIN_SIZE or r.height() < MIN_SIZE:
                return
        self.prepareGeometryChange()
        self._rect = r
        self._sync()
        self.update()
        self.changed.emit()

    def mouseReleaseEvent(self, e):
        self._mode = None
        e.accept()

    # -- painting
    def _draw_text(self, p: QPainter, r: QRectF, text: str, color: QColor, scale: float, bold: bool):
        f = QFont(theme.FONT)
        f.setBold(bold)
        px = max(9.0, r.height() * scale)
        f.setPixelSize(int(px))
        fm = QFontMetricsF(f)
        w = fm.horizontalAdvance(text)
        if w > r.width() * 0.94:
            px = max(8.0, px * r.width() * 0.94 / w)
            f.setPixelSize(int(px))
            fm = QFontMetricsF(f)
            w = fm.horizontalAdvance(text)
        path = QPainterPath()
        path.addText(QPointF(r.center().x() - w / 2, r.center().y() + (fm.ascent() - fm.descent()) / 2), f, text)
        p.setPen(QPen(QColor(0, 0, 0, 230), max(2.0, px / 7), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawPath(path)

    def paint(self, p: QPainter, option, widget=None):
        p.setRenderHint(QPainter.Antialiasing)
        name, col = KINDS[self.kind]
        color, r, sel = QColor(col), self._rect, self.isSelected()

        fill = QColor(color)
        fill.setAlpha(52 if sel else 30)
        p.setPen(Qt.NoPen)
        p.setBrush(fill)
        p.drawRoundedRect(r, 5, 5)

        if self.kind == "blur":
            hatch = QColor(color)
            hatch.setAlpha(80)
            p.setBrush(QBrush(hatch, Qt.BDiagPattern))
            p.drawRoundedRect(r, 5, 5)
        elif self.kind == "text":
            self._draw_text(p, r, self.text or "@kenh_cua_ban", QColor("#FFFFFF"), 0.55, False)
        elif self.kind == "sub":
            self._draw_text(p, r, "Phụ đề tiếng Việt mẫu", QColor("#FFE14D"), 0.5, True)
        elif self.kind == "logo":
            inner = r.adjusted(4, 4, -4, -4)
            if self.logo is not None and not self.logo.isNull():
                s = self.logo.size().scaled(inner.size().toSize(), Qt.KeepAspectRatio)
                tgt = QRectF(0, 0, s.width(), s.height())
                tgt.moveCenter(inner.center())
                p.drawPixmap(tgt, self.logo, QRectF(self.logo.rect()))
            else:
                ic = icons.pixmap("image", col, int(max(12, min(inner.width(), inner.height()) * 0.5)))
                sz = ic.deviceIndependentSize()
                p.drawPixmap(QPointF(inner.center().x() - sz.width() / 2, inner.center().y() - sz.height() / 2), ic)

        pen = QPen(color, 2.0 if sel else 1.3)
        pen.setStyle(Qt.SolidLine if sel else Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 5, 5)

        f = QFont(theme.FONT)
        f.setPixelSize(11)
        f.setBold(True)
        p.setFont(f)
        tw = QFontMetricsF(f).horizontalAdvance(name) + 14
        cy = r.top() - 22 if r.top() - 22 >= 2 else r.top() + 4
        # vùng Làm mờ thường trùng vùng OCR → đặt nhãn ở góc phải để không đè nhau
        cx = r.right() - tw if self.kind == "blur" else r.left()
        chip = QRectF(cx, cy, tw, 18)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(chip, 5, 5)
        p.setPen(QColor("#0A0C11"))
        p.drawText(chip, Qt.AlignCenter, name)

        if sel:
            p.setPen(QPen(color, 1.5))
            p.setBrush(QColor("#FFFFFF"))
            for c in _corners(r):
                p.drawRoundedRect(QRectF(c.x() - HANDLE / 2, c.y() - HANDLE / 2, HANDLE, HANDLE), 2, 2)


class VideoCanvas(QGraphicsView):
    regionsChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setBackgroundBrush(QColor("#07090D"))
        self.setMinimumHeight(150)
        self.setStyleSheet("background: #07090D; border-radius: 10px;")
        self._frame: QPixmap | None = None
        self._size = QSizeF(1920, 1080)
        self._logo: QPixmap | None = None
        self._busy = False
        self.pix = QGraphicsPixmapItem()
        self._scene.addItem(self.pix)
        self.regions: list[RegionItem] = []

    # -- frame
    def img_rect(self) -> QRectF:
        vw, vh, m = self.viewport().width(), self.viewport().height(), 14
        aw, ah = max(1, vw - 2 * m), max(1, vh - 2 * m)
        s = min(aw / self._size.width(), ah / self._size.height())
        w, h = self._size.width() * s, self._size.height() * s
        return QRectF((vw - w) / 2, (vh - h) / 2, w, h)

    def set_aspect(self, w: int, h: int):
        if w and h:
            self._size = QSizeF(w, h)
            self._relayout()

    def set_frame(self, pm: QPixmap | None, busy: bool = False):
        self._frame = pm if pm is not None and not pm.isNull() else None
        self._busy = busy
        if self._frame:
            self._size = QSizeF(self._frame.size())
        self._relayout()

    def _relayout(self):
        vw, vh = self.viewport().width(), self.viewport().height()
        self._scene.setSceneRect(0, 0, vw, vh)
        ir = self.img_rect()
        r = dpr()
        W, H = max(1, int(ir.width() * r)), max(1, int(ir.height() * r))
        out = QPixmap(W, H)
        out.fill(Qt.transparent)
        p = QPainter(out)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, W, H), 8 * r, 8 * r)
        p.setClipPath(clip)
        if self._frame:
            p.drawPixmap(QRectF(0, 0, W, H), self._frame, QRectF(self._frame.rect()))
        else:
            self._paint_placeholder(p, W, H, r)
        p.end()
        out.setDevicePixelRatio(r)
        self.pix.setPixmap(out)
        self.pix.setPos(ir.topLeft())
        for it in self.regions:
            it.set_bounds(ir)

    def _paint_placeholder(self, p: QPainter, W: int, H: int, r: float):
        g = QLinearGradient(0, 0, W, H)
        g.setColorAt(0, QColor("#141828"))
        g.setColorAt(1, QColor("#0B0E15"))
        p.fillRect(0, 0, W, H, g)
        p.setPen(QPen(QColor(255, 255, 255, 9), 1))
        step = int(36 * r)
        for x in range(0, W, step):
            p.drawLine(x, 0, x, H)
        for y in range(0, H, step):
            p.drawLine(0, y, W, y)
        ic = icons.pixmap("film", C["dim"], 40, 1.6)
        p.drawPixmap(int((W - ic.width()) / 2), int(H / 2 - ic.height() - 8 * r), ic)
        f = QFont(theme.FONT)
        f.setPixelSize(int(13 * r))
        p.setFont(f)
        p.setPen(QColor(C["muted"]))
        msg = "Đang tải khung hình…" if self._busy else "Chọn hoặc kéo thả video để xem trước"
        p.drawText(QRectF(0, H / 2 + 4 * r, W, 24 * r), Qt.AlignCenter, msg)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._relayout()

    def showEvent(self, e):
        super().showEvent(e)
        self._relayout()

    # -- regions
    def _create(self, kind: str, norm, text: str = "") -> RegionItem:
        it = RegionItem(kind, norm, text, self._logo if kind == "logo" else None)
        it.changed.connect(self.regionsChanged)
        self._scene.addItem(it)
        self.regions.append(it)
        it.set_bounds(self.img_rect())
        return it

    def add_region(self, kind: str, text: str = "") -> RegionItem:
        it = self._create(kind, DEFAULTS[kind], text)
        self._scene.clearSelection()
        it.setSelected(True)
        self.setFocus()
        self.regionsChanged.emit()
        return it

    def set_regions(self, items: list[dict]):
        for it in self.regions:
            self._scene.removeItem(it)
        self.regions = []
        for d in items:
            if d.get("kind") in KINDS:
                self._create(d["kind"], d.get("rect", DEFAULTS[d["kind"]]), d.get("text", ""))

    def get_regions(self) -> list[dict]:
        return [it.to_dict() for it in self.regions]

    def _remove(self, it: RegionItem):
        self._scene.removeItem(it)
        self.regions.remove(it)
        self.regionsChanged.emit()

    def remove_selected(self):
        for it in [i for i in self.regions if i.isSelected()]:
            self._remove(it)

    def set_logo(self, path: str | None):
        self._logo = QPixmap(path) if path else None
        for it in self.regions:
            if it.kind == "logo":
                it.logo = self._logo
                it.update()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.remove_selected()
        else:
            super().keyPressEvent(e)

    def mousePressEvent(self, e):
        if not isinstance(self.itemAt(e.position().toPoint()), RegionItem):
            self._scene.clearSelection()
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        it = self.itemAt(e.position().toPoint())
        if isinstance(it, RegionItem) and it.kind == "text":
            text, ok = QInputDialog.getText(self, "Sửa chữ", "Nội dung chữ / watermark:", text=it.text)
            if ok:
                it.text = text
                it.update()
                self.regionsChanged.emit()
            return
        super().mouseDoubleClickEvent(e)

    def contextMenuEvent(self, e):
        it = self.itemAt(e.pos())
        if isinstance(it, RegionItem):
            menu = QMenu(self)
            if it.kind == "text":
                menu.addAction("Sửa nội dung chữ…", lambda: self._edit_text(it))
            menu.addAction(f"Xóa vùng “{KINDS[it.kind][0]}”", lambda: self._remove(it))
            menu.exec(e.globalPos())

    def _edit_text(self, it: RegionItem):
        text, ok = QInputDialog.getText(self, "Sửa chữ", "Nội dung chữ / watermark:", text=it.text)
        if ok:
            it.text = text
            it.update()
            self.regionsChanged.emit()
