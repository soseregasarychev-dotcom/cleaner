"""Всплывашка перед автоуборкой: «Через 60 с уберу — отложить?»."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from .. import phrases
from . import icons, theme, tone
from .widgets import label

SECONDS = 60


class CountdownPopup(QWidget):
    go = Signal()
    postpone = Signal(int)  # часов

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(540, 186)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.setSpacing(8)
        top = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(icons.app_pixmap(64).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        top.addWidget(logo)
        self.title = title = label("")
        title.setStyleSheet("font-size: 12pt; font-weight: 600;")
        top.addWidget(title)
        top.addStretch()
        lay.addLayout(top)
        self.text = label("", "Muted", wrap=True)
        lay.addWidget(self.text)
        self.bar = QProgressBar()
        self.bar.setFixedHeight(6)
        self.bar.setMaximum(SECONDS)
        lay.addWidget(self.bar)
        btns = QHBoxLayout()
        later = tone.bind(QPushButton(), "cd_hour")
        later.clicked.connect(lambda: self._postpone(1))
        tomorrow = tone.bind(QPushButton(), "cd_tomorrow")
        tomorrow.clicked.connect(lambda: self._postpone(24))
        now = tone.bind(QPushButton(), "cd_now")
        now.setObjectName("Primary")
        now.clicked.connect(self._go)
        btns.addWidget(later)
        btns.addWidget(tomorrow)
        btns.addStretch()
        btns.addWidget(now)
        lay.addLayout(btns)
        self._left = SECONDS
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._left = SECONDS
        self.title.setText(phrases.pick("countdown_title"))
        self._text = phrases.pick("countdown_text", left="{left}")
        self._update()
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.move(geo.right() - self.width() - 16, geo.bottom() - self.height() - 16)
        self.show()
        self.raise_()
        self._timer.start()

    def _tick(self) -> None:
        self._left -= 1
        if self._left <= 0:
            self._go()
        else:
            self._update()

    def _update(self) -> None:
        self.text.setText(self._text.replace("{left}", str(self._left)))
        self.bar.setValue(SECONDS - self._left)

    def _go(self) -> None:
        self._timer.stop()
        self.hide()
        self.go.emit()

    def _postpone(self, hours: int) -> None:
        self._timer.stop()
        self.hide()
        self.postpone.emit(hours)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QColor(theme.BORDER))
        p.setBrush(QColor(theme.CARD))
        p.drawRoundedRect(r, 16, 16)
