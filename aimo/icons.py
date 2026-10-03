"""One stroke system for all native application and shell icons."""
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPen, QPainterPath, QPixmap, QIcon, QColor
from .theme import THEME


def draw_icon(p, name, rect, color=None, width=1.6):
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.translate(rect.x(), rect.y())
    p.scale(rect.width() / 24, rect.height() / 24)
    pen = QPen(color or THEME.c("text"), width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    if name in ("folder", "files"):
        path.moveTo(3, 7); path.lineTo(3, 19); path.lineTo(21, 19); path.lineTo(21, 7)
        path.lineTo(12, 7); path.lineTo(10, 4); path.lineTo(3, 4); path.closeSubpath()
        p.drawPath(path)
    elif name in ("note", "file"):
        path.moveTo(5, 3); path.lineTo(14, 3); path.lineTo(19, 8); path.lineTo(19, 21)
        path.lineTo(5, 21); path.closeSubpath(); p.drawPath(path)
        p.drawLine(14, 3, 14, 8); p.drawLine(14, 8, 19, 8)
        p.drawLine(8, 12, 16, 12); p.drawLine(8, 16, 14, 16)
    elif name in ("browser", "globe"):
        p.drawEllipse(QRectF(3, 3, 18, 18)); p.drawEllipse(QRectF(8, 3, 8, 18))
        p.drawLine(3, 12, 21, 12); p.drawLine(5, 7, 19, 7); p.drawLine(5, 17, 19, 17)
    elif name == "terminal":
        p.drawRoundedRect(QRectF(3, 5, 18, 14), 2, 2)
        p.drawLine(7, 9, 10, 12); p.drawLine(10, 12, 7, 15); p.drawLine(13, 15, 17, 15)
    elif name == "calculator":
        p.drawRoundedRect(QRectF(5, 2, 14, 20), 2, 2); p.drawRect(QRectF(8, 5, 8, 4))
        for x in [8, 12, 16]:
            for y in [13, 17]: p.drawPoint(QPointF(x, y))
    elif name == "settings":
        for y, x in [(6, 9), (12, 15), (18, 8)]:
            p.drawLine(3, y, x-3, y); p.drawLine(x+3, y, 21, y)
            p.drawEllipse(QRectF(x-2.5, y-2.5, 5, 5))
    elif name == "start":
        path.moveTo(4, 20); path.lineTo(12, 3); path.lineTo(20, 20)
        p.drawPath(path); p.drawLine(8, 13, 16, 13)
    elif name == "close":
        p.drawLine(7, 7, 17, 17); p.drawLine(7, 17, 17, 7)
    elif name == "minimize": p.drawLine(6, 15, 18, 15)
    elif name == "maximize": p.drawRect(QRectF(6, 6, 12, 12))
    elif name == "restore":
        p.drawRect(QRectF(5, 8, 11, 11)); p.drawLine(8, 5, 19, 5)
        p.drawLine(19, 5, 19, 16)
    elif name in ("back", "forward", "chevron"):
        sign = -1 if name == "back" else 1
        p.drawLine(12-sign*3, 6, 12+sign*3, 12)
        p.drawLine(12+sign*3, 12, 12-sign*3, 18)
    elif name == "refresh":
        p.drawArc(QRectF(4, 4, 16, 16), 45*16, 285*16)
        p.drawLine(18, 4, 18, 9); p.drawLine(13, 9, 18, 9)
    elif name == "home":
        path.moveTo(3, 11); path.lineTo(12, 3); path.lineTo(21, 11)
        p.drawPath(path); p.drawLine(6, 9, 6, 21); p.drawLine(6, 21, 18, 21)
        p.drawLine(18, 21, 18, 9); p.drawRect(QRectF(10, 14, 4, 7))
    elif name == "search":
        p.drawEllipse(QRectF(4, 3, 12, 12)); p.drawLine(14, 14, 20, 20)
    elif name == "user":
        p.drawEllipse(QRectF(8, 3, 8, 8)); p.drawArc(QRectF(4, 14, 16, 14), 0, 180*16)
    elif name == "power":
        p.drawArc(QRectF(4, 4, 16, 16), 130*16, 280*16); p.drawLine(12, 2, 12, 11)
    elif name == "lock":
        p.drawRoundedRect(QRectF(5, 10, 14, 11), 2, 2)
        p.drawArc(QRectF(8, 2, 8, 14), 0, 180*16); p.drawLine(12, 14, 12, 17)
    elif name == "network":
        for r in [15, 10, 5]:
            p.drawArc(QRectF(12-r, 7-r, r*2, r*2), 40*16, 100*16)
        p.drawPoint(QPointF(12, 19))
    elif name == "volume":
        path.moveTo(4, 9); path.lineTo(8, 9); path.lineTo(13, 5); path.lineTo(13, 19)
        path.lineTo(8, 15); path.lineTo(4, 15); path.closeSubpath(); p.drawPath(path)
        p.drawArc(QRectF(11, 5, 10, 14), -65*16, 130*16)
    elif name == "trash":
        p.drawLine(4, 6, 20, 6); p.drawRect(QRectF(9, 3, 6, 3))
        path.moveTo(6, 6); path.lineTo(7, 21); path.lineTo(17, 21); path.lineTo(18, 6)
        p.drawPath(path); p.drawLine(10, 10, 10, 17); p.drawLine(14, 10, 14, 17)
    elif name == "save":
        p.drawRect(QRectF(4, 3, 16, 18)); p.drawRect(QRectF(8, 3, 8, 6))
        p.drawRect(QRectF(7, 14, 10, 7))
    elif name == "plus":
        p.drawLine(5, 12, 19, 12); p.drawLine(12, 5, 12, 19)
    elif name == "check":
        path.moveTo(5, 12); path.lineTo(10, 17); path.lineTo(20, 6); p.drawPath(path)
    else:
        p.drawRoundedRect(QRectF(4, 4, 16, 16), 3, 3)
        p.drawLine(8, 8, 16, 8); p.drawLine(8, 12, 16, 12); p.drawLine(8, 16, 12, 16)
    p.restore()


def icon(name, size=24, color=None):
    pix = QPixmap(size*2, size*2); pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix); draw_icon(p, name, QRectF(0, 0, size*2, size*2), color); p.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)
