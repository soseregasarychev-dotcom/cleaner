"""Фоновые задачи: план и уборка идут в отдельном потоке, окно не зависает."""

from __future__ import annotations

import copy

from PySide6.QtCore import QThread, Signal

from ..config import Settings
from ..executor import RunReport, execute
from ..planner import Locations, Plan, build_plan


class PlanWorker(QThread):
    progress = Signal(str)
    done = Signal(object, object)  # Plan, Locations
    failed = Signal(str)

    def __init__(self, settings: Settings, auto: bool = False, parent=None):
        super().__init__(parent)
        self.settings = copy.deepcopy(settings)
        self.auto = auto

    def run(self) -> None:
        try:
            loc = Locations.system(self.settings)
            plan = build_plan(self.settings, loc, auto=self.auto, progress=self.progress.emit)
            self.done.emit(plan, loc)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class ExecWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(object)  # RunReport

    def __init__(self, plan: Plan, loc: Locations, trigger: str, parent=None):
        super().__init__(parent)
        self.plan, self.loc, self.trigger = plan, loc, trigger

    def run(self) -> None:
        report: RunReport = execute(self.plan, self.loc, self.trigger, self.progress.emit)
        self.done.emit(report)
