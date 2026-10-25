"""Планирование уборки: что перенести, что удалить. Ничего не меняет на диске."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from . import paths, recyclebin
from .config import Settings
from .fsops import (
    FILE_ATTRIBUTE_REPARSE_POINT,
    is_reparse,
    is_system,
    is_within,
    item_time,
    matches_any,
    tree_size,
)

CAT_DESKTOP = "Рабочий стол → архив"
CAT_DOWNLOADS = "Загрузки → архив"
CAT_CAD = "Мусор AutoCAD/Revit"
CAT_TEMP = "Временные файлы (TEMP)"
CAT_RECYCLE = "Корзина"
CAT_PURGE = "Архив старше срока"

CATEGORY_ORDER = [CAT_DESKTOP, CAT_DOWNLOADS, CAT_CAD, CAT_TEMP, CAT_RECYCLE, CAT_PURGE]

DOWNLOADS_SUBDIR = "Загрузки"


@dataclass
class Locations:
    desktop: Path
    downloads: Path
    temp: Path
    recycle_dirs: list[Path]
    protected: list[Path]
    # Имена объектов рабочего стола, стоящих в зоне покоя
    zone_names: set[str] = field(default_factory=set)
    # Зона задана, но значки прочитать не удалось — рабочий стол не трогаем
    zone_error: str | None = None

    @classmethod
    def system(cls, s: Settings | None = None) -> "Locations":
        loc = cls(
            desktop=paths.desktop_dir(),
            downloads=paths.downloads_dir(),
            temp=paths.temp_dir(),
            recycle_dirs=paths.recycle_bin_dirs(),
            protected=paths.protected_roots(),
        )
        if s is not None:
            loc.resolve_zone(s)
        return loc

    def resolve_zone(self, s: Settings) -> None:
        self.zone_names, self.zone_error = set(), None
        if not s.desktop_zone:
            return
        from . import desktop_icons

        try:
            icons = desktop_icons.read_icons()
            if not icons:
                raise desktop_icons.DesktopIconsError("значки не найдены")
            self.zone_names = desktop_icons.names_in_zone(
                _top_entries(self.desktop),
                icons,
                tuple(s.desktop_zone),
                desktop_icons.extensions_hidden(),
            )
        except Exception as e:  # noqa: BLE001 — любая ошибка = не рискуем
            self.zone_error = str(e)

    def archive_root(self, s: Settings) -> Path:
        return self.desktop / s.archive_name

    def allowed_roots(self) -> list[Path]:
        return [self.desktop, self.downloads, self.temp, *self.recycle_dirs]


@dataclass
class Action:
    kind: str  # move | delete | clean_old | recycle | purge
    category: str
    path: Path
    label: str
    size: int = 0
    files: int = 0
    dest: Path | None = None
    extra: Path | None = None  # для корзины: файл $I
    cutoff: float | None = None  # для clean_old: удалять всё старше этой метки
    note: str = ""
    enabled: bool = True
    exclusion_key: str | None = None  # имя для «добавить в исключения»


@dataclass
class Plan:
    created: datetime
    archive_root: Path
    day_dir: Path
    actions: list[Action] = field(default_factory=list)
    auto: bool = False
    warnings: list[str] = field(default_factory=list)
    zone_kept: list[str] = field(default_factory=list)  # что осталось в зоне

    def by_category(self) -> dict[str, list[Action]]:
        out: dict[str, list[Action]] = {c: [] for c in CATEGORY_ORDER}
        for a in self.actions:
            out.setdefault(a.category, []).append(a)
        return {k: v for k, v in out.items() if v}

    @property
    def total_size(self) -> int:
        return sum(a.size for a in self.actions if a.enabled)


@dataclass
class ArchiveFolder:
    path: Path
    day: date
    expires: date

    def days_left(self, today: date) -> int:
        return (self.expires - today).days


def parse_day(name: str) -> date | None:
    try:
        return datetime.strptime(name, "%Y-%m-%d").date()
    except ValueError:
        return None


def archive_folders(archive_root: Path, keep_days: int) -> list[ArchiveFolder]:
    result = []
    try:
        entries = list(archive_root.iterdir())
    except OSError:
        return result
    for e in entries:
        d = parse_day(e.name)
        if d and e.is_dir() and not is_reparse(e):
            result.append(ArchiveFolder(e, d, d + timedelta(days=keep_days)))
    return sorted(result, key=lambda f: f.day, reverse=True)


def _top_entries(root: Path) -> list[Path]:
    try:
        return sorted(root.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return []


def _old_size(path: Path, cutoff: float) -> tuple[int, int]:
    """Сколько байт/файлов внутри старше cutoff (без перехода по ссылкам)."""
    if is_reparse(path):
        return 0, 0
    if path.is_file():
        if item_time(path) < cutoff:
            try:
                return os.lstat(path).st_size, 1
            except OSError:
                return 0, 0
        return 0, 0
    total = count = 0
    stack = [str(path)]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    try:
                        st = e.stat(follow_symlinks=False)
                        if getattr(st, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
                            continue
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        elif max(st.st_mtime, st.st_ctime) < cutoff:
                            total += st.st_size
                            count += 1
                    except OSError:
                        continue
        except OSError:
            continue
    return total, count


def build_plan(
    s: Settings,
    loc: Locations,
    now: datetime | None = None,
    auto: bool = False,
    progress: Callable[[str], None] | None = None,
) -> Plan:
    now = now or datetime.now()
    say = progress or (lambda _m: None)
    archive_root = loc.archive_root(s)
    day_dir = archive_root / now.strftime("%Y-%m-%d")
    plan = Plan(created=now, archive_root=archive_root, day_dir=day_dir, auto=auto)
    fresh_cutoff = (now - timedelta(hours=s.fresh_guard_hours)).timestamp() if auto else None

    def is_fresh(p: Path) -> bool:
        return fresh_cutoff is not None and item_time(p) > fresh_cutoff

    desktop_ok = True
    if s.desktop_zone and loc.zone_error:
        desktop_ok = False
        plan.warnings.append(
            "Рабочий стол пропущен: не удалось прочитать, какие значки стоят "
            f"в зоне покоя ({loc.zone_error})."
        )
    plan.zone_kept = sorted(loc.zone_names, key=str.lower)
    zone_keep = {n.lower() for n in loc.zone_names}

    sources: list[tuple[Path, list[str], bool, str, Path]] = []
    if desktop_ok:
        sources.append(
            (loc.desktop, s.desktop_exclusions, s.desktop_enabled, CAT_DESKTOP, day_dir)
        )
    sources += [
        (
            loc.downloads,
            s.downloads_exclusions,
            s.downloads_enabled,
            CAT_DOWNLOADS,
            day_dir / DOWNLOADS_SUBDIR,
        ),
    ]

    # Папки, внутри которых облако (или которые сами в облаке), не трогаем
    for root, *_ in sources:
        for top in _top_entries(root):
            if top.is_dir() and _touches(top, loc.protected):
                plan.warnings.append(
                    f"«{top.name}» не трогаю: внутри папка облака или защищённое место."
                )

    # 1. Мусор САПР — только файлы, лежащие прямо на столе / в Загрузках.
    #    Внутрь папок не заходим: там могут быть рабочие копии и облако.
    cad_files: set[str] = set()
    if s.cad_enabled and s.cad_masks:
        say("Ищу мусор AutoCAD/Revit…")
        for root, excl, _enabled, _cat, _dst in sources:
            keep = zone_keep if root == loc.desktop else set()
            for top in _top_entries(root):
                if _skip_top(top, archive_root, excl, keep) or _touches(top, loc.protected):
                    continue
                if top.is_file() and not is_reparse(top) and matches_any(top.name, s.cad_masks):
                    if is_fresh(top):
                        continue
                    size, _ = tree_size(top)
                    cad_files.add(os.path.normcase(str(top)))
                    plan.actions.append(
                        Action("delete", CAT_CAD, top, _rel(top, root.parent), size, 1)
                    )

    # 2–3. Рабочий стол и Загрузки → архив
    for root, excl, enabled, cat, dst in sources:
        if not enabled:
            continue
        say(f"Смотрю {root.name}…")
        keep = zone_keep if root == loc.desktop else set()
        for top in _top_entries(root):
            if _skip_top(top, archive_root, excl, keep):
                continue
            if _touches(top, loc.protected):
                continue
            if os.path.normcase(str(top)) in cad_files:
                continue
            if is_fresh(top):
                continue
            size, files = tree_size(top)
            plan.actions.append(
                Action(
                    "move",
                    cat,
                    top,
                    top.name + ("\\" if top.is_dir() else ""),
                    size,
                    files,
                    dest=dst,
                    exclusion_key=top.name,
                )
            )

    # 4. TEMP
    if s.temp_enabled and loc.temp.is_dir():
        say("Считаю временные файлы…")
        cutoff = (now - timedelta(days=s.temp_age_days)).timestamp()
        for top in _top_entries(loc.temp):
            size, files = _old_size(top, cutoff)
            empty_old_dir = top.is_dir() and files == 0 and item_time(top) < cutoff
            if size or files or empty_old_dir:
                plan.actions.append(
                    Action(
                        "clean_old",
                        CAT_TEMP,
                        top,
                        top.name + ("\\" if top.is_dir() else ""),
                        size,
                        files,
                        cutoff=cutoff,
                        note=f"старше {s.temp_age_days} дн.",
                    )
                )

    # 5. Корзина
    if s.recycle_enabled and loc.recycle_dirs:
        say("Проверяю корзину…")
        limit = now - timedelta(days=s.recycle_age_days)
        for item in recyclebin.list_items(loc.recycle_dirs):
            if item.deleted_at < limit:
                size, files = tree_size(item.data_path)
                plan.actions.append(
                    Action(
                        "recycle",
                        CAT_RECYCLE,
                        item.data_path,
                        Path(item.original_path).name or item.original_path,
                        size or item.size,
                        files,
                        extra=item.info_file,
                        note=f"в корзине с {item.deleted_at:%d.%m.%Y}",
                    )
                )

    # 6. Просроченный архив
    plan.actions.extend(purge_actions(s, loc, now.date()))
    return plan


def purge_actions(s: Settings, loc: Locations, today: date) -> list[Action]:
    out = []
    for f in archive_folders(loc.archive_root(s), s.archive_keep_days):
        if f.expires <= today:
            size, files = tree_size(f.path)
            out.append(
                Action(
                    "purge",
                    CAT_PURGE,
                    f.path,
                    f"Архив от {f.day:%d.%m.%Y}",
                    size,
                    files,
                    note=f"хранился {s.archive_keep_days} дн.",
                )
            )
    return out


def _skip_top(
    top: Path, archive_root: Path, exclusions: list[str], keep: set[str] = frozenset()
) -> bool:
    if os.path.normcase(str(top)) == os.path.normcase(str(archive_root)):
        return True
    if top.name.lower() in keep:  # стоит в зоне покоя
        return True
    if matches_any(top.name, exclusions):
        return True
    if is_system(top):  # desktop.ini и прочие системные файлы
        return True
    return False


def route_exclusions(
    paths: list[str | Path], desktop: Path, downloads: Path
) -> tuple[list[tuple[str, str]], list[str]]:
    """Разложить пути (из перетаскивания или окна выбора) по спискам исключений.

    Возвращает ([(«desktop»|«downloads», имя)], [пропущенные пути]).
    Исключение — это имя объекта, лежащего прямо в источнике; вложенное не годится,
    потому что убирается целиком родительская папка.
    """
    roots = {"desktop": desktop, "downloads": downloads}
    ok, skipped = [], []
    for raw in paths:
        p = Path(raw)
        parent = os.path.normcase(os.path.abspath(str(p.parent)))
        for src, root in roots.items():
            if parent == os.path.normcase(os.path.abspath(str(root))):
                ok.append((src, p.name))
                break
        else:
            skipped.append(str(p))
    return ok, skipped


def _touches(path: Path, protected: list[Path]) -> bool:
    """Путь внутри защищённого места или содержит его внутри себя."""
    return any(is_within(path, p) or is_within(p, path) for p in protected)


def _rel(p: Path, root: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)
