"""Иконки, нарисованные кодом: значок приложения и линейные иконки меню."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from . import theme


def app_pixmap(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 256.0

    # Скруглённый квадрат с градиентом
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor("#24A077"))
    grad.setColorAt(1, QColor("#2B6A8A"))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(QRectF(8 * s, 8 * s, 240 * s, 240 * s), 56 * s, 56 * s)

    white = QColor("white")
    # Ручка метлы
    pen = QPen(white, 18 * s, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(172 * s, 52 * s), QPointF(122 * s, 132 * s))

    # Метёлка
    p.setPen(Qt.NoPen)
    p.setBrush(white)
    path = QPainterPath()
    path.moveTo(104 * s, 120 * s)
    path.lineTo(146 * s, 146 * s)
    path.lineTo(118 * s, 206 * s)
    path.quadTo(84 * s, 204 * s, 56 * s, 180 * s)
    path.closeSubpath()
    p.drawPath(path)
    # Прорези прутьев
    p.setPen(QPen(QColor("#2A8A79"), 6 * s, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(112 * s, 160 * s), QPointF(94 * s, 192 * s))
    p.drawLine(QPointF(126 * s, 168 * s), QPointF(110 * s, 200 * s))

    # Искорки чистоты
    p.setPen(Qt.NoPen)
    p.setBrush(white)
    _sparkle(p, 190 * s, 150 * s, 20 * s)
    _sparkle(p, 168 * s, 196 * s, 11 * s)
    p.end()
    return pm


def _sparkle(p: QPainter, cx: float, cy: float, r: float) -> None:
    path = QPainterPath()
    path.moveTo(cx, cy - r)
    path.quadTo(cx, cy, cx + r, cy)
    path.quadTo(cx, cy, cx, cy + r)
    path.quadTo(cx, cy, cx - r, cy)
    path.quadTo(cx, cy, cx, cy - r)
    p.drawPath(path)


def app_icon() -> QIcon:
    icon = QIcon()
    for sz in (16, 20, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(app_pixmap(sz))
    return icon


def line_icon(name: str, color: str = "#3A3A3C", size: int = 20) -> QIcon:
    icon = QIcon()
    for scale in (1, 2):
        icon.addPixmap(_line_pixmap(name, color, size, scale))
    return icon


def nav_icon(name: str) -> QIcon:
    icon = QIcon()
    for scale in (1, 2):
        icon.addPixmap(_line_pixmap(name, "#55555A", 20, scale), QIcon.Normal, QIcon.Off)
        icon.addPixmap(_line_pixmap(name, theme.ACCENT, 20, scale), QIcon.Normal, QIcon.On)
    return icon


def _line_pixmap(name: str, color: str, size: int, scale: int) -> QPixmap:
    pm = QPixmap(size * scale, size * scale)
    pm.setDevicePixelRatio(scale)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    k = size / 20.0
    p.scale(k, k)

    if name == "home":
        path = QPainterPath()
        path.moveTo(3, 9.5)
        path.lineTo(10, 3.5)
        path.lineTo(17, 9.5)
        p.drawPath(path)
        p.drawRoundedRect(QRectF(5, 8.5, 10, 8.5), 1.5, 1.5)
        p.drawLine(QPointF(10, 17), QPointF(10, 13))
    elif name == "zone":
        dash = QPen(QColor(color), 1.7, Qt.CustomDashLine, Qt.RoundCap)
        dash.setDashPattern([2.2, 2.0])
        p.setPen(dash)
        p.drawRoundedRect(QRectF(3, 3, 14, 14), 3, 3)
        p.setPen(pen)
        p.drawRoundedRect(QRectF(7, 7, 6, 6), 1.2, 1.2)
    elif name == "archive":
        p.drawRoundedRect(QRectF(3, 4, 14, 4), 1.2, 1.2)
        p.drawRoundedRect(QRectF(4.5, 8, 11, 8.5), 1.2, 1.2)
        p.drawLine(QPointF(8, 11), QPointF(12, 11))
    elif name == "journal":
        for y in (5.5, 10, 14.5):
            p.drawLine(QPointF(7.5, y), QPointF(16.5, y))
            p.drawPoint(QPointF(4, y))
    elif name == "settings":
        for y, x in ((5, 12), (10, 7), (15, 13)):
            p.drawLine(QPointF(3, y), QPointF(17, y))
            p.setBrush(QColor("white"))
            p.drawEllipse(QPointF(x, y), 2.1, 2.1)
            p.setBrush(Qt.NoBrush)
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(3, 6)
        path.lineTo(3, 15.5)
        path.lineTo(17, 15.5)
        path.lineTo(17, 7.5)
        path.lineTo(9.5, 7.5)
        path.lineTo(8, 5)
        path.lineTo(3.5, 5)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "file":
        path = QPainterPath()
        path.moveTo(5, 3)
        path.lineTo(11.5, 3)
        path.lineTo(15, 6.5)
        path.lineTo(15, 17)
        path.lineTo(5, 17)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(11.5, 3), QPointF(11.5, 6.5))
        p.drawLine(QPointF(11.5, 6.5), QPointF(15, 6.5))
    elif name == "mask":
        for a, b in (((10, 4), (10, 16)), ((4.8, 7), (15.2, 13)), ((4.8, 13), (15.2, 7))):
            p.drawLine(QPointF(*a), QPointF(*b))
    elif name == "refresh":
        p.drawArc(QRectF(4, 4, 12, 12), 30 * 16, 290 * 16)
        p.drawLine(QPointF(15.5, 4), QPointF(15.5, 7.5))
        p.drawLine(QPointF(15.5, 7.5), QPointF(12, 7.5))
    elif name == "plus":
        p.drawLine(QPointF(10, 4), QPointF(10, 16))
        p.drawLine(QPointF(4, 10), QPointF(16, 10))
    elif name == "draw":
        p.drawLine(QPointF(4, 16), QPointF(15, 5))
        p.drawLine(QPointF(13, 3.5), QPointF(16.5, 7))
    p.end()
    return pm
