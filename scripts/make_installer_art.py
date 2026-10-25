"""Картинки для мастера установки Inno Setup (BMP в assets/)."""

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter  # noqa: E402

from uborshchik.gui.icons import app_pixmap  # noqa: E402

app = QGuiApplication(sys.argv)
OUT = ROOT / "assets"
OUT.mkdir(exist_ok=True)


def save_bmp(img: QImage, name: str) -> None:
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    Image.open(io.BytesIO(bytes(buf.data()))).convert("RGB").save(OUT / name, "BMP")


def big(w: int, h: int) -> QImage:
    """Левая картинка мастера: градиент, значок, название, девиз."""
    k = w / 164
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor("#24A077"))
    g.setColorAt(1, QColor("#2B6A8A"))
    p.fillRect(img.rect(), g)
    # Лёгкая «чертёжная» сетка
    p.setPen(QColor(255, 255, 255, 18))
    step = int(14 * k)
    for x in range(0, w, step):
        p.drawLine(x, 0, x, h)
    for y in range(0, h, step):
        p.drawLine(0, y, w, y)
    icon = int(84 * k)
    pm = app_pixmap(256).scaled(icon, icon, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    p.drawPixmap((w - icon) // 2, int(70 * k), pm)
    p.setPen(QColor("white"))
    f = QFont("Segoe UI", 1)
    f.setPixelSize(int(22 * k))
    f.setWeight(QFont.Weight.Bold)
    p.setFont(f)
    p.drawText(QRectF(0, 166 * k, w, 30 * k), Qt.AlignHCenter, "Уборщик")
    f.setPixelSize(int(10.5 * k))
    f.setWeight(QFont.Weight.Normal)
    p.setFont(f)
    p.setPen(QColor(255, 255, 255, 215))
    p.drawText(
        QRectF(10 * k, 200 * k, w - 20 * k, 60 * k),
        Qt.AlignHCenter | Qt.TextWordWrap,
        "Чистый рабочий стол —\nчистая совесть",
    )
    p.end()
    return img


def small(s: int) -> QImage:
    img = QImage(s, s, QImage.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    pm = app_pixmap(256).scaled(s, s, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    p.drawPixmap(0, 0, pm)
    p.end()
    return img


# 100%, 125%, 150% масштаба Windows
for i, (w, h) in enumerate([(164, 314), (205, 392), (246, 471)]):
    save_bmp(big(w, h), f"wizard_big_{i}.bmp")
for i, s in enumerate([55, 69, 83]):
    save_bmp(small(s), f"wizard_small_{i}.bmp")
print("ok")
