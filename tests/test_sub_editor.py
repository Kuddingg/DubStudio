"""Test cửa sổ Sửa phụ đề nâng cao: dòng thời gian kéo thả, hoàn tác / làm lại, gộp / tách câu, hỏi lưu khi đóng."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from core.project import Job  # noqa: E402
from core.srt import Cue, parse_srt, write_srt  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    from app import theme
    theme.apply(app)
    return app


@pytest.fixture
def dlg(qapp):
    job = Job(path="khong_co_video.mp4")
    zh = [Cue(1000, 3000, "", "一二"), Cue(4000, 6000, "", "三四"), Cue(7000, 9000, "", "五六")]
    vi = [Cue(1000, 3000, "", "Một hai"), Cue(4000, 6000, "", "Ba bốn"), Cue(7000, 9000, "", "Năm sáu")]
    (job.workdir / "sub_zh.srt").write_text(write_srt(zh, "dst"), "utf-8")
    (job.workdir / "sub_vi.srt").write_text(write_srt(vi, "dst"), "utf-8")
    from app.dialogs.sub_editor import SubEditorDialog
    d = SubEditorDialog(job, None, {})
    d.resize(1200, 860)
    d.show()
    tl = d.timeline
    tl.resize(1000, 110)
    tl.span, tl.view_start = 10000, 0               # 1000px = 10s → 1px = 10ms
    tl.set_duration(10000)
    QApplication.processEvents()
    yield d
    d._dirty = False
    d.close()


def drag(tl, x0, x1, y=60):
    QTest.mousePress(tl, Qt.LeftButton, Qt.NoModifier, QPoint(x0, y))
    QTest.mouseMove(tl, QPoint((x0 + x1) // 2, y))
    QTest.mouseMove(tl, QPoint(x1, y))
    QTest.mouseRelease(tl, Qt.LeftButton, Qt.NoModifier, QPoint(x1, y))


def px(d, ms):
    return int(round(d.timeline._x(ms)))


def spans(d):
    return [(c.start, c.end) for c in d.cues]


def test_drag_move_is_clamped_by_neighbours(dlg):
    drag(dlg.timeline, px(dlg, 5000), px(dlg, 9000))                   # kéo câu 2 (4–6s) sang phải 4s → bị chặn bởi câu 3 (7s)
    assert spans(dlg)[1] == (5000, 7000)
    assert dlg.table.currentIndex().row() == 1 and dlg.model.data(dlg.model.index(1, 1)) == "00:00:05,000"


def test_drag_edge_resizes(dlg):
    drag(dlg.timeline, px(dlg, 3000), px(dlg, 3500))                     # mép phải câu 1 (3s) → 3.5s
    assert spans(dlg)[0] == (1000, 3500)


def test_click_empty_area_seeks(dlg):
    got = []
    dlg.timeline.seek.connect(got.append)
    QTest.mouseClick(dlg.timeline, Qt.LeftButton, Qt.NoModifier, QPoint(px(dlg, 3500), 60))
    assert abs(got[0] - 3500) <= 20


def test_undo_redo_covers_drag_merge_split_delete(dlg):
    orig = spans(dlg)
    drag(dlg.timeline, px(dlg, 3000), px(dlg, 3500))
    dlg.table.selectRow(0)
    dlg._merge_next()
    assert len(dlg.cues) == 2 and dlg.cues[0].dst == "Một hai Ba bốn" and dlg.cues[0].src == "一二三四"
    dlg._del_row()
    assert len(dlg.cues) == 1
    dlg.undo(); dlg.undo(); dlg.undo()
    assert spans(dlg) == orig and len(dlg.cues) == 3
    dlg.redo()
    assert spans(dlg)[0] == (1000, 3500)


def test_split_at_cursor(dlg):
    dlg.table.selectRow(2)                           # "Năm sáu" 7–9s
    cur = dlg.ed_dst.textCursor()
    cur.setPosition(3)
    dlg.ed_dst.setTextCursor(cur)
    dlg._split()
    assert [c.dst for c in dlg.cues[2:]] == ["Năm", "sáu"]
    assert dlg.cues[2].end == dlg.cues[3].start == 8000      # đầu phát ngoài câu → tách giữa


def test_ask_to_save_on_close(dlg, monkeypatch):
    drag(dlg.timeline, px(dlg, 3000), px(dlg, 3500))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Save))
    dlg.done(0)
    saved = parse_srt(dlg.srt_vi.read_text("utf-8"))
    assert (saved[0].start, saved[0].end) == (1000, 3500)
