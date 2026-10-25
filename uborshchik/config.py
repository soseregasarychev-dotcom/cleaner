"""Настройки Уборщика: dataclass + JSON в %APPDATA%\\Uborshchik\\settings.json."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

DEFAULT_CAD_MASKS = [
    "*.bak",
    "*.dwl",
    "*.dwl2",
    "*.sv$",
    "*.ac$",
    "*.pcp",
    "*.[0-9][0-9][0-9][0-9].rvt",
    "*.[0-9][0-9][0-9][0-9].rfa",
]


@dataclass
class Settings:
    # Где убирать
    desktop_enabled: bool = True
    downloads_enabled: bool = True
    temp_enabled: bool = True
    cad_enabled: bool = True
    recycle_enabled: bool = True

    # Исключения: имя или маска (*, ?), без учёта регистра
    desktop_exclusions: list[str] = field(
        default_factory=lambda: ["*.lnk", "*.url", "desktop.ini"]
    )
    downloads_exclusions: list[str] = field(default_factory=lambda: ["desktop.ini"])
    cad_masks: list[str] = field(default_factory=lambda: list(DEFAULT_CAD_MASKS))

    # Зона покоя на рабочем столе: [left, top, right, bottom] в физических
    # пикселях экрана. Всё, чьи значки стоят внутри, не убирается.
    desktop_zone: list[int] | None = None
    zone_visible: bool = True

    # Сроки
    archive_name: str = "Архив"
    archive_keep_days: int = 90
    archive_warn_days: int = 7
    temp_age_days: int = 7
    recycle_age_days: int = 30

    # Расписание
    auto_enabled: bool = True
    interval_days: int = 10
    run_time: str = "21:00"
    fresh_guard_hours: int = 1  # при автоуборке не трогать свежие файлы
    autostart: bool = True

    # Тон общения
    humor: bool = True
    address: str = ""  # пусто — случайное обращение каждый раз

    # Служебное
    first_run_done: bool = False
    last_run: str | None = None  # ISO datetime
    postponed_until: str | None = None
    warned_archives: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "Settings":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(path)
