"""Когда убирать: чистая логика расписания (без таймеров и окон)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from .config import Settings
from .planner import ArchiveFolder, Locations, archive_folders


def _run_time(s: Settings) -> time:
    try:
        h, m = s.run_time.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        return time(21, 0)


def next_run(s: Settings, now: datetime) -> datetime | None:
    """Следующая автоуборка. None — автоуборка выключена или ещё не было
    первого (ручного, с просмотром) запуска."""
    if not s.auto_enabled or not s.first_run_done:
        return None
    t = _run_time(s)
    if s.last_run:
        last = datetime.fromisoformat(s.last_run)
        nxt = datetime.combine(last.date() + timedelta(days=max(1, s.interval_days)), t)
    else:
        nxt = datetime.combine(now.date(), t)
    if s.postponed_until:
        post = datetime.fromisoformat(s.postponed_until)
        if post > nxt:
            nxt = post
    return nxt


def is_due(s: Settings, now: datetime) -> bool:
    nxt = next_run(s, now)
    return nxt is not None and now >= nxt


def expiring_soon(s: Settings, loc: Locations, today: date) -> list[ArchiveFolder]:
    """Папки архива, которые удалятся в ближайшие дни и о которых ещё не предупреждали."""
    out = []
    for f in archive_folders(loc.archive_root(s), s.archive_keep_days):
        left = f.days_left(today)
        if 0 < left <= s.archive_warn_days and f.path.name not in s.warned_archives:
            out.append(f)
    return out
