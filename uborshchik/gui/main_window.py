"""Главное окно: боковое меню и страницы."""

from __future__ import annotations

import os
from datetime import date, datetime

from PySide6.QtCore import QSize, Qt, QTime, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__, phrases, schedule
from ..fsops import tree_size
from ..planner import (
    CAT_CAD,
    CAT_DESKTOP,
    CAT_DOWNLOADS,
    CAT_PURGE,
    CAT_RECYCLE,
    CAT_TEMP,
    archive_folders,
)
from ..util import human_date, human_size, plural
from . import icons, theme, tone
from .widgets import Banner, StatCard, Switch, card, label


def page_scaffold(
    title: str, subtitle: str = "", key: str | None = None
) -> tuple[QWidget, QVBoxLayout]:
    """Страница с прокруткой, заголовком и колонкой контента."""
    outer = QWidget()
    outer.setObjectName("Page")
    ol = QVBoxLayout(outer)
    ol.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    inner = QWidget()
    inner.setObjectName("Page")
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(36, 30, 36, 30)
    lay.setSpacing(14)
    h1 = label(title, "H1")
    if key:
        tone.bind(h1, key)
    lay.addWidget(h1)
    if subtitle:
        lay.addWidget(label(subtitle, "Muted", wrap=True))
    lay.addSpacing(4)
    scroll.setWidget(inner)
    ol.addWidget(scroll)
    return outer, lay


# ---------------------------------------------------------------- Главная
class HomePage(QWidget):
    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        page, lay = page_scaffold(phrases.pick("greeting"))
        self.h1 = lay.itemAt(0).widget()
        QVBoxLayout(self).addWidget(page)
        self.layout().setContentsMargins(0, 0, 0, 0)

        hero = QFrame()
        hero.setObjectName("Hero")
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(28, 24, 28, 24)
        col = QVBoxLayout()
        self.hero_title = label("Рабочий стол ждёт уборки")
        self.hero_title.setStyleSheet("font-size: 16pt; font-weight: 600;")
        self.hero_sub = label("", wrap=True)
        self.hero_sub.setStyleSheet("color: rgba(255,255,255,0.86);")
        self.next_run = label("")
        self.next_run.setStyleSheet("color: rgba(255,255,255,0.86); font-size: 9.5pt;")
        col.addWidget(self.hero_title)
        col.addWidget(self.hero_sub)
        col.addSpacing(6)
        col.addWidget(self.next_run)
        hl.addLayout(col, 1)
        self.go = tone.bind(QPushButton(), "clean_now")
        self.go.setObjectName("HeroButton")
        self.go.setCursor(Qt.PointingHandCursor)
        self.go.clicked.connect(ctl.start_cleanup)
        hl.addWidget(self.go, 0, Qt.AlignVCenter)
        lay.addWidget(hero)

        head = QHBoxLayout()
        head.addWidget(label("Что накопилось", "H2"))
        head.addStretch()
        self.scan_state = label("", "Faint")
        head.addWidget(self.scan_state)
        refresh = QPushButton(icons.line_icon("refresh", theme.ACCENT), "")
        refresh.setObjectName("Link")
        refresh.setToolTip("Пересчитать")
        refresh.clicked.connect(ctl.rescan)
        head.addWidget(refresh)
        lay.addLayout(head)

        grid = QGridLayout()
        grid.setSpacing(12)
        self.c_desk = StatCard("Рабочий стол", "#1F8A65")
        self.c_down = StatCard("Загрузки", "#2E6F8E")
        self.c_temp = StatCard("Временные файлы", "#B7791F")
        self.c_cad = StatCard("Мусор AutoCAD/Revit", "#8E5AB5")
        self.c_bin = StatCard("Корзина", "#C4402F")
        self.c_arch = StatCard("Архив", "#6F6E73")
        for i, c in enumerate(
            [self.c_desk, self.c_down, self.c_temp, self.c_cad, self.c_bin, self.c_arch]
        ):
            grid.addWidget(c, i // 3, i % 3)
        lay.addLayout(grid)

        self.banner = Banner("")
        self.banner.setVisible(False)
        lay.addWidget(self.banner)

        self.last = label("", "Faint", wrap=True)
        lay.addWidget(self.last)
        lay.addStretch()

        ctl.scan_started.connect(self._scan_started)
        ctl.scan_updated.connect(self._scan_done)
        ctl.settings_changed.connect(self.refresh_texts)
        ctl.busy_changed.connect(lambda b: self.go.setEnabled(not b))
        self.refresh_texts()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self.h1.setText(phrases.pick("greeting"))

    def refresh_texts(self) -> None:
        s = self.ctl.settings
        nxt = schedule.next_run(s, datetime.now())
        if not s.first_run_done:
            self.next_run.setText(phrases.pick("first_run"))
        elif nxt is None:
            self.next_run.setText("Автоуборка выключена — убираю только по кнопке.")
        else:
            when = "сегодня" if nxt.date() == date.today() else human_date(nxt.date())
            self.next_run.setText(f"Следующая автоуборка — {when} в {nxt:%H:%M}")
        rows = self.ctl.journal.read(1)
        if rows:
            r = rows[0]
            dt = datetime.fromisoformat(r["started"])
            from ..executor import RunReport

            rep = RunReport(**{k: v for k, v in r.items() if k in RunReport.__dataclass_fields__})
            self.last.setText(
                f"Последняя уборка: {human_date(dt.date())} в {dt:%H:%M} — {rep.summary()}"
            )

    def _scan_started(self) -> None:
        self.scan_state.setText("считаю…")
        for c in (self.c_desk, self.c_down, self.c_temp, self.c_cad, self.c_bin, self.c_arch):
            c.sub.setText("считаю…")

    def _scan_done(self, plan) -> None:
        if plan is None:
            self.scan_state.setText("не удалось посчитать")
            return
        self.scan_state.setText(f"обновлено в {datetime.now():%H:%M}")
        by = plan.by_category()

        def stat(cat):
            acts = by.get(cat, [])
            return len(acts), sum(a.size for a in acts), sum(a.files for a in acts)

        s = self.ctl.settings
        n, size, _ = stat(CAT_DESKTOP)
        self.c_desk.set(
            f"{n}",
            (f"{plural(n, 'объект', 'объекта', 'объектов')} · {human_size(size)}" if n else "чисто")
            + (f" · в зоне {len(plan.zone_kept)}" if plan.zone_kept else ""),
        )
        if not s.desktop_enabled:
            self.c_desk.set("—", "выключено")
        n, size, _ = stat(CAT_DOWNLOADS)
        self.c_down.set(f"{n}", f"файлов · {human_size(size)}" if n else "чисто")
        if not s.downloads_enabled:
            self.c_down.set("—", "выключено")
        n, size, files = stat(CAT_TEMP)
        self.c_temp.set(human_size(size), f"старше {s.temp_age_days} дн." if n else "чисто")
        if not s.temp_enabled:
            self.c_temp.set("—", "выключено")
        n, size, _ = stat(CAT_CAD)
        self.c_cad.set(f"{n}", f"файлов · {human_size(size)}" if n else "чисто")
        if not s.cad_enabled:
            self.c_cad.set("—", "выключено")
        n, size, _ = stat(CAT_RECYCLE)
        self.c_bin.set(human_size(size), f"лежит дольше {s.recycle_age_days} дн." if n else "чисто")
        if not s.recycle_enabled:
            self.c_bin.set("—", "выключено")

        folders = archive_folders(plan.archive_root, s.archive_keep_days)
        purge = len(by.get(CAT_PURGE, []))
        self.c_arch.set(
            f"{len(folders)}",
            f"{plural(len(folders), 'уборка', 'уборки', 'уборок')} хранится"
            + (f" · {purge} к удалению" if purge else ""),
        )

        freed = sum(a.size for a in plan.actions if a.kind != "move")
        if freed >= 1024**3:
            self.hero_title.setText(phrases.pick("hero_free", size=human_size(freed)))
        elif plan.actions:
            self.hero_title.setText(phrases.pick("hero_some"))
        else:
            self.hero_title.setText(phrases.pick("hero_clean"))
        moved = len(by.get(CAT_DESKTOP, [])) + len(by.get(CAT_DOWNLOADS, []))
        if moved:
            sub = phrases.pick(
                "hero_sub",
                moved=f"{moved} {plural(moved, 'объект', 'объекта', 'объектов')}",
                days=s.archive_keep_days,
            )
        elif plan.actions:
            sub = phrases.pick("hero_sub_trash")
        else:
            sub = ""
        self.hero_sub.setText(sub)
        self.hero_sub.setVisible(bool(sub))
        self.banner.setVisible(bool(plan.warnings))
        self.banner.set_text("⚠  " + "\n⚠  ".join(plan.warnings) if plan.warnings else "")


# ---------------------------------------------------------- Что не трогать
class ExclusionList(QListWidget):
    """Список исключений, принимающий файлы и папки перетаскиванием."""

    dropped = Signal(list)  # пути
    delete_pressed = Signal()

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setIconSize(QSize(18, 18))
        self._hover = False

    @staticmethod
    def _local_paths(e) -> list[str]:
        md = e.mimeData()
        if not md.hasUrls():
            return []
        return [u.toLocalFile() for u in md.urls() if u.isLocalFile() and u.toLocalFile()]

    def _set_hover(self, on: bool) -> None:
        self._hover = on
        self.setStyleSheet(
            f"QListWidget {{ border: 2px dashed {theme.ACCENT}; background: {theme.ACCENT_SOFT}; }}"
            if on
            else ""
        )
        self.viewport().update()

    def dragEnterEvent(self, e) -> None:
        if self._local_paths(e):
            e.setDropAction(Qt.CopyAction)
            e.accept()
            self._set_hover(True)
        else:
            e.ignore()

    def dragMoveEvent(self, e) -> None:
        if self._local_paths(e):
            e.setDropAction(Qt.CopyAction)
            e.accept()
        else:
            e.ignore()

    def dragLeaveEvent(self, e) -> None:
        self._set_hover(False)
        super().dragLeaveEvent(e)

    def dropEvent(self, e) -> None:
        paths = self._local_paths(e)
        self._set_hover(False)
        if paths:
            # CopyAction: Проводник ничего не переносит, мы только запоминаем имена
            e.setDropAction(Qt.CopyAction)
            e.accept()
            self.dropped.emit(paths)

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key_Delete:
            self.delete_pressed.emit()
        else:
            super().keyPressEvent(e)

    def paintEvent(self, e) -> None:
        super().paintEvent(e)
        if self.count() == 0 or self._hover:
            p = QPainter(self.viewport())
            p.setPen(QColor(theme.ACCENT if self._hover else theme.FAINT))
            p.setFont(theme.font(9.5))
            text = "Отпустите — добавлю в исключения" if self._hover else "Перетащите сюда файлы и папки"
            r = self.viewport().rect()
            if self._hover and self.count():
                r = r.adjusted(0, r.height() - 36, 0, 0)
            p.drawText(r, Qt.AlignCenter, text)
            p.end()


class ProtectPage(QWidget):
    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        page, lay = page_scaffold(
            "Что не трогать",
            "Зона покоя на рабочем столе, исключения и места, куда Уборщик не заходит никогда.",
            key="nav_protect",
        )
        QVBoxLayout(self).addWidget(page)
        self.layout().setContentsMargins(0, 0, 0, 0)

        # Зона
        zc = card()
        zl = QVBoxLayout(zc)
        zl.setContentsMargins(22, 18, 22, 18)
        zl.setSpacing(8)
        zl.addWidget(label("Зона покоя", "H2"))
        zl.addWidget(
            label(
                "Область рабочего стола: всё, что в неё положено, остаётся на месте. "
                "На столе она видна как пунктирная зелёная рамка — клики проходят сквозь неё.",
                "Muted",
                wrap=True,
            )
        )
        self.zone_state = label("")
        zl.addWidget(self.zone_state)
        zr = QHBoxLayout()
        self.draw_btn = tone.bind(QPushButton(icons.line_icon("draw", "white"), ""), "zone_draw", "  ")
        self.draw_btn.setObjectName("Primary")
        self.draw_btn.clicked.connect(ctl.pick_zone)
        self.clear_btn = tone.bind(QPushButton(), "zone_clear")
        self.clear_btn.setObjectName("Danger")
        self.clear_btn.clicked.connect(self._clear_zone)
        zr.addWidget(self.draw_btn)
        zr.addWidget(self.clear_btn)
        zr.addStretch()
        zr.addWidget(label("Показывать рамку", "Muted"))
        self.zone_vis = Switch(ctl.settings.zone_visible)
        self.zone_vis.toggled.connect(ctl.set_zone_visible)
        zr.addWidget(self.zone_vis)
        zl.addLayout(zr)
        lay.addWidget(zc)

        # Исключения
        self._build_exclusions(lay)

        # Защищённые места
        pc = card()
        pl = QVBoxLayout(pc)
        pl.setContentsMargins(22, 18, 22, 18)
        pl.addWidget(label("Не трогаю никогда", "H2"))
        pl.addWidget(
            label(
                "Облака (в том числе найденные автоматически), документы, настройки программ "
                "и системные папки. Папки на столе, внутри которых лежит облако, тоже пропускаются.",
                "Muted",
                wrap=True,
            )
        )
        self.protected = label("", "Faint", wrap=True)
        self.protected.setTextInteractionFlags(Qt.TextSelectableByMouse)
        pl.addWidget(self.protected)
        lay.addWidget(pc)
        lay.addStretch()

        ctl.settings_changed.connect(self.refresh)
        self.refresh()

    def _build_exclusions(self, parent_lay) -> None:
        c = card()
        cl = QVBoxLayout(c)
        cl.setContentsMargins(22, 18, 22, 18)
        cl.setSpacing(8)
        head = QHBoxLayout()
        head.addWidget(label("Исключения", "H2"))
        head.addStretch()
        self.seg = QButtonGroup(self)
        for i, title in enumerate(("Рабочий стол", "Загрузки")):
            b = QPushButton(title)
            b.setObjectName("SegLeft" if i == 0 else "SegRight")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.seg.addButton(b, i)
            head.addWidget(b)
        head.setSpacing(0)
        cl.addLayout(head)
        cl.addWidget(
            label(
                "Перетащите сюда файлы и папки с рабочего стола или из Загрузок — "
                "я сам разложу по спискам. Del — удалить выбранное.",
                "Faint",
                wrap=True,
            )
        )
        self.excl_stack = QStackedWidget()
        self.desk_list = self._make_list("desktop")
        self.down_list = self._make_list("downloads")
        self.excl_stack.addWidget(self.desk_list)
        self.excl_stack.addWidget(self.down_list)
        self.seg.idClicked.connect(self.excl_stack.setCurrentIndex)
        self.seg.button(0).setChecked(True)
        cl.addWidget(self.excl_stack)

        r = QHBoxLayout()
        r.setSpacing(8)
        f = tone.bind(QPushButton(icons.line_icon("file", theme.TEXT), ""), "excl_files", " ")
        f.clicked.connect(lambda: self._add_files(self._src()))
        d = tone.bind(QPushButton(icons.line_icon("folder", theme.TEXT), ""), "excl_folder", " ")
        d.clicked.connect(lambda: self._add_folder(self._src()))
        mask = tone.bind(QPushButton(icons.line_icon("mask", theme.TEXT), ""), "excl_mask", " ")
        mask.setToolTip("Маска: * — любые символы, ? — один. Например *.lnk или Паспорт*")
        mask.clicked.connect(lambda: self._add_mask(self._src()))
        rm = tone.bind(QPushButton(), "excl_remove")
        rm.setObjectName("Danger")
        rm.clicked.connect(lambda: self._remove(self._src(), self.excl_stack.currentWidget()))
        for b in (f, d, mask):
            r.addWidget(b)
        r.addStretch()
        r.addWidget(rm)
        cl.addLayout(r)
        parent_lay.addWidget(c)

    def _make_list(self, src: str) -> "ExclusionList":
        lst = ExclusionList()
        lst.setMinimumHeight(200)
        lst.setSelectionMode(QAbstractItemView.ExtendedSelection)
        lst.dropped.connect(self._add_paths)
        lst.delete_pressed.connect(lambda: self._remove(src, lst))
        return lst

    def _src(self) -> str:
        return "desktop" if self.excl_stack.currentIndex() == 0 else "downloads"

    def refresh(self) -> None:
        s = self.ctl.settings
        if s.desktop_zone:
            l, t, r, b = s.desktop_zone
            self.zone_state.setText(
                f"<span style='color:{theme.ACCENT}'>●</span> Зона задана: {r - l}×{b - t} px "
                f"(от {l},{t} до {r},{b})"
            )
        else:
            self.zone_state.setText(
                f"<span style='color:{theme.FAINT}'>●</span> Зона не задана — нажмите «Нарисовать зону»."
            )
        self.clear_btn.setEnabled(bool(s.desktop_zone))
        self.zone_vis.blockSignals(True)
        self.zone_vis.setChecked(s.zone_visible)
        self.zone_vis.blockSignals(False)
        for lst, items, src in (
            (self.desk_list, s.desktop_exclusions, "desktop"),
            (self.down_list, s.downloads_exclusions, "downloads"),
        ):
            base = self.ctl.source_dir(src)
            lst.clear()
            for x in items:
                it = QListWidgetItem(x, lst)
                p = base / x
                if p.is_dir():
                    it.setIcon(icons.line_icon("folder", theme.ACCENT))
                    it.setToolTip(f"Папка: {p}")
                elif p.is_file():
                    it.setIcon(icons.line_icon("file", theme.ACCENT))
                    it.setToolTip(f"Файл: {p}")
                elif any(ch in x for ch in "*?"):
                    it.setIcon(icons.line_icon("mask", theme.MUTED))
                    it.setToolTip("Маска: подходит ко всем подходящим именам")
                else:
                    it.setIcon(icons.line_icon("file", theme.FAINT))
                    it.setForeground(Qt.gray)
                    it.setToolTip("Сейчас такого нет — правило сработает, когда появится")
        self.protected.setText("\n".join(str(p) for p in self.ctl.protected_paths()))

    def _clear_zone(self) -> None:
        if QMessageBox.question(self, APP_NAME, "Убрать зону покоя? Значки в ней начнут убираться.") == QMessageBox.Yes:
            self.ctl.set_zone(None)

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self.refresh()  # файлы могли появиться/исчезнуть — обновить значки

    def _add_files(self, src: str) -> None:
        base = self.ctl.source_dir(src)
        files, _ = QFileDialog.getOpenFileNames(self, "Файлы, которые не трогать", str(base))
        if files:
            self._add_paths(files)

    def _add_folder(self, src: str) -> None:
        base = self.ctl.source_dir(src)
        path = QFileDialog.getExistingDirectory(self, "Папка, которую не трогать", str(base))
        if path:
            self._add_paths([path])

    def _add_paths(self, paths: list[str]) -> None:
        added, skipped = self.ctl.add_exclusion_paths(paths)
        if skipped:
            QMessageBox.information(
                self,
                APP_NAME,
                "Исключения работают для того, что лежит прямо на рабочем столе или "
                "в Загрузках. Это я пропустил:\n\n" + "\n".join(skipped[:10])
                + (f"\n… и ещё {len(skipped) - 10}" if len(skipped) > 10 else ""),
            )
        # Подсветить только что добавленное и показать нужный список
        for idx, lst in enumerate((self.desk_list, self.down_list)):
            lst.clearSelection()
            for i in range(lst.count()):
                it = lst.item(i)
                if it.text() in added:
                    it.setSelected(True)
                    lst.scrollToItem(it)
                    self.seg.button(idx).setChecked(True)
                    self.excl_stack.setCurrentIndex(idx)

    def _add_mask(self, src: str) -> None:
        text, ok = QInputDialog.getText(
            self, "Новое исключение", "Имя или маска (например, *.lnk, Паспорт*, Модели):"
        )
        if ok and text.strip():
            self.ctl.add_exclusion(src, text.strip())

    def _remove(self, src: str, lst: QListWidget) -> None:
        names = [i.text() for i in lst.selectedItems()]
        if names:
            self.ctl.remove_exclusions(src, names)


# ---------------------------------------------------------------- Архив
class ArchivePage(QWidget):
    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        page, lay = page_scaffold("Архив", key="nav_archive")
        QVBoxLayout(self).addWidget(page)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.info = label("", "Muted", wrap=True)
        lay.addWidget(self.info)
        top = QHBoxLayout()
        op = tone.bind(QPushButton(icons.line_icon("folder", theme.TEXT), ""), "archive_open_root", " ")
        op.clicked.connect(lambda: ctl.open_archive())
        top.addWidget(op)
        top.addStretch()
        lay.addLayout(top)
        self.list_box = QVBoxLayout()
        self.list_box.setSpacing(10)
        lay.addLayout(self.list_box)
        lay.addStretch()
        ctl.settings_changed.connect(self.refresh)
        ctl.archive_changed.connect(self.refresh)

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self.refresh()

    def refresh(self) -> None:
        while self.list_box.count():
            w = self.list_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        s = self.ctl.settings
        root = self.ctl.archive_root()
        self.info.setText(
            f"Всё, что убрано с рабочего стола и из Загрузок, лежит в <b>{root}</b> по датам. "
            f"Каждая уборка хранится {s.archive_keep_days} дней, за {s.archive_warn_days} дн. до "
            "удаления я предупрежу."
        )
        folders = archive_folders(root, s.archive_keep_days)
        if not folders:
            empty = label("Архив пока пуст.", "Muted")
            self.list_box.addWidget(empty)
            return
        today = date.today()
        for f in folders:
            self.list_box.addWidget(self._row(f, today))

    def _row(self, f, today) -> QWidget:
        s = self.ctl.settings
        c = card()
        h = QHBoxLayout(c)
        h.setContentsMargins(18, 12, 14, 12)
        h.setSpacing(14)
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(label(f"Уборка {human_date(f.day)} {f.day.year}", "H2"))
        size, files = tree_size(f.path)
        left = f.days_left(today)
        bar = QProgressBar()
        bar.setFixedHeight(6)
        bar.setMaximum(s.archive_keep_days)
        bar.setValue(max(0, s.archive_keep_days - max(left, 0)))
        if left <= s.archive_warn_days:
            bar.setStyleSheet(f"QProgressBar::chunk {{ background: {theme.DANGER}; border-radius: 3px; }}")
        col.addWidget(bar)
        when = "удалится при следующей проверке" if left <= 0 else f"удалится через {left} {plural(left, 'день', 'дня', 'дней')} ({human_date(f.expires)})"
        col.addWidget(label(f"{files} {plural(files, 'файл', 'файла', 'файлов')} · {human_size(size)} · {when}", "Faint"))
        h.addLayout(col, 1)
        op = QPushButton(phrases.btn("archive_open"))
        op.clicked.connect(lambda: os.startfile(f.path))
        rm = QPushButton(phrases.btn("archive_delete"))
        rm.setObjectName("Danger")
        rm.clicked.connect(lambda: self.ctl.delete_archive_folder(f.path))
        h.addWidget(op)
        h.addWidget(rm)
        return c


# ---------------------------------------------------------------- Журнал
class JournalPage(QWidget):
    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        page, lay = page_scaffold("Журнал", "Каждая уборка: когда, как запущена и что сделано.", key="nav_journal")
        QVBoxLayout(self).addWidget(page)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Когда", "Запуск", "Итог"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(420)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.cellDoubleClicked.connect(self._details)
        lay.addWidget(self.table)
        lay.addWidget(label("Двойной щелчок — подробности.", "Faint"))
        ctl.journal_changed.connect(self.refresh)
        self._rows: list[dict] = []

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self.refresh()

    def refresh(self) -> None:
        from ..executor import RunReport

        self._rows = self.ctl.journal.read()
        self.table.setRowCount(len(self._rows))
        for i, r in enumerate(self._rows):
            dt = datetime.fromisoformat(r["started"])
            rep = RunReport(**{k: v for k, v in r.items() if k in RunReport.__dataclass_fields__})
            trig = {"auto": "автоматически", "manual": "вручную", "purge": "срок архива"}.get(
                r.get("trigger"), r.get("trigger", "")
            )
            for j, text in enumerate([f"{dt:%d.%m.%Y %H:%M}", trig, rep.summary()]):
                self.table.setItem(i, j, QTableWidgetItem(text))
        if not self._rows:
            self.table.setRowCount(1)
            self.table.setItem(0, 2, QTableWidgetItem("Пока ни одной уборки."))

    def _details(self, row: int, _col: int) -> None:
        if row >= len(self._rows):
            return
        r = self._rows[row]
        dlg = QDialog(self)
        dlg.setWindowTitle("Подробности уборки")
        dlg.resize(820, 520)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(20, 18, 20, 18)
        t = QTableWidget(len(r.get("details", [])), 4)
        t.setHorizontalHeaderLabels(["Раздел", "Путь", "Размер", "Результат"])
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.setShowGrid(False)
        hh = t.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        names = {"moved": "в архиве", "deleted": "удалено", "partial": "частично", "skipped": "пропущено", "blocked": "защищено"}
        for i, d in enumerate(r.get("details", [])):
            info = d.get("info", "")
            res = names.get(d["status"], d["status"]) + (f" — {info}" if d["status"] != "deleted" and info else "")
            for j, text in enumerate([d["category"], d["path"], human_size(d.get("size", 0)), res]):
                it = QTableWidgetItem(text)
                it.setToolTip(text)
                t.setItem(i, j, it)
        v.addWidget(t)
        dlg.exec()


# ---------------------------------------------------------------- Настройки
def _spin(lo: int, hi: int, suffix: str, value: int) -> QSpinBox:
    sp = QSpinBox()
    sp.setRange(lo, hi)
    sp.setSuffix(suffix)
    sp.setValue(value)
    sp.setFixedWidth(96)
    sp.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return sp


class SettingsPage(QWidget):
    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        page, lay = page_scaffold("Настройки", "Изменения сохраняются сразу.", key="nav_settings")
        QVBoxLayout(self).addWidget(page)
        self.layout().setContentsMargins(0, 0, 0, 0)
        s = ctl.settings

        # Где убирать
        c1, l1 = self._section(lay, "Где убирать")
        self._toggle(l1, "Рабочий стол", "Всё, кроме зоны покоя и исключений → в архив", "desktop_enabled")
        self._toggle(l1, "Загрузки", "Всё, кроме исключений → в архив, в подпапку «Загрузки»", "downloads_enabled")
        self._toggle(
            l1, "Временные файлы (TEMP)", "Удалять насовсем файлы старше", "temp_enabled",
            spin=("temp_age_days", 1, 365, " дн."),
        )
        self._toggle(
            l1, "Корзина", "Очищать то, что лежит в ней дольше", "recycle_enabled",
            spin=("recycle_age_days", 1, 365, " дн."),
        )
        self._toggle(
            l1, "Мусор AutoCAD/Revit",
            "Удалять насовсем файлы, лежащие прямо на столе и в Загрузках", "cad_enabled",
        )
        masks = QLineEdit(", ".join(s.cad_masks))
        masks.setToolTip("Маски через запятую")
        masks.editingFinished.connect(
            lambda: self._set("cad_masks", [m.strip() for m in masks.text().split(",") if m.strip()])
        )
        l1.addWidget(masks)

        # Архив
        c2, l2 = self._section(lay, "Архив")
        self._spin_row(l2, "Хранить каждую уборку", "archive_keep_days", 7, 3650, " дн.")
        self._spin_row(l2, "Предупреждать об удалении за", "archive_warn_days", 1, 60, " дн.")

        # Расписание
        c3, l3 = self._section(lay, "Расписание")
        self._toggle(l3, "Автоуборка", "Сама убирает по расписанию; за минуту до начала спрошу", "auto_enabled")
        self._spin_row(l3, "Убирать каждые", "interval_days", 1, 90, " дн.")
        tr = QHBoxLayout()
        tr.addWidget(label("Время уборки"))
        tr.addStretch()
        te = QTimeEdit(QTime.fromString(s.run_time, "HH:mm"))
        te.setDisplayFormat("HH:mm")
        te.setFixedWidth(96)
        te.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        te.timeChanged.connect(lambda t: self._set("run_time", t.toString("HH:mm")))
        tr.addWidget(te)
        l3.addLayout(tr)
        self._spin_row(l3, "При автоуборке не трогать файлы свежее", "fresh_guard_hours", 0, 72, " ч")
        ar = QHBoxLayout()
        ar.addWidget(label("Запускать вместе с Windows"))
        ar.addStretch()
        sw = Switch(s.autostart)
        sw.toggled.connect(ctl.set_autostart)
        ar.addWidget(sw)
        l3.addLayout(ar)

        # Тон общения
        c4, l4 = self._section(lay, "Тон общения")
        hr = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label("Шутливый тон"))
        col.addWidget(
            label("Прораб с характером: шутки про стройку в уведомлениях и на кнопках", "Faint", wrap=True)
        )
        hr.addLayout(col, 1)
        hsw = Switch(s.humor)
        hsw.toggled.connect(ctl.set_humor)
        hr.addWidget(hsw)
        l4.addLayout(hr)
        adr = QHBoxLayout()
        adr.addWidget(label("Как обращаться"))
        adr.addStretch()
        self.addr = QComboBox()
        self.addr.addItem("Каждый раз по-разному", "")
        for a in phrases.ADDRESSES:
            self.addr.addItem(a, a)
        idx = self.addr.findData(s.address)
        self.addr.setCurrentIndex(max(0, idx))
        self.addr.setMinimumWidth(260)
        self.addr.setEnabled(s.humor)
        hsw.toggled.connect(self.addr.setEnabled)
        self.addr.currentIndexChanged.connect(
            lambda _i: ctl.set_address(self.addr.currentData())
        )
        adr.addWidget(self.addr)
        l4.addLayout(adr)

        lay.addWidget(label(f"{APP_NAME} {__version__} · настройки и журнал: {ctl.data_dir}", "Faint", wrap=True))
        lay.addStretch()

    def _section(self, lay, title):
        c = card()
        l = QVBoxLayout(c)
        l.setContentsMargins(22, 18, 22, 18)
        l.setSpacing(12)
        l.addWidget(label(title, "H2"))
        lay.addWidget(c)
        return c, l

    def _set(self, key, value) -> None:
        setattr(self.ctl.settings, key, value)
        self.ctl.save()

    def _toggle(self, lay, title, sub, key, spin=None) -> None:
        r = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label(title))
        col.addWidget(label(sub, "Faint", wrap=True))
        r.addLayout(col, 1)
        if spin:
            skey, lo, hi, suffix = spin
            sp = _spin(lo, hi, suffix, getattr(self.ctl.settings, skey))
            sp.valueChanged.connect(lambda v: self._set(skey, v))
            r.addWidget(sp)
        sw = Switch(getattr(self.ctl.settings, key))
        sw.toggled.connect(lambda v: self._set(key, v))
        r.addWidget(sw)
        lay.addLayout(r)

    def _spin_row(self, lay, title, key, lo, hi, suffix) -> None:
        r = QHBoxLayout()
        r.addWidget(label(title))
        r.addStretch()
        sp = _spin(lo, hi, suffix, getattr(self.ctl.settings, key))
        sp.valueChanged.connect(lambda v: self._set(key, v))
        r.addWidget(sp)
        lay.addLayout(r)


# ---------------------------------------------------------------- Окно
class MainWindow(QMainWindow):
    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icons.app_icon())
        self.resize(1080, 720)
        self.setMinimumSize(900, 600)

        central = QWidget()
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(220)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 20, 14, 16)
        sl.setSpacing(4)
        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(icons.app_pixmap(64).scaled(34, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        brand.addWidget(logo)
        brand.addWidget(label(APP_NAME, "Brand"))
        brand.addStretch()
        sl.addLayout(brand)
        sl.addSpacing(18)

        self.stack = QStackedWidget()
        self.group = QButtonGroup(self)
        pages = [
            ("home", "nav_home", HomePage(ctl)),
            ("zone", "nav_protect", ProtectPage(ctl)),
            ("archive", "nav_archive", ArchivePage(ctl)),
            ("journal", "nav_journal", JournalPage(ctl)),
            ("settings", "nav_settings", SettingsPage(ctl)),
        ]
        for i, (ic, title, page) in enumerate(pages):
            b = tone.bind(QPushButton(icons.nav_icon(ic), ""), title, "  ")
            b.setObjectName("Nav")
            b.setIconSize(QSize(20, 20))
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.group.addButton(b, i)
            sl.addWidget(b)
            self.stack.addWidget(page)
        self.group.button(0).setChecked(True)
        self.group.idClicked.connect(self.stack.setCurrentIndex)
        sl.addStretch()
        tip = label("Окно можно закрыть — Уборщик останется в трее и уберёт по расписанию.", "Faint", wrap=True)
        sl.addWidget(tip)

        h.addWidget(side)
        h.addWidget(self.stack, 1)
        self.setCentralWidget(central)

    def go(self, index: int) -> None:
        self.group.button(index).setChecked(True)
        self.stack.setCurrentIndex(index)

    def closeEvent(self, e) -> None:
        # Закрытие окна не выключает программу — она живёт в трее
        e.ignore()
        self.hide()
        self.ctl.on_window_hidden()
