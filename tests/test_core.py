import struct
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from conftest import age, make
from uborshchik import desktop_icons, recyclebin, schedule
from uborshchik.executor import execute
from uborshchik.fsops import Guard, GuardError, matches_any, unique_target
from uborshchik.planner import (
    CAT_CAD,
    CAT_DESKTOP,
    CAT_DOWNLOADS,
    CAT_PURGE,
    CAT_RECYCLE,
    CAT_TEMP,
    build_plan,
)


def labels(plan, cat):
    return sorted(a.path.name for a in plan.actions if a.category == cat)


# --- Guard ---------------------------------------------------------------

def test_guard_blocks_outside_and_protected(tmp_path):
    allowed = tmp_path / "Desktop"
    cloud = allowed / "Облако"
    g = Guard([allowed], [cloud])
    g.check(allowed / "file.pdf")
    with pytest.raises(GuardError):
        g.check(tmp_path / "other" / "file.pdf")
    with pytest.raises(GuardError):
        g.check(allowed)  # сам корень
    with pytest.raises(GuardError):
        g.check(cloud / "a.dwg")  # внутри облака
    with pytest.raises(GuardError):
        g.check(tmp_path)  # родитель облака


def test_masks_case_insensitive_and_revit_backup():
    assert matches_any("Чертёж.BAK", ["*.bak"])
    assert matches_any("model.0001.rvt", ["*.[0-9][0-9][0-9][0-9].rvt"])
    assert not matches_any("model.rvt", ["*.[0-9][0-9][0-9][0-9].rvt"])
    assert matches_any("x.sv$", ["*.sv$"])
    # Имя папки со скобками — как точное имя, а не как маска
    assert matches_any("Проект [2026]", ["Проект [2026]"])


def test_route_dropped_paths(loc):
    from uborshchik.planner import route_exclusions

    ok, skipped = route_exclusions(
        [
            loc.desktop / "Модели",
            str(loc.downloads / "setup.exe"),
            loc.desktop / "Модели" / "вложенный.rvt",
            r"D:\где-то\файл.pdf",
        ],
        loc.desktop,
        loc.downloads,
    )
    assert ok == [("desktop", "Модели"), ("downloads", "setup.exe")]
    assert len(skipped) == 2


def test_excluded_folder_is_kept(loc, settings):
    make(loc.desktop / "Модели" / "a.rvt")
    make(loc.desktop / "Проект [2026]" / "b.dwg")
    make(loc.desktop / "лишнее.pdf")
    settings.desktop_exclusions += ["Модели", "Проект [2026]"]
    plan = build_plan(settings, loc)
    assert labels(plan, CAT_DESKTOP) == ["лишнее.pdf"]


def test_unique_target(tmp_path):
    make(tmp_path / "a.pdf")
    make(tmp_path / "a (2).pdf")
    assert unique_target(tmp_path, "a.pdf").name == "a (3).pdf"
    assert unique_target(tmp_path, "b.pdf").name == "b.pdf"


# --- План ----------------------------------------------------------------

def test_desktop_plan_respects_exclusions(loc, settings):
    d = loc.desktop
    make(d / "report.pdf")
    make(d / "Chrome.lnk")
    make(d / "keep-me.docx")
    (d / "Папка").mkdir()
    make(d / "Папка" / "inner.bak")  # внутри папки мусор не ищем
    (d / "Архив").mkdir()
    make(d / "old.bak")
    settings.desktop_exclusions += ["keep-*"]
    plan = build_plan(settings, loc)
    assert labels(plan, CAT_DESKTOP) == ["report.pdf", "Папка"]
    assert labels(plan, CAT_CAD) == ["old.bak"]


def test_zone_names_kept(loc, settings):
    make(loc.desktop / "in-zone[1].pdf")
    make(loc.desktop / "out.pdf")
    loc.zone_names = {"in-zone[1].pdf"}
    settings.desktop_zone = [0, 0, 10, 10]
    plan = build_plan(settings, loc)
    assert labels(plan, CAT_DESKTOP) == ["out.pdf"]
    assert plan.zone_kept == ["in-zone[1].pdf"]


def test_zone_error_skips_desktop(loc, settings):
    make(loc.desktop / "out.pdf")
    make(loc.downloads / "setup.exe")
    settings.desktop_zone = [0, 0, 10, 10]
    loc.zone_error = "Проводник не отвечает"
    plan = build_plan(settings, loc)
    assert labels(plan, CAT_DESKTOP) == []
    assert labels(plan, CAT_DOWNLOADS) == ["setup.exe"]
    assert plan.warnings


def test_folder_with_cloud_inside_is_untouched(loc, settings):
    cloud = loc.desktop / "Облако" / "Yandex.Disk"
    make(cloud / "work.dwg")
    make(loc.desktop / "Облако" / "x.bak")
    loc.protected = [cloud]
    plan = build_plan(settings, loc)
    assert labels(plan, CAT_DESKTOP) == []
    assert any("Облако" in w for w in plan.warnings)


def test_fresh_guard_only_in_auto(loc, settings):
    make(loc.desktop / "just-saved.dwg")
    assert labels(build_plan(settings, loc, auto=False), CAT_DESKTOP) == ["just-saved.dwg"]
    assert labels(build_plan(settings, loc, auto=True), CAT_DESKTOP) == []


# --- Выполнение ----------------------------------------------------------

def test_execute_moves_to_dated_archive(loc, settings):
    make(loc.desktop / "a.pdf", b"12345")
    make(loc.downloads / "setup.exe")
    make(loc.desktop / "trash.bak")
    now = datetime(2026, 10, 25, 21, 0)
    plan = build_plan(settings, loc, now=now)
    report = execute(plan, loc)
    day = loc.desktop / "Архив" / "2026-10-25"
    assert (day / "a.pdf").read_bytes() == b"12345"
    assert (day / "Загрузки" / "setup.exe").exists()
    assert not (loc.desktop / "trash.bak").exists()
    assert not (day / "trash.bak").exists()
    assert report.moved == 2 and report.deleted == 1


def test_second_run_same_day_does_not_overwrite(loc, settings):
    now = datetime(2026, 10, 25)
    make(loc.desktop / "a.pdf", b"first")
    execute(build_plan(settings, loc, now=now), loc)
    make(loc.desktop / "a.pdf", b"second")
    execute(build_plan(settings, loc, now=now), loc)
    day = loc.desktop / "Архив" / "2026-10-25"
    assert (day / "a.pdf").read_bytes() == b"first"
    assert (day / "a (2).pdf").read_bytes() == b"second"


def test_locked_file_is_skipped(loc, settings):
    f = make(loc.desktop / "open.dwg")
    with open(f, "rb"):  # Python открывает без FILE_SHARE_DELETE
        report = execute(build_plan(settings, loc), loc)
    assert f.exists()
    assert report.skipped == 1 and report.moved == 0


def test_temp_deletes_only_old(loc, settings):
    old = make(loc.temp / "inst" / "old.cab", b"o" * 100)
    new = make(loc.temp / "inst" / "new.cab")
    age(old, 30)
    lone = make(loc.temp / "old.tmp")
    age(lone, 30)
    plan = build_plan(settings, loc)
    acts = [a for a in plan.actions if a.category == CAT_TEMP]
    assert sorted(a.path.name for a in acts) == ["inst", "old.tmp"]
    execute(plan, loc)
    assert not old.exists() and not lone.exists()
    assert new.exists()


def test_purge_expired_archive(loc, settings):
    root = loc.desktop / "Архив"
    make(root / "2026-07-01" / "a.pdf")
    make(root / "2026-10-01" / "b.pdf")
    make(root / "мои заметки" / "c.txt")  # не дата — не трогаем
    now = datetime(2026, 10, 25)
    plan = build_plan(settings, loc, now=now)
    assert [a.path.name for a in plan.actions if a.category == CAT_PURGE] == ["2026-07-01"]
    execute(plan, loc)
    assert not (root / "2026-07-01").exists()
    assert (root / "2026-10-01").exists() and (root / "мои заметки").exists()


# --- Корзина -------------------------------------------------------------

def _info_v2(name: str, size: int, when: datetime) -> bytes:
    ft = int((when.timestamp() + 11644473600) * 10_000_000)
    raw = (name + "\x00").encode("utf-16-le")
    return struct.pack("<qqqi", 2, size, ft, len(raw) // 2) + raw


def test_recycle_bin_old_items(loc, settings):
    settings.recycle_enabled = True
    b = loc.recycle_dirs[0]
    now = datetime(2026, 10, 25)
    make(b / "$IAAA111.pdf", _info_v2(r"C:\x\old.pdf", 3, now - timedelta(days=40)))
    make(b / "$RAAA111.pdf", b"old")
    make(b / "$IBBB222.pdf", _info_v2(r"C:\x\new.pdf", 3, now - timedelta(days=2)))
    make(b / "$RBBB222.pdf", b"new")
    items = recyclebin.list_items([b])
    assert {i.original_path for i in items} == {r"C:\x\old.pdf", r"C:\x\new.pdf"}
    plan = build_plan(settings, loc, now=now)
    acts = [a for a in plan.actions if a.category == CAT_RECYCLE]
    assert [a.label for a in acts] == ["old.pdf"]
    execute(plan, loc)
    assert not (b / "$RAAA111.pdf").exists() and not (b / "$IAAA111.pdf").exists()
    assert (b / "$RBBB222.pdf").exists()


# --- Расписание ----------------------------------------------------------

def test_schedule(settings):
    now = datetime(2026, 10, 25, 12, 0)
    assert schedule.next_run(settings, now) is None  # первый запуск — только руками
    settings.first_run_done = True
    settings.last_run = "2026-10-25T12:00:00"
    assert schedule.next_run(settings, now) == datetime(2026, 11, 4, 21, 0)
    assert not schedule.is_due(settings, datetime(2026, 11, 4, 20, 59))
    assert schedule.is_due(settings, datetime(2026, 11, 4, 21, 0))
    settings.postponed_until = "2026-11-05T09:00:00"
    assert schedule.next_run(settings, now) == datetime(2026, 11, 5, 9, 0)


def test_missed_run_is_caught_up(settings):
    """Комп был выключен 4 ноября в 21:00 — уборка догоняется при включении 5-го."""
    settings.first_run_done = True
    settings.last_run = "2026-10-25T21:00:00"
    assert schedule.is_due(settings, datetime(2026, 11, 5, 9, 15))
    # После догоняющей уборки отсчёт идёт от неё: следующая — 15 ноября в 21:00
    settings.last_run = "2026-11-05T09:20:00"
    assert schedule.next_run(settings, datetime(2026, 11, 5, 9, 21)) == datetime(2026, 11, 15, 21, 0)


def test_expiring_soon(loc, settings):
    root = loc.desktop / "Архив"
    (root / "2026-07-30").mkdir(parents=True)  # удалится 28.10 — через 3 дня
    (root / "2026-09-01").mkdir()
    soon = schedule.expiring_soon(settings, loc, date(2026, 10, 25))
    assert [f.path.name for f in soon] == ["2026-07-30"]
    settings.warned_archives = ["2026-07-30"]
    assert schedule.expiring_soon(settings, loc, date(2026, 10, 25)) == []


# --- Зона ----------------------------------------------------------------

def test_names_in_zone_matching():
    icons = [
        desktop_icons.Icon("Chrome", 0, 0, 10, 10),  # ярлык без .lnk
        desktop_icons.Icon("отчёт.pdf", 0, 20, 10, 30),
        desktop_icons.Icon("вне зоны.pdf", 100, 100, 110, 110),
    ]
    entries = [Path("Chrome.lnk"), Path("отчёт.pdf"), Path("вне зоны.pdf"), Path("Chrome")]
    names = desktop_icons.names_in_zone(entries, icons, (0, 0, 50, 50), hide_ext=False)
    # Папка «Chrome» подписана так же, как ярлык: при совпадении защищаем обоих
    assert names == {"Chrome.lnk", "отчёт.pdf", "Chrome"}


def test_names_in_zone_hidden_extensions():
    icons = [desktop_icons.Icon("план", 0, 0, 10, 10)]
    entries = [Path("план.dwg"), Path("план.pdf"), Path("другое.dwg")]
    names = desktop_icons.names_in_zone(entries, icons, (0, 0, 50, 50), hide_ext=True)
    assert names == {"план.dwg", "план.pdf"}
