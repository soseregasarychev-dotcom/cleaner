"""Чтение корзины Windows напрямую из $Recycle.Bin\\<SID>.

Каждый удалённый объект — пара файлов:
  $IXXXXXX.ext — метаданные (исходный путь, размер, время удаления);
  $RXXXXXX.ext — само содержимое (файл или папка).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

_EPOCH_1601 = datetime(1601, 1, 1, tzinfo=timezone.utc)


@dataclass
class RecycleItem:
    info_file: Path  # $I…
    data_path: Path  # $R…
    original_path: str
    size: int
    deleted_at: datetime  # локальное время без tz


def _filetime_to_local(ft: int) -> datetime:
    dt = _EPOCH_1601 + timedelta(microseconds=ft // 10)
    return dt.astimezone().replace(tzinfo=None)


def parse_info(data: bytes) -> tuple[str, int, datetime] | None:
    if len(data) < 24:
        return None
    version, size, ft = struct.unpack_from("<qqq", data, 0)
    try:
        if version == 2:
            (n,) = struct.unpack_from("<i", data, 24)
            raw = data[28 : 28 + n * 2]
        elif version == 1:
            raw = data[24 : 24 + 520]
        else:
            return None
        name = raw.decode("utf-16-le", errors="replace").split("\x00", 1)[0]
        return name, size, _filetime_to_local(ft)
    except (struct.error, OverflowError, ValueError):
        return None


def list_items(bin_dirs: list[Path]) -> list[RecycleItem]:
    items: list[RecycleItem] = []
    for d in bin_dirs:
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for info in entries:
            if not info.name.startswith("$I"):
                continue
            data_path = info.with_name("$R" + info.name[2:])
            try:
                parsed = parse_info(info.read_bytes())
            except OSError:
                continue
            if not parsed:
                continue
            name, size, deleted = parsed
            items.append(RecycleItem(info, data_path, name, size, deleted))
    return items
