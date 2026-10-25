import ctypes
import os
import time
from ctypes import wintypes
from pathlib import Path

import pytest

from uborshchik.config import Settings
from uborshchik.planner import Locations


@pytest.fixture
def loc(tmp_path: Path) -> Locations:
    for name in ("Desktop", "Downloads", "Temp", "Bin"):
        (tmp_path / name).mkdir()
    return Locations(
        desktop=tmp_path / "Desktop",
        downloads=tmp_path / "Downloads",
        temp=tmp_path / "Temp",
        recycle_dirs=[tmp_path / "Bin"],
        protected=[],
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(recycle_enabled=False)


def make(path: Path, content: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def age(path: Path, days: float) -> None:
    """Состарить файл/папку: и дату изменения, и дату создания."""
    ts = time.time() - days * 86400
    os.utime(path, (ts, ts))
    ft = int((ts + 11644473600) * 10_000_000)
    ftime = wintypes.FILETIME(ft & 0xFFFFFFFF, ft >> 32)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    h = k32.CreateFileW(
        str(path), 0x100, 0x7, None, 3, 0x02000000, None  # FILE_WRITE_ATTRIBUTES, BACKUP_SEMANTICS
    )
    assert h and h != wintypes.HANDLE(-1).value
    try:
        k32.SetFileTime(wintypes.HANDLE(h), ctypes.byref(ftime), None, ctypes.byref(ftime))
    finally:
        k32.CloseHandle(wintypes.HANDLE(h))
