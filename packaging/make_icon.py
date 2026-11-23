"""Vẽ icon app (gradient tím → xanh + sóng âm) ra packaging/dubstudio.ico nhiều kích thước."""
import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPen

HERE = Path(__file__).parent
app = QGuiApplication(sys.argv)
S = 256
img = QImage(S, S, QImage.Format_ARGB32)
img.fill(Qt.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)
g = QLinearGradient(0, 0, S, S)
g.setColorAt(0, QColor("#7C5CFF"))
g.setColorAt(1, QColor("#22D3EE"))
p.setPen(Qt.NoPen)
p.setBrush(g)
p.drawRoundedRect(QRectF(8, 8, S - 16, S - 16), 60, 60)
pen = QPen(QColor("#FFFFFF"), 18, Qt.SolidLine, Qt.RoundCap)
p.setPen(pen)
cx = S / 2
for x, h in [(-72, 30), (-36, 80), (0, 130), (36, 70), (72, 34)]:
    p.drawLine(int(cx + x), int(S / 2 - h / 2), int(cx + x), int(S / 2 + h / 2))
p.end()
png = HERE / "dubstudio.png"
img.save(str(png))
Image.open(png).save(HERE / "dubstudio.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("ok", HERE / "dubstudio.ico")
