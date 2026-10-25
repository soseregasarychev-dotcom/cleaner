"""Зона покоя на рабочем столе: постоянная рамка и окно, где её рисуют."""

from __future__ import annotations

import ctypes

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .. import desktop_icons, phrases
from . import theme
from .screens import logical_to_phys, zone_to_logical

_user32 = ctypes.windll.user32
_user32.FindWindowW.restype = ctypes.c_void_p
_user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
_user32.SetWindowLongPtrW.restype = ctypes.c_void_p
_user32.SetWindowPos.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.c_uint,
]
_user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
_user32.GetWindowLongPtrW.restype = ctypes.c_void_p
_user32.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
_user32.GetWindow.restype = ctypes.c_void_p
_user32.GetParent.argtypes = [ctypes.c_void_p]
_user32.GetParent.restype = ctypes.c_void_p
GWLP_HWNDPARENT = -8
GW_HWNDPREV = 3
HWND_BOTTOM = ctypes.c_void_p(1)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10


def desktop_host() -> int | None:
    """Окно верхнего уровня, в котором сейчас значки рабочего стола (Progman или WorkerW)."""
    try:
        lv = desktop_icons.find_desktop_listview()
        defview = _user32.GetParent(ctypes.c_void_p(lv))
        host = _user32.GetParent(ctypes.c_void_p(defview)) if defview else None
        if host:
            return host
    except desktop_icons.DesktopIconsError:
        pass
    return _user32.FindWindowW("Progman", None)


class ZoneOverlay(QWidget):
    """Полупрозрачная рамка поверх рабочего стола.

    Клики проходят насквозь, окно не берёт фокус и принадлежит окну со значками
    рабочего стола — поэтому стоит прямо над ними и не пропадает по Win+D.
    """

    def __init__(self):
        super().__init__(
            None,
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnBottomHint
            | Qt.WindowTransparentForInput
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._zone: list[int] | None = None
        self._keep_bottom = QTimer(self)
        self._keep_bottom.setInterval(3000)
        self._keep_bottom.timeout.connect(self._to_bottom)

    def set_zone(self, zone: list[int] | None, visible: bool) -> None:
        self._zone = zone
        if not zone or not visible:
            self.hide()
            self._keep_bottom.stop()
            return
        rect = zone_to_logical(zone)
        self.setGeometry(rect.adjusted(-2, -2, 2, 2))
        self.show()
        self._attach_to_desktop()
        self._keep_bottom.start()
        self.update()

    def _attach_to_desktop(self) -> None:
        self._to_bottom()

    def _to_bottom(self) -> None:
        """Держать рамку прямо над окном, в котором сейчас живут значки рабочего стола.

        Проводник переносит значки из Progman в WorkerW (после «Свернуть все окна»,
        слайд-шоу обоев и т. п.) и по Win+D поднимает это окно наверх. Окно-владелец
        всегда тянет за собой своё «дочернее» — поэтому владельцем делаем именно хозяина
        значков и проверяем его раз в 3 секунды.
        """
        if not self.isVisible():
            return
        hwnd = ctypes.c_void_p(int(self.winId()))
        host = desktop_host()
        if host and _user32.GetWindowLongPtrW(hwnd, GWLP_HWNDPARENT) != host:
            _user32.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, ctypes.c_void_p(host))
        above = _user32.GetWindow(ctypes.c_void_p(host), GW_HWNDPREV) if host else None
        if above and above != hwnd.value:
            # Встать сразу над хозяином значков (под тем, кто был над ним)
            _user32.SetWindowPos(hwnd, ctypes.c_void_p(above), 0, 0, 0, 0,
                                 SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        elif not host:
            _user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0,
                                 SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        c = QColor(theme.ZONE)

        fill = QColor(c)
        fill.setAlpha(26)
        p.setPen(Qt.NoPen)
        p.setBrush(fill)
        p.drawRoundedRect(r, 14, 14)

        # Светлая подложка под пунктиром — контраст на тёмных обоях
        p.setPen(QPen(QColor(255, 255, 255, 90), 4.5))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 14, 14)

        edge = QColor(c)
        edge.setAlpha(225)
        pen = QPen(edge, 2.4, Qt.CustomDashLine, Qt.RoundCap)
        pen.setDashPattern([5, 3])
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 14, 14)

        # Подпись-«таблетка» внизу по центру
        f = theme.font(8.5, theme.QFont.Weight.DemiBold)
        p.setFont(f)
        text = phrases.btn("zone_label")
        tw = p.fontMetrics().horizontalAdvance(text) + 22
        th = 22
        pill = QRectF(r.center().x() - tw / 2, r.bottom() - th - 8, tw, th)
        bg = QColor(c)
        bg.setAlpha(215)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(pill, th / 2, th / 2)
        p.setPen(QColor("white"))
        p.drawText(pill, Qt.AlignCenter, text)


class ZonePicker(QWidget):
    """Полноэкранное окно на одном мониторе: обвести мышью новую зону."""

    picked = Signal(list)  # [left, top, right, bottom] в физических пикселях
    cancelled = Signal()

    def __init__(self, screen, current: list[int] | None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._screen = screen
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        self.setCursor(Qt.CrossCursor)
        self._start: QPoint | None = None
        self._end: QPoint | None = None
        self._current = None
        if current:
            cr = zone_to_logical(current)
            if screen.geometry().intersects(cr):
                self._current = cr.translated(-screen.geometry().topLeft())

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key_Escape:
            self.cancelled.emit()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self._start = self._end = e.position().toPoint()
            self.update()
        elif e.button() == Qt.RightButton:
            self.cancelled.emit()

    def mouseMoveEvent(self, e) -> None:
        if self._start is not None:
            self._end = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() != Qt.LeftButton or self._start is None:
            return
        rect = QRect(self._start, e.position().toPoint()).normalized()
        self._start = None
        if rect.width() < 40 or rect.height() < 40:
            self.update()
            return
        origin = self._screen.geometry().topLeft()
        l, t = logical_to_phys(rect.topLeft() + origin, self._screen)
        r, b = logical_to_phys(rect.bottomRight() + origin, self._screen)
        self.picked.emit([l, t, r, b])

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        full = QPainterPath()
        full.addRect(QRectF(self.rect()))
        sel = None
        if self._start is not None and self._end is not None:
            sel = QRectF(QRect(self._start, self._end).normalized())
        elif self._current is not None:
            sel = QRectF(self._current)
        shade = full
        if sel is not None:
            hole = QPainterPath()
            hole.addRoundedRect(sel, 14, 14)
            shade = full.subtracted(hole)
        p.fillPath(shade, QColor(18, 24, 22, 120))

        if sel is not None:
            edge = QColor(theme.ZONE)
            edge.setAlpha(240)
            pen = QPen(edge, 2.5, Qt.CustomDashLine)
            pen.setDashPattern([5, 3])
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(sel, 14, 14)

        # Подсказка
        text = "Обведите мышью область, которую Уборщик не трогает   ·   Esc — отмена"
        p.setFont(theme.font(12, theme.QFont.Weight.DemiBold))
        fm = p.fontMetrics()
        w = fm.horizontalAdvance(text) + 40
        box = QRectF((self.width() - w) / 2, 40, w, 46)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 235))
        p.drawRoundedRect(box, 23, 23)
        p.setPen(QColor(theme.TEXT))
        p.drawText(box, Qt.AlignCenter, text)


class ZonePickSession:
    """По окну-«рисовалке» на каждый монитор; результат — в callback."""

    def __init__(self, current: list[int] | None, on_done):
        self._on_done = on_done
        self._windows: list[ZonePicker] = []
        for s in QGuiApplication.screens():
            w = ZonePicker(s, current)
            w.picked.connect(self._finish)
            w.cancelled.connect(lambda: self._finish(None))
            self._windows.append(w)
        for w in self._windows:
            w.show()
            w.raise_()
        if self._windows:
            self._windows[0].activateWindow()

    def _finish(self, zone) -> None:
        for w in self._windows:
            w.close()
        self._windows.clear()
        self._on_done(zone)
