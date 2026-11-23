"""Bảng màu + stylesheet toàn app (dark theme)."""
from string import Template

from PySide6.QtGui import QColor, QFont, QFontDatabase

C = {
    "bg": "#090B10",
    "surface": "#0D1016",
    "card": "#12161F",
    "card2": "#191E2A",
    "input": "#0C0F15",
    "border": "#222838",
    "border2": "#2E3547",
    "text": "#E8EAF1",
    "muted": "#8C94A8",
    "dim": "#5C6478",
    "accent": "#7C5CFF",
    "accent2": "#5B8CFF",
    "cyan": "#22D3EE",
    "green": "#22C55E",
    "red": "#F43F5E",
    "amber": "#F5A524",
}

FONT = "Segoe UI"


def mix(a: str, b: str, t: float) -> QColor:
    ca, cb = QColor(a), QColor(b)
    return QColor(
        int(ca.red() + (cb.red() - ca.red()) * t),
        int(ca.green() + (cb.green() - ca.green()) * t),
        int(ca.blue() + (cb.blue() - ca.blue()) * t),
    )


QSS = Template(r"""
* { font-family: "$font"; }
QWidget { color: $text; font-size: 13px; }
QMainWindow, QDialog, #Root { background: $bg; }
QToolTip { background: $card2; color: $text; border: 1px solid $border2; padding: 6px 8px; border-radius: 6px; }

/* ---------- Sidebar / Topbar ---------- */
#Sidebar { background: $surface; border-right: 1px solid $border; }
#Brand { font-size: 16px; font-weight: 700; }
#BrandSub { color: $dim; font-size: 11px; }
#NavSection { color: $dim; font-size: 10px; font-weight: 700; padding-left: 12px; }
QPushButton#Nav { background: transparent; border: none; border-radius: 10px; color: $muted;
    text-align: left; padding: 10px 12px; font-size: 13px; font-weight: 600; }
QPushButton#Nav:hover { background: $card; color: $text; }
QPushButton#Nav:checked { background: rgba(124, 92, 255, 38); color: #FFFFFF; }
#TopBar { background: $bg; border-bottom: 1px solid $border; }
#PageTitle { font-size: 19px; font-weight: 700; }
#PageSub { color: $muted; font-size: 12px; }
QFrame#Pill { background: $card; border: 1px solid $border; border-radius: 15px; }
QFrame#PlanBox { background: $card; border: 1px solid $border; border-radius: 12px; }

/* ---------- Cards / labels ---------- */
QFrame#Card { background: $card; border: 1px solid $border; border-radius: 14px; }
QLabel#CardTitle { color: $muted; font-size: 11px; font-weight: 700; }
QLabel#FieldLabel { color: $muted; font-size: 12px; }
QLabel#Muted { color: $muted; }
QLabel#Dim { color: $dim; font-size: 11px; }
QLabel#Value { color: $text; font-size: 12px; font-weight: 600; }
QLabel#H2 { font-size: 15px; font-weight: 700; }
QLabel#Mono { font-family: "Cascadia Mono", "Consolas"; font-size: 13px; color: $text; }
QFrame#Divider { background: $border; border: none; }

/* ---------- Inputs ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {
    background: $input; border: 1px solid $border; border-radius: 8px; padding: 6px 10px;
    selection-background-color: $accent; selection-color: #FFFFFF; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { min-height: 20px; }
QPlainTextEdit, QTextEdit { padding: 8px; }
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover, QPlainTextEdit:hover { border-color: $border2; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus { border-color: $accent; }
QLineEdit:read-only { color: $muted; }
QComboBox::drop-down { border: none; width: 26px; subcontrol-origin: padding; subcontrol-position: center right; }
QComboBox::down-arrow { image: url("$chevron"); width: 12px; height: 12px; }
QComboBox QAbstractItemView { background: $card2; border: 1px solid $border2; border-radius: 8px; padding: 4px; outline: 0; }
QComboBox QAbstractItemView::item { min-height: 28px; padding: 0 8px; border-radius: 6px; color: $text; }
QComboBox QAbstractItemView::item:hover, QComboBox QAbstractItemView::item:selected { background: rgba(124, 92, 255, 60); color: #FFFFFF; }

/* ---------- Buttons ---------- */
QPushButton { background: $card2; border: 1px solid $border2; border-radius: 9px; padding: 7px 14px; font-weight: 600; color: $text; }
QPushButton:hover { background: #222838; border-color: #3A4258; }
QPushButton:pressed { background: #151924; }
QPushButton:disabled { color: $dim; background: $card; border-color: $border; }
QPushButton[variant="primary"] { border: none; color: #FFFFFF;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $accent, stop:1 $accent2); }
QPushButton[variant="primary"]:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8E72FF, stop:1 #6F9BFF); }
QPushButton[variant="primary"]:pressed { background: $accent; }
QPushButton[variant="primary"]:disabled { background: $card2; color: $dim; }
QPushButton[variant="danger"] { background: rgba(244, 63, 94, 28); border: 1px solid rgba(244, 63, 94, 90); color: #FF8FA3; }
QPushButton[variant="danger"]:hover { background: rgba(244, 63, 94, 55); }
QPushButton[variant="danger"]:disabled { background: $card; border-color: $border; color: $dim; }
QPushButton[variant="ghost"] { background: transparent; border: 1px solid transparent; color: $muted; }
QPushButton[variant="ghost"]:hover { background: $card2; color: $text; }
QPushButton[variant="tool"] { background: $input; border: 1px solid $border; padding: 6px 10px; font-weight: 500; }
QPushButton[variant="tool"]:hover { border-color: $border2; background: $card2; }
QPushButton[variant="tool"]:checked { border-color: $accent; background: rgba(124, 92, 255, 40); }
QPushButton#Seg { border-radius: 0; background: $input; border: 1px solid $border; padding: 6px 8px; font-weight: 500; color: $muted; }
QPushButton#Seg[pos="first"] { border-top-left-radius: 8px; border-bottom-left-radius: 8px; }
QPushButton#Seg[pos="last"] { border-top-right-radius: 8px; border-bottom-right-radius: 8px; }
QPushButton#Seg:hover { color: $text; }
QPushButton#Seg:checked { background: rgba(124, 92, 255, 45); color: #FFFFFF; border-color: $accent; }

/* ---------- Check / slider / progress ---------- */
QCheckBox { spacing: 8px; color: $text; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 5px; border: 1px solid $border2; background: $input; }
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; image: url("$check"); }
QSlider { min-height: 18px; }
QSlider::groove:horizontal { height: 4px; background: $border; border-radius: 2px; }
QSlider::sub-page:horizontal { border-radius: 2px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $accent, stop:1 $accent2); }
QSlider::handle:horizontal { background: #FFFFFF; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
QSlider::handle:horizontal:hover { background: #DCD3FF; }
QProgressBar { background: $input; border: none; border-radius: 3px; min-height: 6px; max-height: 6px; }
QProgressBar::chunk { border-radius: 3px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $accent, stop:1 $cyan); }

/* ---------- Scroll ---------- */
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #262C3B; border-radius: 3px; min-height: 30px; margin: 0 2px; }
QScrollBar::handle:vertical:hover { background: #39425A; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #262C3B; border-radius: 3px; min-width: 30px; margin: 2px 0; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

/* ---------- Lists / tables ---------- */
QListWidget { background: transparent; border: none; outline: 0; }
QListWidget#Presets::item { padding: 9px 12px; border-radius: 8px; color: $muted; margin: 1px 0; }
QListWidget#Presets::item:hover { background: $card2; color: $text; }
QListWidget#Presets::item:selected { background: rgba(124, 92, 255, 45); color: #FFFFFF; }
QTableView, QTableWidget { background: $input; border: 1px solid $border; border-radius: 10px; gridline-color: transparent;
    selection-background-color: rgba(124, 92, 255, 60); selection-color: #FFFFFF; alternate-background-color: #10141C; outline: 0; }
QTableView::item { padding: 4px 8px; border: none; }
QHeaderView { background: transparent; }
QHeaderView::section { background: $card2; color: $muted; border: none; border-bottom: 1px solid $border; padding: 7px 8px;
    font-weight: 600; font-size: 12px; }
QTableCornerButton::section { background: $card2; border: none; }
QSplitter::handle { background: transparent; }
QSplitter::handle:vertical { height: 10px; }
QSplitter::handle:horizontal { width: 10px; }

/* ---------- Chips / rows ---------- */
QLabel#Chip { border-radius: 9px; padding: 2px 9px; font-size: 11px; font-weight: 700; background: $card2; color: $muted; }
QLabel#Chip[tone="ok"] { background: rgba(34, 197, 94, 35); color: #4ADE80; }
QLabel#Chip[tone="run"] { background: rgba(124, 92, 255, 50); color: #C4B5FF; }
QLabel#Chip[tone="err"] { background: rgba(244, 63, 94, 40); color: #FF8FA3; }
QLabel#Chip[tone="warn"] { background: rgba(245, 165, 36, 38); color: #FCC86B; }
QLabel#Chip[tone="info"] { background: rgba(34, 211, 238, 32); color: #67E8F9; }
QFrame#JobRow { background: $card2; border: 1px solid $border; border-radius: 12px; }
QFrame#JobRow:hover { border-color: $border2; }
QFrame#JobRow[selected="true"] { border: 1px solid $accent; background: #1C2032; }
QFrame#DropZone { border: 2px dashed $border2; border-radius: 14px; background: $input; }
QFrame#StatTile { background: $card2; border: 1px solid $border; border-radius: 12px; }
QFrame#ToolCard { background: $card; border: 1px solid $border; border-radius: 14px; }
QFrame#ToolCard:hover { border-color: $border2; background: #151A25; }
QFrame#VideoPanel { background: #000000; border-radius: 10px; }
QPlainTextEdit#Console { font-family: "Cascadia Mono", "Consolas"; font-size: 12px; background: #07090D; color: #A9B1C4; }
QMenu { background: $card2; border: 1px solid $border2; border-radius: 8px; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 6px; }
QMenu::item:selected { background: rgba(124, 92, 255, 60); }
QMessageBox, QInputDialog, QColorDialog, QFileDialog { background: $card; }
""")


def _pick_font() -> str:
    fams = set(QFontDatabase.families())
    # Không dùng "Segoe UI Variable": Qt đo sai độ rộng chữ đậm của font variable → nút bị cụt chữ
    for f in ("Segoe UI", "Inter", "Arial"):
        if f in fams:
            return f
    return QFont().family()


def apply(app) -> None:
    global FONT
    from . import icons

    FONT = _pick_font()
    f = QFont(FONT, 10)
    f.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(f)
    values = dict(C, font=FONT,
                  check=icons.write_file("check", "#FFFFFF", 3.2),
                  chevron=icons.write_file("chevron-down", C["muted"], 2.4))
    app.setStyleSheet(QSS.substitute(values))
