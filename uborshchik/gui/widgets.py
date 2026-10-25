"""Общие виджеты: переключатель, карточки, заголовки."""

from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme


class Switch(QAbstractButton):
    """Переключатель в стиле iOS."""

    def __init__(self, checked: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def sizeHint(self) -> QSize:
        return QSize(40, 24)

    def _animate(self, on: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, v: float) -> None:
        self._pos = v
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 2, 38, 20)
        off, on = QColor("#D5D1CA"), QColor(theme.ACCENT)
        if not self.isEnabled():
            off, on = QColor("#E6E3DE"), QColor("#A9D3C3")
        c = QColor(
            int(off.red() + (on.red() - off.red()) * self._pos),
            int(off.green() + (on.green() - off.green()) * self._pos),
            int(off.blue() + (on.blue() - off.blue()) * self._pos),
        )
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawRoundedRect(r, 10, 10)
        x = 3 + self._pos * 18
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(x, 4, 16, 16))


def card(parent: QWidget | None = None, shadow: bool = False) -> QFrame:
    f = QFrame(parent)
    f.setObjectName("Card")
    if shadow:
        eff = QGraphicsDropShadowEffect(f)
        eff.setBlurRadius(24)
        eff.setOffset(0, 4)
        eff.setColor(QColor(0, 0, 0, 22))
        f.setGraphicsEffect(eff)
    return f


def label(text: str = "", obj: str | None = None, wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    if obj:
        lb.setObjectName(obj)
    lb.setWordWrap(wrap)
    return lb


class StatCard(QFrame):
    clicked = Signal()

    def __init__(self, title: str, icon_color: str = theme.ACCENT, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(104)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(2)
        top = QHBoxLayout()
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background:{icon_color}; border-radius:4px;")
        top.addWidget(dot)
        t = label(title, "Muted")
        top.addWidget(t)
        top.addStretch()
        lay.addLayout(top)
        self.value = label("…")
        self.value.setStyleSheet("font-size: 19pt; font-weight: 600;")
        lay.addWidget(self.value)
        self.sub = label("считаю…", "Faint")
        lay.addWidget(self.sub)

    def set(self, value: str, sub: str = "") -> None:
        self.value.setText(value)
        self.sub.setText(sub)


class Banner(QFrame):
    def __init__(self, text: str = "", kind: str = "Banner", parent=None):
        super().__init__(parent)
        self.setObjectName(kind)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        self.text = label(text, wrap=True)
        lay.addWidget(self.text)

    def set_text(self, text: str) -> None:
        self.text.setText(text)
        self.setVisible(bool(text))


def row(*widgets, spacing: int = 10, stretch_end: bool = False) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    for w in widgets:
        if w is None:
            lay.addStretch()
        elif isinstance(w, QWidget):
            lay.addWidget(w)
        else:
            lay.addLayout(w)
    if stretch_end:
        lay.addStretch()
    return lay
