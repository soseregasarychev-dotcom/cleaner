"""Скриншоты страниц окна в PNG (для проверки вёрстки). Ничего не убирает.

    .venv\\Scripts\\python.exe scripts\\shot.py <папка> [--preview]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from uborshchik.gui import icons, theme  # noqa: E402
from uborshchik.gui.app import Controller  # noqa: E402
from uborshchik.gui.preview import PreviewDialog  # noqa: E402

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
want_preview = "--preview" in sys.argv

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(theme.QSS)
app.setFont(theme.font(10))
ctl = Controller(app)
ctl.tick.stop()
ctl.daily.stop()
win = ctl.window
win.show()
icons.app_pixmap(256).save(str(out / "icon.png"))


def shoot(plan):
    for i, name in enumerate(["home", "protect", "archive", "journal", "settings"]):
        win.go(i)
        app.processEvents()
        win.grab().save(str(out / f"{i}_{name}.png"))
    if want_preview and plan is not None:
        dlg = PreviewDialog(plan, ctl._last_scan[2], win)
        dlg.setStyleSheet(theme.QSS)
        dlg.show()
        app.processEvents()
        dlg.grab().save(str(out / "5_preview.png"))
        dlg.stack.setCurrentIndex(1)
        dlg.on_progress(40, 100, "Визуализация узла 9А.pdf")
        app.processEvents()
        dlg.grab().save(str(out / "6_progress.png"))
    ctl.countdown.start()
    app.processEvents()
    ctl.countdown.grab().save(str(out / "7_countdown.png"))
    ctl.quit()


ctl.scan_updated.connect(lambda p: QTimer.singleShot(300, lambda: shoot(p)))
ctl.rescan()
QTimer.singleShot(240_000, app.quit)
app.exec()
