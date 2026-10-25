"""Перевод физических пикселей экрана (как у Проводника) в координаты Qt и обратно.

Qt 6 на Windows сохраняет «нативное» начало координат каждого монитора, а
размеры делит на коэффициент масштаба этого монитора.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QGuiApplication, QScreen


def _native_rect(s: QScreen) -> QRect:
    g = s.geometry()
    dpr = s.devicePixelRatio()
    return QRect(g.x(), g.y(), round(g.width() * dpr), round(g.height() * dpr))


def screen_for_phys(x: int, y: int) -> QScreen:
    for s in QGuiApplication.screens():
        if _native_rect(s).contains(x, y):
            return s
    return QGuiApplication.primaryScreen()


def phys_to_logical(x: int, y: int, s: QScreen | None = None) -> QPoint:
    s = s or screen_for_phys(x, y)
    g, dpr = s.geometry(), s.devicePixelRatio()
    return QPoint(round(g.x() + (x - g.x()) / dpr), round(g.y() + (y - g.y()) / dpr))


def logical_to_phys(p: QPoint, s: QScreen) -> tuple[int, int]:
    g, dpr = s.geometry(), s.devicePixelRatio()
    return round(g.x() + (p.x() - g.x()) * dpr), round(g.y() + (p.y() - g.y()) * dpr)


def zone_to_logical(zone: list[int]) -> QRect:
    left, top, right, bottom = zone
    s = screen_for_phys((left + right) // 2, (top + bottom) // 2)
    a = phys_to_logical(left, top, s)
    b = phys_to_logical(right, bottom, s)
    return QRect(a, b)
