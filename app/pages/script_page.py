"""Tab Kịch bản dịch: preset prompt + thuật ngữ + bộ lọc từ."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLineEdit, QListWidget,
                               QMessageBox, QPlainTextEdit, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from core import presets as store

from .. import icons
from ..theme import C
from ..widgets.common import Card, button, chip, field_label, label, toast


class ScriptPage(QWidget):
    presetsChanged = Signal(list)

    def __init__(self):
        super().__init__()
        self.items = store.load()
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        # ---- left: list
        left = Card("Danh sách kịch bản", "book", C["accent"])
        left.setFixedWidth(290)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm kịch bản…")
        self.search.addAction(icons.icon("search", C["muted"], 16), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self._filter)
        left.add(self.search)
        self.list = QListWidget()
        self.list.setObjectName("Presets")
        self.list.setCursor(Qt.PointingHandCursor)
        self.list.currentRowChanged.connect(self._show)
        left.add(self.list, 1)
        row = QHBoxLayout()
        add = button("Thêm mới", "plus", "primary")
        add.clicked.connect(self._add)
        dup = button("Nhân bản", "copy")
        dup.clicked.connect(self._dup)
        row.addWidget(add)
        row.addWidget(dup)
        left.add(row)
        root.addWidget(left)

        # ---- right: detail
        right = QVBoxLayout()
        right.setSpacing(16)
        detail = Card("Chi tiết kịch bản", "edit", C["cyan"])
        self.name = QLineEdit()
        self.name.setPlaceholderText("Tên kịch bản")
        self.name.setStyleSheet("font-size: 15px; font-weight: 600;")
        detail.add(field_label("Tên"))
        detail.add(self.name)
        hint = QHBoxLayout()
        hint.addWidget(field_label("Prompt gửi cho AI"))
        hint.addStretch()
        self.chars = label("", "Dim")
        hint.addWidget(self.chars)
        detail.add(hint)
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("Mô tả giọng văn, cách xưng hô, độ dài câu… AI sẽ dùng đoạn này khi dịch.")
        self.prompt.textChanged.connect(lambda: self.chars.setText(f"{len(self.prompt.toPlainText())} ký tự"))
        detail.add(self.prompt, 1)
        right.addWidget(detail, 3)

        bottom = QHBoxLayout()
        bottom.setSpacing(16)
        gl = Card("Thuật ngữ (Glossary)", "languages", C["green"])
        gl.header.addWidget(chip("Dịch cố định", "ok"))
        self.gloss = QTableWidget(0, 2)
        self.gloss.setHorizontalHeaderLabels(["Gốc", "Dịch thành"])
        self.gloss.verticalHeader().hide()
        self.gloss.verticalHeader().setDefaultSectionSize(30)
        self.gloss.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.gloss.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.gloss.setShowGrid(False)
        self.gloss.setAlternatingRowColors(True)
        gl.add(self.gloss, 1)
        gr = QHBoxLayout()
        ga = button("Thêm", "plus", "tool")
        ga.clicked.connect(self._gloss_add)
        gd = button("Xóa dòng", "trash", "tool")
        gd.clicked.connect(lambda: self.gloss.removeRow(self.gloss.currentRow()))
        gr.addWidget(ga)
        gr.addWidget(gd)
        gr.addStretch()
        gl.add(gr)
        bottom.addWidget(gl, 1)

        fl = Card("Bộ lọc từ", "sliders", C["amber"])
        fl.add(label("Thay từ sau khi dịch, trước khi đọc. Mỗi dòng một cặp: <b>từ gốc → từ thay</b>", "Muted", wrap=True))
        self.filters = QPlainTextEdit()
        self.filters.setPlaceholderText("chết → chít\ngiết → tiêu diệt\nđâm → chọc")
        fl.add(self.filters, 1)
        bottom.addWidget(fl, 1)
        right.addLayout(bottom, 2)

        actions = QHBoxLayout()
        self.btn_del = button("Xóa kịch bản", "trash", "danger")
        self.btn_del.clicked.connect(self._delete)
        actions.addWidget(self.btn_del)
        actions.addStretch()
        save = button("Lưu thay đổi", "save", "primary")
        save.setMinimumWidth(150)
        save.clicked.connect(self._save)
        actions.addWidget(save)
        right.addLayout(actions)
        root.addLayout(right, 1)

        self._reload_list(0)

    # ------------------------------------------------------------------
    def names(self) -> list[str]:
        return [p["name"] for p in self.items]

    def _reload_list(self, select: int = 0):
        self.list.blockSignals(True)
        self.list.clear()
        self.list.addItems(self.names())
        self.list.blockSignals(False)
        if self.items:
            self.list.setCurrentRow(max(0, min(select, len(self.items) - 1)))
        self._filter(self.search.text())

    def _filter(self, q: str):
        q = q.lower().strip()
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(q) and q not in it.text().lower())

    def _show(self, i: int):
        if not (0 <= i < len(self.items)):
            return
        p = self.items[i]
        self.name.setText(p["name"])
        self.prompt.setPlainText(p.get("prompt", ""))
        self.filters.setPlainText(p.get("filters", ""))
        self.gloss.setRowCount(0)
        for a, b in p.get("glossary", []):
            self._gloss_add(a, b)

    def _gloss_add(self, a="", b=""):
        r = self.gloss.rowCount()
        self.gloss.insertRow(r)
        self.gloss.setItem(r, 0, QTableWidgetItem(a if isinstance(a, str) else ""))
        self.gloss.setItem(r, 1, QTableWidgetItem(b if isinstance(b, str) else ""))
        if not a:
            self.gloss.editItem(self.gloss.item(r, 0))

    def _collect(self) -> dict:
        gloss = []
        for r in range(self.gloss.rowCount()):
            a = (self.gloss.item(r, 0).text() if self.gloss.item(r, 0) else "").strip()
            b = (self.gloss.item(r, 1).text() if self.gloss.item(r, 1) else "").strip()
            if a:
                gloss.append([a, b])
        return {"name": self.name.text().strip() or "Không tên", "prompt": self.prompt.toPlainText().strip(),
                "glossary": gloss, "filters": self.filters.toPlainText().strip()}

    def _save(self):
        i = self.list.currentRow()
        if i < 0:
            return
        self.items[i] = self._collect()
        store.save(self.items)
        self._reload_list(i)
        self.presetsChanged.emit(self.names())
        toast(self, f"Đã lưu kịch bản “{self.items[i]['name']}”", "ok")

    def _add(self):
        self.items.append({"name": "Kịch bản mới", "prompt": "", "glossary": [], "filters": ""})
        self._reload_list(len(self.items) - 1)
        self.name.setFocus()
        self.name.selectAll()

    def _dup(self):
        i = self.list.currentRow()
        if i < 0:
            return
        p = self._collect()
        p["name"] += " (bản sao)"
        self.items.insert(i + 1, p)
        self._reload_list(i + 1)

    def _delete(self):
        i = self.list.currentRow()
        if i < 0 or len(self.items) <= 1:
            toast(self, "Cần giữ lại ít nhất một kịch bản", "warn")
            return
        if QMessageBox.question(self, "Xóa kịch bản", f"Xóa “{self.items[i]['name']}”?") != QMessageBox.Yes:
            return
        self.items.pop(i)
        store.save(self.items)
        self._reload_list(i)
        self.presetsChanged.emit(self.names())
