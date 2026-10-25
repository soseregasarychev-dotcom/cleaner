"""Показать рамку зоны на N секунд (проверка отрисовки). Ничего не убирает.

    .venv\\Scripts\\python.exe scripts\\overlay_demo.py L T R B [секунд]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from uborshchik.gui.zone import ZoneOverlay  # noqa: E402

zone = [int(x) for x in sys.argv[1:5]]
secs = int(sys.argv[5]) if len(sys.argv) > 5 else 15
app = QApplication(sys.argv)
ov = ZoneOverlay()
ov.set_zone(zone, True)
QTimer.singleShot(secs * 1000, app.quit)
app.exec()
