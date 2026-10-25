"""Сохранить значок приложения в assets/icon.ico (для exe)."""

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from uborshchik.gui.icons import app_pixmap  # noqa: E402

app = QGuiApplication(sys.argv)
buf = QBuffer()
buf.open(QIODevice.WriteOnly)
app_pixmap(256).save(buf, "PNG")
img = Image.open(io.BytesIO(bytes(buf.data())))
out = ROOT / "assets" / "icon.ico"
out.parent.mkdir(exist_ok=True)
img.save(out, sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(out)
