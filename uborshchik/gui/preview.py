"""Окно «Вот что я сделаю»: план с галочками → уборка → итог."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import phrases
from ..executor import RunReport
from ..planner import CAT_DESKTOP, CAT_DOWNLOADS, Action, Locations, Plan
from ..util import human_size, plural
from . import theme, tone
from .widgets import Banner, label

CAT_HINT = {
    CAT_DESKTOP: "перенесу в архив",
    CAT_DOWNLOADS: "перенесу в архив",
}
ROLE_ACTION = Qt.UserRole + 1


def show_in_explorer(path: Path) -> None:
    subprocess.Popen(["explorer", f"/select,{path}"])


class PreviewDialog(QDialog):
    run_requested = Signal(object)  # Plan
    exclude_requested = Signal(str, str)  # источник ("desktop"/"downloads"), имя

    def __init__(self, plan: Plan, loc: Locations, parent=None):
        super().__init__(parent)
        self.plan, self.loc = plan, loc
        self.setWindowTitle("Уборщик — проверка перед уборкой")
        self.resize(900, 640)
        self.setMinimumSize(720, 480)

        self.stack = QStackedWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.stack)
        self.stack.addWidget(self._build_review())
        self.stack.addWidget(self._build_progress())
        self.stack.addWidget(self._build_result())

    # --- 1. Просмотр ---------------------------------------------------
    def _build_review(self) -> QWidget:
        w = QWidget()
        w.setObjectName("Page")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(12)
        lay.addWidget(label(phrases.pick("preview_title"), "H1"))
        self.summary = label("", "Muted", wrap=True)
        lay.addWidget(self.summary)

        for wtext in self.plan.warnings:
            lay.addWidget(Banner("⚠  " + wtext))
        if self.plan.zone_kept:
            n = len(self.plan.zone_kept)
            info = Banner(
                f"В зоне покоя {n} {plural(n, 'объект', 'объекта', 'объектов')} — их не трогаю.",
                kind="Info",
            )
            info.setToolTip("\n".join(self.plan.zone_kept[:40]))
            lay.addWidget(info)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Что", "Размер", ""])
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        hdr = self.tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setStretchLastSection(False)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        self.tree.itemDoubleClicked.connect(self._open_item)
        self._fill_tree()
        self.tree.itemChanged.connect(self._update_summary)
        lay.addWidget(self.tree, 1)

        hint = label(
            "Снимите галочку, чтобы пропустить. Правый щелчок — «больше никогда не трогать». "
            "Двойной щелчок — показать в Проводнике.",
            "Faint",
            wrap=True,
        )
        lay.addWidget(hint)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = tone.bind(QPushButton(), "preview_cancel")
        cancel.clicked.connect(self.reject)
        self.go = tone.bind(QPushButton(), "preview_go")
        self.go.setObjectName("Primary")
        self.go.setDefault(True)
        self.go.clicked.connect(self._run)
        btns.addWidget(cancel)
        btns.addWidget(self.go)
        lay.addLayout(btns)
        self._update_summary()
        return w

    def _fill_tree(self) -> None:
        self.tree.blockSignals(True)
        bold = theme.font(10, theme.QFont.Weight.DemiBold)
        for cat, actions in self.plan.by_category().items():
            top = QTreeWidgetItem(self.tree)
            top.setFlags(top.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
            top.setCheckState(0, Qt.Checked)
            size = sum(a.size for a in actions)
            hint = CAT_HINT.get(cat, "удалю насовсем")
            top.setText(0, f"{cat}  ·  {len(actions)}")
            top.setText(1, human_size(size))
            top.setText(2, hint)
            top.setFont(0, bold)
            top.setFont(1, bold)
            top.setForeground(2, Qt.darkGray)
            for a in sorted(actions, key=lambda a: -a.size):
                it = QTreeWidgetItem(top)
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(0, Qt.Checked)
                it.setText(0, a.label)
                it.setToolTip(0, str(a.path))
                it.setText(1, human_size(a.size))
                it.setText(2, a.note)
                it.setForeground(2, Qt.gray)
                it.setData(0, ROLE_ACTION, a)
        self.tree.blockSignals(False)

    def _actions_checked(self) -> list[Action]:
        # Выполняется только то, что сейчас отмечено в дереве
        for a in self.plan.actions:
            a.enabled = False
        out = []
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                it = top.child(j)
                a: Action = it.data(0, ROLE_ACTION)
                a.enabled = it.checkState(0) == Qt.Checked
                if a.enabled:
                    out.append(a)
        return out

    def _update_summary(self, *_):
        acts = self._actions_checked()
        moved = [a for a in acts if a.kind == "move"]
        deleted = [a for a in acts if a.kind != "move"]
        parts = []
        if moved:
            parts.append(
                f"в архив <b>{len(moved)}</b> {plural(len(moved), 'объект', 'объекта', 'объектов')} "
                f"({human_size(sum(a.size for a in moved))})"
            )
        if deleted:
            parts.append(f"освобожу <b>{human_size(sum(a.size for a in deleted))}</b>")
        text = " · ".join(parts) if parts else phrases.pick("preview_empty")
        self.summary.setText(
            text + f"<br><span style='color:{theme.FAINT}'>Архив: {self.plan.day_dir}</span>"
        )
        self.go.setEnabled(bool(acts))

    def _menu(self, pos) -> None:
        it = self.tree.itemAt(pos)
        a: Action | None = it.data(0, ROLE_ACTION) if it else None
        if not a:
            return
        m = QMenu(self)
        m.addAction("Показать в Проводнике", lambda: self._open_item(it))
        if a.exclusion_key and a.category in (CAT_DESKTOP, CAT_DOWNLOADS):
            src = "desktop" if a.category == CAT_DESKTOP else "downloads"
            m.addAction(
                "Больше никогда не трогать",
                lambda: self._exclude(it, src, a.exclusion_key),
            )
        m.exec(self.tree.viewport().mapToGlobal(pos))

    def _exclude(self, it: QTreeWidgetItem, src: str, name: str) -> None:
        self.exclude_requested.emit(src, name)
        parent = it.parent()
        parent.removeChild(it)
        if parent.childCount() == 0:
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(parent))
        self._update_summary()

    def _open_item(self, it: QTreeWidgetItem, *_):
        a: Action | None = it.data(0, ROLE_ACTION)
        if a and a.path.exists():
            show_in_explorer(a.path)

    def _run(self) -> None:
        self._actions_checked()
        self.stack.setCurrentIndex(1)
        self.run_requested.emit(self.plan)

    # --- 2. Процесс ----------------------------------------------------
    def _build_progress(self) -> QWidget:
        w = QWidget()
        w.setObjectName("Page")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(60, 60, 60, 60)
        lay.addStretch()
        lay.addWidget(label(phrases.pick("progress_title"), "H1"), 0, Qt.AlignHCenter)
        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(8)
        lay.addSpacing(16)
        lay.addWidget(self.pbar)
        self.pstatus = label("", "Muted")
        self.pstatus.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.pstatus)
        lay.addStretch()
        return w

    def on_progress(self, i: int, n: int, text: str) -> None:
        self.pbar.setMaximum(max(1, n))
        self.pbar.setValue(i)
        fm = self.pstatus.fontMetrics()
        self.pstatus.setText(fm.elidedText(text, Qt.ElideMiddle, 600))

    # --- 3. Итог -------------------------------------------------------
    def _build_result(self) -> QWidget:
        w = QWidget()
        w.setObjectName("Page")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 40, 40, 30)
        lay.addStretch()
        check = QLabel("✓")
        check.setAlignment(Qt.AlignCenter)
        check.setFixedSize(72, 72)
        check.setStyleSheet(
            f"background:{theme.ACCENT_SOFT}; color:{theme.ACCENT}; border-radius:36px;"
            "font-size:30pt; font-weight:700;"
        )
        lay.addWidget(check, 0, Qt.AlignHCenter)
        lay.addSpacing(10)
        self.result_title = label("", "H1")
        lay.addWidget(self.result_title, 0, Qt.AlignHCenter)
        self.result_text = label("", "Muted", wrap=True)
        self.result_text.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.result_text)
        self.result_problems = label("", "Faint", wrap=True)
        self.result_problems.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.result_problems)
        lay.addStretch()
        btns = QHBoxLayout()
        btns.addStretch()
        self.open_archive = tone.bind(QPushButton(), "result_archive")
        self.open_archive.clicked.connect(
            lambda: os.startfile(self.plan.day_dir if self.plan.day_dir.exists() else self.plan.archive_root)
            if self.plan.archive_root.exists()
            else None
        )
        close = tone.bind(QPushButton(), "result_close")
        close.setObjectName("Primary")
        close.clicked.connect(self.accept)
        btns.addWidget(self.open_archive)
        btns.addWidget(close)
        btns.addStretch()
        lay.addLayout(btns)
        return w

    def show_result(self, report: RunReport) -> None:
        self.result_title.setText(phrases.pick("result_title"))
        self.result_text.setText(report.summary().capitalize())
        if report.problems:
            shown = "\n".join(report.problems[:4])
            more = len(report.problems) - 4
            self.result_problems.setText(
                phrases.pick("result_problems")
                + "\n"
                + shown
                + (f"\n… и ещё {more}" if more > 0 else "")
            )
        self.open_archive.setVisible(report.moved > 0)
        self.stack.setCurrentIndex(2)
