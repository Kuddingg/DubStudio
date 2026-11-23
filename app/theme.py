"""Bảng màu + stylesheet toàn app (chế độ tối / sáng)."""
from string import Template

from PySide6.QtGui import QColor, QFont, QFontDatabase

DARK = {
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
    # màu phụ (trước đây ghi cứng trong QSS)
    "sel_text": "#FFFFFF",          # chữ trên nền đang chọn (menu trái, nút phân đoạn…)
    "btn_hover": "#222838",
    "btn_hover_border": "#3A4258",
    "btn_pressed": "#151924",
    "danger_text": "#FF8FA3",
    "scroll": "#262C3B",
    "scroll_hover": "#39425A",
    "alt_row": "#10141C",
    "row_sel": "#1C2032",
    "tool_hover": "#151A25",
    "console_bg": "#07090D",
    "console_text": "#A9B1C4",
    "chip_ok": "#4ADE80",
    "chip_run": "#C4B5FF",
    "chip_err": "#FF8FA3",
    "chip_warn": "#FCC86B",
    "chip_info": "#67E8F9",
    "switch_off": "#2A3142",
    "tint": "124, 92, 255",          # màu nhấn dạng r, g, b cho nền trong suốt
    "primary_h1": "#8E72FF", "primary_h2": "#6F9BFF",
    "on_primary": "#FFFFFF",
    "radius": "14px", "radius_sm": "9px",
}

LIGHT = {
    "bg": "#F3F4F8",
    "surface": "#FFFFFF",
    "card": "#FFFFFF",
    "card2": "#F1F3F7",
    "input": "#FFFFFF",
    "border": "#E1E4EB",
    "border2": "#CBD0DA",
    "text": "#161A24",
    "muted": "#5B6376",
    "dim": "#8D94A5",
    "accent": "#6D4AFF",
    "accent2": "#4C7DFF",
    "cyan": "#0891B2",
    "green": "#16A34A",
    "red": "#E11D48",
    "amber": "#D97706",
    "sel_text": "#3A22C9",
    "btn_hover": "#E9ECF2",
    "btn_hover_border": "#B9C0CD",
    "btn_pressed": "#DFE3EB",
    "danger_text": "#C8243F",
    "scroll": "#CDD2DC",
    "scroll_hover": "#A8B0BF",
    "alt_row": "#F6F7FA",
    "row_sel": "#F1EDFF",
    "tool_hover": "#F8F9FC",
    "console_bg": "#F7F8FB",
    "console_text": "#3A4255",
    "chip_ok": "#15803D",
    "chip_run": "#5B3FD6",
    "chip_err": "#C8243F",
    "chip_warn": "#A15C07",
    "chip_info": "#0E7490",
    "switch_off": "#C9CED9",
    "tint": "109, 74, 255",
    "primary_h1": "#7E60FF", "primary_h2": "#5E8CFF",
    "on_primary": "#FFFFFF",
    "radius": "14px", "radius_sm": "9px",
}

# Phong cách "Cam": nền đen ấm, thẻ bo lớn, nhấn cam, nút chính trắng
WARM = {
    "bg": "#0B0B0C",
    "surface": "#111113",
    "card": "#18181B",
    "card2": "#222226",
    "input": "#131315",
    "border": "#26262B",
    "border2": "#36363C",
    "text": "#F4F4F5",
    "muted": "#A1A1AA",
    "dim": "#68686F",
    "accent": "#FF6B1A",
    "accent2": "#FF9440",
    "cyan": "#E8D44D",
    "green": "#4ADE80",
    "red": "#F43F5E",
    "amber": "#F5B524",
    "sel_text": "#FFFFFF",
    "btn_hover": "#2A2A2F",
    "btn_hover_border": "#47474F",
    "btn_pressed": "#1B1B1E",
    "danger_text": "#FF8FA3",
    "scroll": "#2C2C31",
    "scroll_hover": "#44444B",
    "alt_row": "#151517",
    "row_sel": "#2A1D15",
    "tool_hover": "#1E1E22",
    "console_bg": "#0E0E10",
    "console_text": "#B4B4BB",
    "chip_ok": "#4ADE80",
    "chip_run": "#FFB27A",
    "chip_err": "#FF8FA3",
    "chip_warn": "#FCD34D",
    "chip_info": "#E8D44D",
    "switch_off": "#34343A",
    "tint": "255, 107, 26",
    "primary_h1": "#FF8236", "primary_h2": "#FFAA5E",
    "on_primary": "#FFFFFF",
    "radius": "20px", "radius_sm": "14px",
}

# Tên hiển thị trong tab Hệ thống → giá trị nội bộ
MODES = {"Tối": "dark", "Sáng": "light", "Cam": "warm", "Theo Windows": "system"}

C = dict(DARK)        # các module import C trực tiếp → luôn sửa tại chỗ, không gán lại
MODE = "dark"         # chế độ đang dùng thật sự ("dark" / "light")

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
QPushButton#Nav:checked { background: rgba($tint, 38); color: $sel_text; }
#TopBar { background: $bg; border-bottom: 1px solid $border; }
#PageTitle { font-size: 19px; font-weight: 700; }
#PageSub { color: $muted; font-size: 12px; }
QFrame#Pill { background: $card; border: 1px solid $border; border-radius: 15px; }
QFrame#PlanBox { background: $card; border: 1px solid $border; border-radius: 12px; }

/* ---------- Cards / labels ---------- */
QFrame#Card { background: $card; border: 1px solid $border; border-radius: $radius; }
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
QComboBox QAbstractItemView::item:hover, QComboBox QAbstractItemView::item:selected { background: rgba($tint, 60); color: $sel_text; }

/* ---------- Buttons ---------- */
QPushButton { background: $card2; border: 1px solid $border2; border-radius: $radius_sm; padding: 7px 14px; font-weight: 600; color: $text; }
QPushButton:hover { background: $btn_hover; border-color: $btn_hover_border; }
QPushButton:pressed { background: $btn_pressed; }
QPushButton:disabled { color: $dim; background: $card; border-color: $border; }
QPushButton[variant="primary"] { border: none; color: $on_primary;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $accent, stop:1 $accent2); }
QPushButton[variant="primary"]:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $primary_h1, stop:1 $primary_h2); }
QPushButton[variant="primary"]:pressed { background: $accent; }
QPushButton[variant="primary"]:disabled { background: $card2; color: $dim; }
QPushButton[variant="danger"] { background: rgba(244, 63, 94, 28); border: 1px solid rgba(244, 63, 94, 90); color: $danger_text; }
QPushButton[variant="danger"]:hover { background: rgba(244, 63, 94, 55); }
QPushButton[variant="danger"]:disabled { background: $card; border-color: $border; color: $dim; }
QPushButton[variant="ghost"] { background: transparent; border: 1px solid transparent; color: $muted; }
QPushButton[variant="ghost"]:hover { background: $card2; color: $text; }
QPushButton[variant="tool"] { background: $input; border: 1px solid $border; padding: 6px 10px; font-weight: 500; }
QPushButton[variant="tool"]:hover { border-color: $border2; background: $card2; }
QPushButton[variant="tool"]:checked { border-color: $accent; background: rgba($tint, 40); }
QPushButton#Seg { border-radius: 0; background: $input; border: 1px solid $border; padding: 6px 8px; font-weight: 500; color: $muted; }
QPushButton#Seg[pos="first"] { border-top-left-radius: 8px; border-bottom-left-radius: 8px; }
QPushButton#Seg[pos="last"] { border-top-right-radius: 8px; border-bottom-right-radius: 8px; }
QPushButton#Seg:hover { color: $text; }
QPushButton#Seg:checked { background: rgba($tint, 45); color: $sel_text; border-color: $accent; }

/* ---------- Check / slider / progress ---------- */
QCheckBox { spacing: 8px; color: $text; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 5px; border: 1px solid $border2; background: $input; }
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; image: url("$check"); }
QSlider { min-height: 18px; }
QSlider::groove:horizontal { height: 4px; background: $border; border-radius: 2px; }
QSlider::sub-page:horizontal { border-radius: 2px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $accent, stop:1 $accent2); }
QSlider::handle:horizontal { background: #FFFFFF; border: 1px solid $border2; width: 12px; height: 12px; margin: -5px 0; border-radius: 7px; }
QSlider::handle:horizontal:hover { background: #DCD3FF; }
QProgressBar { background: $input; border: none; border-radius: 3px; min-height: 6px; max-height: 6px; }
QProgressBar::chunk { border-radius: 3px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $accent, stop:1 $cyan); }

/* ---------- Scroll ---------- */
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $scroll; border-radius: 3px; min-height: 30px; margin: 0 2px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: $scroll_hover; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $scroll; border-radius: 3px; min-width: 30px; margin: 2px 0; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

/* ---------- Lists / tables ---------- */
QListWidget { background: transparent; border: none; outline: 0; }
QListWidget#Presets::item { padding: 9px 12px; border-radius: 8px; color: $muted; margin: 1px 0; }
QListWidget#Presets::item:hover { background: $card2; color: $text; }
QListWidget#Presets::item:selected { background: rgba($tint, 45); color: $sel_text; }
QTableView, QTableWidget { background: $input; border: 1px solid $border; border-radius: 10px; gridline-color: transparent;
    selection-background-color: rgba($tint, 60); selection-color: $sel_text; alternate-background-color: $alt_row; outline: 0; }
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
QLabel#Chip[tone="ok"] { background: rgba(34, 197, 94, 35); color: $chip_ok; }
QLabel#Chip[tone="run"] { background: rgba($tint, 50); color: $chip_run; }
QLabel#Chip[tone="err"] { background: rgba(244, 63, 94, 40); color: $chip_err; }
QLabel#Chip[tone="warn"] { background: rgba(245, 165, 36, 38); color: $chip_warn; }
QLabel#Chip[tone="info"] { background: rgba(34, 211, 238, 32); color: $chip_info; }
QFrame#JobRow { background: $card2; border: 1px solid $border; border-radius: $radius_sm; }
QFrame#JobRow:hover { border-color: $border2; }
QFrame#JobRow[selected="true"] { border: 1px solid $accent; background: $row_sel; }
QFrame#DropZone { border: 2px dashed $border2; border-radius: 14px; background: $input; }
QFrame#StatTile { background: $card2; border: 1px solid $border; border-radius: 12px; }
QFrame#ToolCard { background: $card; border: 1px solid $border; border-radius: $radius; }
QFrame#ToolCard:hover { border-color: $border2; background: $tool_hover; }
QFrame#VideoPanel { background: #000000; border-radius: 10px; }
QPlainTextEdit#Console { font-family: "Cascadia Mono", "Consolas"; font-size: 12px; background: $console_bg; color: $console_text; }
QMenu { background: $card2; border: 1px solid $border2; border-radius: 8px; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 6px; }
QMenu::item:selected { background: rgba($tint, 60); }
QMessageBox, QInputDialog, QColorDialog, QFileDialog { background: $card; }
""")

WARM_QSS = """
#Sidebar { background: $bg; border-right: none; }
#TopBar { border-bottom: none; }
QPushButton#Nav { border-radius: 14px; }
QPushButton#Nav:checked { background: $card2; color: $text; }
QFrame#Pill, QFrame#PlanBox, QFrame#StatTile { border-radius: 16px; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit { border-radius: 12px; }
QFrame#DropZone { border-radius: 18px; }
"""


def _load_fonts() -> None:
    """Nạp font đi kèm app (assets/fonts/*.ttf), vd Be Vietnam Pro."""
    from core.runtime import RES_DIR
    for f in sorted((RES_DIR / "assets" / "fonts").glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(f))


def _pick_font() -> str:
    _load_fonts()
    fams = set(QFontDatabase.families())
    # Không dùng "Segoe UI Variable": Qt đo sai độ rộng chữ đậm của font variable → nút bị cụt chữ
    for f in ("Be Vietnam Pro", "Segoe UI", "Inter", "Arial"):
        if f in fams:
            return f
    return QFont().family()


def resolve(mode: str) -> str:
    """'dark' / 'light' / 'system' (hoặc tên hiển thị) → 'dark' / 'light'."""
    mode = MODES.get(mode, mode)
    if mode == "system":
        try:
            from PySide6.QtCore import Qt
            from PySide6.QtGui import QGuiApplication
            return "light" if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Light else "dark"
        except Exception:  # noqa: BLE001 - Qt cũ / không đọc được → tối
            return "dark"
    return mode if mode in ("light", "warm") else "dark"


def apply(app, mode: str = "dark") -> None:
    global FONT, MODE
    from . import icons

    MODE = resolve(mode)
    C.clear()
    C.update({"light": LIGHT, "warm": WARM}.get(MODE, DARK))
    FONT = _pick_font()
    f = QFont(FONT, 10)
    f.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(f)
    values = dict(C, font=FONT,
                  check=icons.write_file("check", "#FFFFFF", 3.2),
                  chevron=icons.write_file("chevron-down", C["muted"], 2.4))
    qss = QSS.substitute(values)
    if MODE == "warm":
        qss += Template(WARM_QSS).substitute(values)
    app.setStyleSheet(qss)
