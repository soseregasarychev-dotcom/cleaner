"""Системные пути Windows и список защищённых мест."""

from __future__ import annotations

import ctypes
import os
import subprocess
import uuid
from ctypes import wintypes
from pathlib import Path

from . import APP_ID

# Known Folder GUID-ы (KNOWNFOLDERID)
FOLDERID_DESKTOP = "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"
FOLDERID_DOWNLOADS = "{374DE290-123F-4565-9164-39C4925E467B}"
FOLDERID_DOCUMENTS = "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}"


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_str(cls, s: str) -> "_GUID":
        u = uuid.UUID(s)
        g = cls()
        g.Data1, g.Data2, g.Data3 = u.fields[0], u.fields[1], u.fields[2]
        for i, b in enumerate(u.bytes[8:]):
            g.Data4[i] = b
        return g


def known_folder(guid: str, fallback: Path) -> Path:
    """Путь известной папки Windows (учитывает перенос папки пользователем)."""
    try:
        buf = ctypes.c_wchar_p()
        shell32 = ctypes.windll.shell32
        res = shell32.SHGetKnownFolderPath(
            ctypes.byref(_GUID.from_str(guid)), 0, None, ctypes.byref(buf)
        )
        if res == 0 and buf.value:
            path = Path(buf.value)
            ctypes.windll.ole32.CoTaskMemFree(buf)
            return path
    except Exception:
        pass
    return fallback


def home() -> Path:
    return Path(os.environ.get("USERPROFILE", str(Path.home())))


def desktop_dir() -> Path:
    return known_folder(FOLDERID_DESKTOP, home() / "Desktop")


def downloads_dir() -> Path:
    return known_folder(FOLDERID_DOWNLOADS, home() / "Downloads")


def documents_dir() -> Path:
    return known_folder(FOLDERID_DOCUMENTS, home() / "Documents")


def temp_dir() -> Path:
    # Длинный путь вместо 8.3 (C:\Users\3AAF~1\...)
    raw = os.environ.get("TEMP") or str(home() / "AppData" / "Local" / "Temp")
    try:
        return Path(os.path.realpath(raw))
    except OSError:
        return Path(raw)


def cloud_dir() -> Path:
    """Облако владельца (Google Drive «Мой диск»)."""
    return home() / "Мой диск"


def app_data_dir() -> Path:
    base = Path(os.environ.get("APPDATA", str(home() / "AppData" / "Roaming")))
    d = base / APP_ID
    d.mkdir(parents=True, exist_ok=True)
    return d


def current_user_sid() -> str | None:
    """SID текущего пользователя — нужен для папки корзины $Recycle.Bin\\<SID>."""
    try:
        out = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            capture_output=True,
            encoding="oem",
            errors="replace",
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
        # "domain\user","S-1-5-21-..."
        parts = [p.strip().strip('"') for p in out.strip().split(",")]
        if len(parts) >= 2 and parts[-1].startswith("S-1-"):
            return parts[-1]
    except Exception:
        pass
    return None


def fixed_drives() -> list[Path]:
    """Локальные несъёмные диски — у каждого своя корзина."""
    drives: list[Path] = []
    try:
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if mask & (1 << i):
                root = f"{chr(65 + i)}:\\"
                # 3 = DRIVE_FIXED
                if ctypes.windll.kernel32.GetDriveTypeW(root) == 3:
                    drives.append(Path(root))
    except Exception:
        drives.append(Path("C:\\"))
    return drives


def recycle_bin_dirs() -> list[Path]:
    sid = current_user_sid()
    if not sid:
        return []
    result = []
    for drive in fixed_drives():
        d = drive / "$Recycle.Bin" / sid
        if d.is_dir():
            result.append(d)
    return result


def cloud_sync_roots() -> list[Path]:
    """Папки синхронизации облачных клиентов: всё, что в них удалено,
    удалится и в облаке, поэтому их не трогаем ни при каких условиях."""
    import winreg

    roots = [cloud_dir()]
    if os.environ.get("OneDrive"):
        roots.append(Path(os.environ["OneDrive"]))
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Yandex") as yk:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(yk, i)
                except OSError:
                    break
                i += 1
                if "disk" not in sub.lower():
                    continue
                try:
                    with winreg.OpenKey(yk, sub) as k:
                        for value in ("CurrentUserSyncPath", "RootFolder"):
                            try:
                                v = winreg.QueryValueEx(k, value)[0]
                                if v:
                                    roots.append(Path(v))
                            except OSError:
                                pass
                except OSError:
                    pass
    except OSError:
        pass
    seen, out = set(), []
    for r in roots:
        key = os.path.normcase(str(r))
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def protected_roots() -> list[Path]:
    """Места, которые Уборщик не трогает никогда."""
    h = home()
    roots = [
        *cloud_sync_roots(),
        documents_dir(),
        h / "AppData" / "Roaming",
        h / "Pictures",
        h / "Videos",
        h / "Music",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        Path(os.environ.get("ProgramData", r"C:\ProgramData")),
        Path(os.environ.get("SystemRoot", r"C:\Windows")),
    ]
    return roots
