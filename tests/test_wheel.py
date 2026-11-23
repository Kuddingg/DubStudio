"""Lăn chuột qua ô chọn / ô số không được đổi giá trị; trang vẫn cuộn."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtWidgets import (QApplication, QComboBox, QScrollArea, QSpinBox, QVBoxLayout,  # noqa: E402
                               QWidget)


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    from app.widgets.common import install_wheel_guard
    if not hasattr(a, "_wheel_guard"):
        install_wheel_guard(a)
    return a


def wheel(w, dy=-120):
    pos = QPointF(w.width() / 2, w.height() / 2)
    e = QWheelEvent(pos, w.mapToGlobal(pos), QPoint(), QPoint(0, dy), Qt.NoButton, Qt.NoModifier,
                    Qt.NoScrollPhase, False)
    QApplication.sendEvent(w, e)


def make_page():
    area = QScrollArea()
    area.setWidgetResizable(True)
    body = QWidget()
    v = QVBoxLayout(body)
    cb = QComboBox()
    cb.addItems(["A", "B", "C"])
    sp = QSpinBox()
    sp.setRange(0, 100)
    sp.setValue(50)
    v.addWidget(cb)
    v.addWidget(sp)
    v.addSpacing(3000)                                  # trang dài để cuộn được
    area.setWidget(body)
    area.resize(300, 300)
    area.show()
    return area, cb, sp


def test_wheel_does_not_change_combo_and_scrolls(app):
    area, cb, sp = make_page()
    app.processEvents()
    assert cb.focusPolicy() == Qt.StrongFocus
    wheel(cb)
    wheel(sp)
    app.processEvents()
    assert cb.currentIndex() == 0
    assert sp.value() == 50
    assert area.verticalScrollBar().value() > 0          # cú lăn chuyển sang cuộn trang
    area.close()


def test_spinbox_wheel_works_after_click(app):
    area, cb, sp = make_page()
    app.processEvents()
    sp.setFocus()
    app.processEvents()
    if not sp.hasFocus():                                # nền offscreen đôi khi không cấp focus
        pytest.skip("không lấy được focus")
    wheel(sp, 120)
    assert sp.value() == 51
    wheel(cb)
    assert cb.currentIndex() == 0                        # ô chọn: lăn không bao giờ đổi
    area.close()
