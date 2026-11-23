"""Gắn widget với key cấu hình → đọc/ghi cả form thành dict một lần."""
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFontComboBox, QLineEdit,
                               QPlainTextEdit, QSpinBox)

from .common import ColorSwatch, LabeledToggle, Segmented, SliderRow


class Binder(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fields: dict = {}

    def bind(self, key: str, w):
        self.fields[key] = w
        if isinstance(w, QFontComboBox):
            w.currentFontChanged.connect(self._emit)
        elif isinstance(w, QComboBox):
            w.currentIndexChanged.connect(self._emit)
        elif isinstance(w, (QLineEdit, QPlainTextEdit)):
            w.textChanged.connect(self._emit)
        elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
            w.valueChanged.connect(self._emit)
        elif isinstance(w, (LabeledToggle, QCheckBox)):
            w.toggled.connect(self._emit)
        elif isinstance(w, Segmented):
            w.changed.connect(self._emit)
        elif isinstance(w, SliderRow):
            w.valueChanged.connect(self._emit)
        elif isinstance(w, ColorSwatch):
            w.colorChanged.connect(self._emit)
        return w

    def _emit(self, *_):
        self.changed.emit()

    @staticmethod
    def _get(w):
        if isinstance(w, QFontComboBox):
            return w.currentFont().family()
        if isinstance(w, QComboBox):
            return w.currentText()
        if isinstance(w, QLineEdit):
            return w.text()
        if isinstance(w, QPlainTextEdit):
            return w.toPlainText()
        if isinstance(w, (QSpinBox, QDoubleSpinBox, SliderRow)):
            return w.value()
        if isinstance(w, (LabeledToggle, QCheckBox)):
            return w.isChecked()
        if isinstance(w, Segmented):
            return w.value()
        if isinstance(w, ColorSwatch):
            return w.color()
        return None

    @staticmethod
    def _set(w, v):
        if isinstance(w, QFontComboBox):
            w.setCurrentFont(QFont(v))
        elif isinstance(w, QComboBox):
            i = w.findText(str(v))
            if i >= 0:
                w.setCurrentIndex(i)
            elif w.isEditable():
                w.setCurrentText(str(v))     # ô cho gõ tự do (vd tên model Ollama)
        elif isinstance(w, QLineEdit):
            w.setText(str(v))
        elif isinstance(w, QPlainTextEdit):
            w.setPlainText(str(v))
        elif isinstance(w, (QSpinBox, SliderRow)):
            w.setValue(int(v) if isinstance(w, QSpinBox) else v)
        elif isinstance(w, QDoubleSpinBox):
            w.setValue(float(v))
        elif isinstance(w, (LabeledToggle, QCheckBox)):
            w.setChecked(bool(v))
        elif isinstance(w, Segmented):
            w.setValue(v)
        elif isinstance(w, ColorSwatch):
            w.setColor(str(v))

    def values(self) -> dict:
        return {k: self._get(w) for k, w in self.fields.items()}

    def set_values(self, data: dict) -> None:
        self.blockSignals(True)
        try:
            for k, v in data.items():
                if k in self.fields and v is not None:
                    try:
                        self._set(self.fields[k], v)
                    except (TypeError, ValueError):
                        pass
        finally:
            self.blockSignals(False)
