
import sys
import base64
from PySide6.QtGui import QImage, QPainter, QColor, QPolygonF
from PySide6.QtCore import QBuffer, QIODevice, QPointF, Qt
from PySide6.QtWidgets import QApplication

def generate_arrow_png(up=True):
    size = 12
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor('#e0e0e0'))
    painter.setPen(Qt.NoPen)
    
    if up:
        # Points for upward triangle: (6, 2), (2, 10), (10, 10)
        points = [QPointF(6, 3), QPointF(2, 9), QPointF(10, 9)]
    else:
        # Points for downward triangle: (6, 10), (2, 2), (10, 2)
        points = [QPointF(6, 9), QPointF(2, 3), QPointF(10, 3)]
        
    painter.drawPolygon(QPolygonF(points))
    painter.end()
    
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return base64.b64encode(ba.data()).decode('utf-8')

app = QApplication(sys.argv)
print("UP_B64:", generate_arrow_png(True))
print("DOWN_B64:", generate_arrow_png(False))
