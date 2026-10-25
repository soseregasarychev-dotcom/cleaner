"""Контроллер приложения: настройки, трей, расписание, запуск уборок."""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .. import APP_ID, APP_NAME, autostart, paths, phrases, schedule
from ..config import Settings
from ..executor import Journal, RunReport, execute
from ..fsops import Guard, delete_path
from ..planner import Locations, Plan, purge_actions, route_exclusions
from ..util import human_date, human_size, plural
from . import icons, theme, tone
from .countdown import CountdownPopup
from .main_window import MainWindow
from .preview import PreviewDialog
from .workers import ExecWorker, PlanWorker
from .zone import ZoneOverlay, ZonePickSession

SERVER_NAME = f"{APP_ID}-{os.environ.get('USERNAME', 'user')}"
START_DELAY_MS = 5 * 60_000  # пауза после запуска перед первой проверкой расписания


class Controller(QObject):
    settings_changed = Signal()
    scan_started = Signal()
    scan_updated = Signal(object)  # Plan | None
    busy_changed = Signal(bool)
    journal_changed = Signal()
    archive_changed = Signal()

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.data_dir = paths.app_data_dir()
        self.settings_path = self.data_dir / "settings.json"
        self.settings = Settings.load(self.settings_path)
        phrases.configure(self.settings.humor, self.settings.address)
        self.journal = Journal(self.data_dir / "journal.jsonl")
        self._busy = False
        self._workers: list = []
        self._last_scan: tuple[datetime, Plan, Locations] | None = None
        self._preview: PreviewDialog | None = None
        self._pick = None

        self.overlay = ZoneOverlay()
        self.window = MainWindow(self)
        self.countdown = CountdownPopup()
        self.countdown.go.connect(self._auto_run)
        self.countdown.postpone.connect(self._postpone)
        self._build_tray()

        self._sync_autostart()
        self._refresh_overlay()

        # Раз в минуту: не пора ли убирать; раз в час — сроки архива
        self.tick = QTimer(self)
        self.tick.setInterval(60_000)
        self.tick.timeout.connect(self._check_schedule)
        self.daily = QTimer(self)
        self.daily.setInterval(3_600_000)
        self.daily.timeout.connect(self._check_archive)
        self.daily.start()
        QTimer.singleShot(5_000, self._check_archive)
        # Пропущенную автоуборку (комп был выключен в 21:00) догоняем не сразу
        # после включения, а через 5 минут — дать человеку спокойно сесть за работу
        QTimer.singleShot(START_DELAY_MS, self._start_schedule)
        # Положение экранов поменялось — перерисовать рамку
        app.screenAdded.connect(lambda *_: self._refresh_overlay())
        app.screenRemoved.connect(lambda *_: self._refresh_overlay())

    # ------------------------------------------------------------ общее
    def save(self) -> None:
        self.settings.save(self.settings_path)
        self.settings_changed.emit()

    def protected_paths(self) -> list[Path]:
        return paths.protected_roots()

    def archive_root(self) -> Path:
        return paths.desktop_dir() / self.settings.archive_name

    def source_dir(self, src: str) -> Path:
        return paths.desktop_dir() if src == "desktop" else paths.downloads_dir()

    def open_archive(self) -> None:
        root = self.archive_root()
        root.mkdir(exist_ok=True)
        os.startfile(root)

    def show_window(self, page: int | None = None) -> None:
        if page is not None:
            self.window.go(page)
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()
        if not self._last_scan or (datetime.now() - self._last_scan[0]).seconds > 300:
            self.rescan()

    def on_window_hidden(self) -> None:
        if not self.settings.first_run_done:
            return
        if not getattr(self, "_told_tray", False):
            self._told_tray = True
            self.notify(phrases.pick("tray_title"), phrases.pick("tray_text"))

    def notify(self, title: str, text: str) -> None:
        self.tray.showMessage(title, text, icons.app_icon(), 8000)

    def _set_busy(self, b: bool) -> None:
        self._busy = b
        self.busy_changed.emit(b)
        self.act_clean.setEnabled(not b)

    # ------------------------------------------------------------ трей
    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(icons.app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        m = QMenu()
        tone.bind(m.addAction("", lambda: self.show_window()), "tray_open")
        self.act_clean = tone.bind(m.addAction("", self.start_cleanup), "tray_clean")
        tone.bind(m.addAction("", self.open_archive), "tray_archive")
        m.addSeparator()
        self.act_zone = tone.bind(QAction("", m, checkable=True), "tray_zone_show")
        self.act_zone.setChecked(self.settings.zone_visible)
        self.act_zone.toggled.connect(self.set_zone_visible)
        m.addAction(self.act_zone)
        tone.bind(m.addAction("", self.pick_zone), "tray_zone_draw")
        m.addSeparator()
        tone.bind(m.addAction("", self.quit), "tray_quit")
        self.tray.setContextMenu(m)
        self._tray_menu = m
        self.tray.activated.connect(
            lambda r: self.show_window() if r in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None
        )
        self.tray.messageClicked.connect(lambda: self.show_window())
        self.tray.show()

    def quit(self) -> None:
        self.overlay.hide()
        self.tray.hide()
        self.app.quit()

    # ------------------------------------------------------------ зона
    def _refresh_overlay(self) -> None:
        self.overlay.set_zone(self.settings.desktop_zone, self.settings.zone_visible)

    def set_zone_visible(self, on: bool) -> None:
        self.settings.zone_visible = on
        self.act_zone.blockSignals(True)
        self.act_zone.setChecked(on)
        self.act_zone.blockSignals(False)
        self.save()
        self._refresh_overlay()

    def set_zone(self, zone: list[int] | None) -> None:
        self.settings.desktop_zone = zone
        self.save()
        self._refresh_overlay()
        self.rescan()

    def pick_zone(self) -> None:
        if self._pick:
            return
        was_visible = self.window.isVisible()
        self.window.hide()
        self.overlay.hide()

        def done(zone):
            self._pick = None
            if zone:
                self.settings.zone_visible = True
                self.set_zone(zone)
                self.notify(phrases.pick("zone_title"), phrases.pick("zone_text"))
            else:
                self._refresh_overlay()
            if was_visible:
                self.show_window(1)

        # Даём окну спрятаться, чтобы рисовать прямо по рабочему столу
        QTimer.singleShot(250, lambda: setattr(self, "_pick", ZonePickSession(self.settings.desktop_zone, done)))

    # ------------------------------------------------------------ исключения
    def add_exclusion(self, src: str, name: str) -> None:
        lst = self.settings.desktop_exclusions if src == "desktop" else self.settings.downloads_exclusions
        if name.lower() not in (x.lower() for x in lst):
            lst.append(name)
            self.save()

    def add_exclusion_paths(self, raw_paths: list[str]) -> tuple[list[str], list[str]]:
        """Добавить файлы/папки (перетаскивание, окно выбора). → (добавлено, пропущено)."""
        routed, skipped = route_exclusions(raw_paths, paths.desktop_dir(), paths.downloads_dir())
        added = []
        for src, name in routed:
            lst = self.settings.desktop_exclusions if src == "desktop" else self.settings.downloads_exclusions
            if name.lower() not in (x.lower() for x in lst):
                lst.append(name)
                added.append(name)
        if added:
            self.save()
        return added, skipped

    def remove_exclusions(self, src: str, names: list[str]) -> None:
        key = "desktop_exclusions" if src == "desktop" else "downloads_exclusions"
        setattr(self.settings, key, [x for x in getattr(self.settings, key) if x not in names])
        self.save()

    def set_humor(self, on: bool) -> None:
        self.settings.humor = on
        self.save()
        phrases.configure(on, self.settings.address)
        tone.retone()
        self.overlay.update()
        self.settings_changed.emit()

    def set_address(self, address: str) -> None:
        self.settings.address = address or ""
        self.save()
        phrases.configure(self.settings.humor, self.settings.address)

    def set_autostart(self, on: bool) -> None:
        self.settings.autostart = on
        self.save()
        self._sync_autostart()

    def _sync_autostart(self) -> None:
        # Из исходников автозапуск не прописываем — только у собранного exe
        if not getattr(sys, "frozen", False):
            return
        try:
            autostart.set_enabled(self.settings.autostart)
        except OSError:
            pass

    # ------------------------------------------------------------ подсчёт
    def rescan(self) -> None:
        if self._busy:
            return
        self.scan_started.emit()
        w = PlanWorker(self.settings)
        w.done.connect(self._scan_done)
        w.failed.connect(lambda _e: self.scan_updated.emit(None))
        self._run_worker(w)

    def _scan_done(self, plan: Plan, loc: Locations) -> None:
        self._last_scan = (datetime.now(), plan, loc)
        self.scan_updated.emit(plan)

    def _run_worker(self, w) -> None:
        self._workers.append(w)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        w.start()

    # ------------------------------------------------------------ ручная уборка
    def start_cleanup(self) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self.show_window()
        self.scan_started.emit()
        w = PlanWorker(self.settings)
        w.done.connect(self._open_preview)
        w.failed.connect(self._plan_failed)
        self._run_worker(w)

    def _plan_failed(self, err: str) -> None:
        self._set_busy(False)
        self.scan_updated.emit(None)
        QMessageBox.warning(self.window, APP_NAME, phrases.pick("plan_failed") + f"\n{err}")

    def _open_preview(self, plan: Plan, loc: Locations) -> None:
        self._scan_done(plan, loc)
        dlg = PreviewDialog(plan, loc, self.window)
        dlg.setStyleSheet(theme.QSS)
        dlg.exclude_requested.connect(self.add_exclusion)
        dlg.run_requested.connect(lambda p: self._execute(p, loc, "manual", dlg))
        dlg.finished.connect(self._preview_closed)
        self._preview = dlg
        dlg.open()

    def _preview_closed(self, *_):
        if self._preview and self._preview.stack.currentIndex() == 1:
            return  # уборка ещё идёт
        self._preview = None
        if self._busy:
            self._set_busy(False)
        self.rescan()

    def _execute(self, plan: Plan, loc: Locations, trigger: str, dlg: PreviewDialog | None) -> None:
        w = ExecWorker(plan, loc, trigger)
        if dlg:
            w.progress.connect(dlg.on_progress)
        w.done.connect(lambda rep: self._finished(rep, dlg))
        self._run_worker(w)

    def _finished(self, report: RunReport, dlg: PreviewDialog | None) -> None:
        self.journal.append(report)
        self.settings.last_run = datetime.now().isoformat(timespec="seconds")
        self.settings.postponed_until = None
        self.settings.first_run_done = True
        self.save()
        self.journal_changed.emit()
        self.archive_changed.emit()
        self._set_busy(False)
        if dlg:
            dlg.show_result(report)
        else:
            summary = report.summary() if (report.moved or report.freed or report.skipped) else phrases.pick("nothing")
            self.notify(phrases.pick("done_title"), phrases.pick("done_text", summary=summary))
        if not dlg:
            self.rescan()

    # ------------------------------------------------------------ автоуборка
    def _start_schedule(self) -> None:
        self._check_schedule()
        self.tick.start()

    def _check_schedule(self) -> None:
        if self._busy or self.countdown.isVisible():
            return
        if schedule.is_due(self.settings, datetime.now()):
            self.countdown.start()

    def _postpone(self, hours: int) -> None:
        until = datetime.now() + timedelta(hours=hours)
        self.settings.postponed_until = until.isoformat(timespec="seconds")
        self.save()
        when = f"{human_date(until.date())} в {until:%H:%M}"
        self.notify(phrases.pick("postponed_title"), phrases.pick("postponed_text", when=when))

    def _auto_run(self) -> None:
        if self._busy:
            return
        self._set_busy(True)
        w = PlanWorker(self.settings, auto=True)
        w.done.connect(lambda plan, loc: self._execute(plan, loc, "auto", None))
        w.failed.connect(self._plan_failed)
        self._run_worker(w)

    # ------------------------------------------------------------ сроки архива
    def _check_archive(self) -> None:
        s = self.settings
        today = date.today()
        loc = Locations(
            desktop=paths.desktop_dir(),
            downloads=paths.downloads_dir(),
            temp=paths.temp_dir(),
            recycle_dirs=[],
            protected=paths.protected_roots(),
        )
        soon = schedule.expiring_soon(s, loc, today)
        if soon:
            f = soon[0]
            left = f.days_left(today)
            more = f" и ещё {len(soon) - 1}" if len(soon) > 1 else ""
            left_txt = f"{left} {plural(left, 'день', 'дня', 'дней')}"
            self.notify(
                phrases.pick("expiring_title", left=left_txt),
                phrases.pick("expiring_text", date=human_date(f.day), more=more, left=left_txt),
            )
            s.warned_archives = sorted(set(s.warned_archives) | {x.path.name for x in soon})
            self.save()
        if not s.first_run_done or self._busy:
            return
        acts = purge_actions(s, loc, today)
        if not acts:
            return
        plan = Plan(created=datetime.now(), archive_root=loc.archive_root(s), day_dir=loc.archive_root(s), actions=acts)
        report = execute(plan, loc, "purge")
        self.journal.append(report)
        live = {f.name for f in loc.archive_root(s).iterdir()} if loc.archive_root(s).exists() else set()
        s.warned_archives = [n for n in s.warned_archives if n in live]
        self.save()
        self.journal_changed.emit()
        self.archive_changed.emit()
        self.notify(phrases.pick("purged_title"), phrases.pick("purged_text", size=human_size(report.freed)))

    def delete_archive_folder(self, path: Path) -> None:
        if QMessageBox.question(
            self.window, APP_NAME, f"Удалить насовсем «{path.name}» из архива?"
        ) != QMessageBox.Yes:
            return
        guard = Guard([paths.desktop_dir()], paths.protected_roots())
        res = delete_path(path, guard)
        self.archive_changed.emit()
        self.notify(phrases.pick("deleted_title"), phrases.pick("deleted_text", size=human_size(res.freed)))


def run(start_hidden: bool = False) -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    # Второй запуск — просто показать окно первого
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.waitForBytesWritten(300)
        return 0

    app.setStyle("Fusion")
    app.setStyleSheet(theme.QSS)
    app.setFont(theme.font(10))
    app.setWindowIcon(icons.app_icon())

    ctl = Controller(app)
    server = QLocalServer()
    QLocalServer.removeServer(SERVER_NAME)
    server.listen(SERVER_NAME)

    def on_conn():
        c = server.nextPendingConnection()
        c.readyRead.connect(lambda: ctl.show_window())

    server.newConnection.connect(on_conn)

    if not start_hidden or not ctl.settings.first_run_done:
        ctl.show_window()
    return app.exec()
