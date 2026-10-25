"""Выполнение плана уборки и журнал."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from .fsops import Guard, GuardError, OpResult, delete_old_in_dir, delete_path, move_path
from .planner import Action, Locations, Plan


@dataclass
class CategoryStat:
    done: int = 0
    skipped: int = 0
    bytes: int = 0


@dataclass
class RunReport:
    started: str
    finished: str = ""
    trigger: str = "manual"  # manual | auto
    moved: int = 0
    deleted: int = 0
    skipped: int = 0
    freed: int = 0  # байт удалено насовсем
    archived: int = 0  # байт перенесено в архив
    categories: dict[str, CategoryStat] = field(default_factory=dict)
    details: list[dict] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def summary(self) -> str:
        from .util import human_size

        parts = []
        if self.moved:
            parts.append(f"в архив: {self.moved} шт. ({human_size(self.archived)})")
        if self.freed:
            parts.append(f"освобождено {human_size(self.freed)}")
        if self.skipped:
            parts.append(f"пропущено {self.skipped} (заняты)")
        return ", ".join(parts) or "убирать было нечего"


def execute(
    plan: Plan,
    loc: Locations,
    trigger: str = "manual",
    progress: Callable[[int, int, str], None] | None = None,
) -> RunReport:
    guard = Guard(loc.allowed_roots(), loc.protected)
    report = RunReport(started=datetime.now().isoformat(timespec="seconds"), trigger=trigger)
    actions = [a for a in plan.actions if a.enabled]
    total = len(actions)
    for i, a in enumerate(actions):
        if progress:
            progress(i, total, a.label)
        stat = report.categories.setdefault(a.category, CategoryStat())
        try:
            _run_one(a, guard, report, stat)
        except GuardError as e:
            report.skipped += 1
            stat.skipped += 1
            report.problems.append(str(e))
            report.details.append(_detail(a, "blocked", str(e)))
    if progress:
        progress(total, total, "Готово")
    report.finished = datetime.now().isoformat(timespec="seconds")
    return report


def _run_one(a: Action, guard: Guard, report: RunReport, stat: CategoryStat) -> None:
    if a.kind == "move":
        if not a.path.exists() and not a.path.is_symlink():
            return
        target, err = move_path(a.path, a.dest, guard)
        if target:
            report.moved += 1
            report.archived += a.size
            stat.done += 1
            stat.bytes += a.size
            report.details.append(_detail(a, "moved", str(target)))
        else:
            report.skipped += 1
            stat.skipped += 1
            report.problems.append(f"{a.label}: {err}")
            report.details.append(_detail(a, "skipped", err or ""))
        return

    if a.kind == "clean_old":
        cutoff = a.cutoff or (datetime.now() - timedelta(days=7)).timestamp()
        res = delete_old_in_dir(a.path, cutoff, guard)
    elif a.kind == "recycle":
        res = OpResult()
        if a.path.exists():
            res.add(delete_path(a.path, guard))
        if a.extra and a.extra.exists() and not a.path.exists():
            delete_path(a.extra, guard)  # $I-файл — после содержимого
            if res.done == 0:
                res.done = 1
    else:  # delete | purge
        res = delete_path(a.path, guard)

    report.deleted += res.done
    report.freed += res.freed
    report.skipped += res.skipped
    stat.done += res.done
    stat.skipped += res.skipped
    stat.bytes += res.freed
    status = "deleted" if not res.skipped else ("partial" if res.done else "skipped")
    report.details.append(_detail(a, status, f"{res.done} удалено, {res.skipped} занято"))


def _detail(a: Action, status: str, info: str) -> dict:
    return {
        "category": a.category,
        "kind": a.kind,
        "path": str(a.path),
        "size": a.size,
        "status": status,
        "info": info,
    }


class Journal:
    """Журнал уборок: одна строка JSON на запуск."""

    def __init__(self, path: Path):
        self.path = path

    def append(self, report: RunReport) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(report), ensure_ascii=False) + "\n")

    def read(self, limit: int = 200) -> list[dict]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return list(reversed(rows))[:limit]
