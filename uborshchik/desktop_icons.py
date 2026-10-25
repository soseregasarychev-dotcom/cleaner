"""Координаты значков на рабочем столе.

Рабочий стол Windows — это список SysListView32 внутри процесса Проводника.
Чтобы спросить у него подписи и прямоугольники значков, выделяем память в
процессе explorer.exe, шлём сообщения LVM_* и читаем ответ обратно.
Координаты — физические пиксели экрана.
"""

from __future__ import annotations

import ctypes
import os
import winreg
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LVM_FIRST = 0x1000
LVM_GETITEMCOUNT = LVM_FIRST + 4
LVM_GETITEMRECT = LVM_FIRST + 14
LVM_GETITEMTEXTW = LVM_FIRST + 115
LVIF_TEXT = 0x1
LVIR_BOUNDS = 0

PROCESS_VM_OPERATION = 0x8
PROCESS_VM_READ = 0x10
PROCESS_VM_WRITE = 0x20
PROCESS_QUERY_INFORMATION = 0x400
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x4
SMTO_ABORTIFHUNG = 0x2

user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowExW.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.SendMessageTimeoutW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
]
user32.SendMessageTimeoutW.restype = wintypes.LPARAM
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
kernel32.VirtualAllocEx.restype = ctypes.c_void_p
kernel32.VirtualFreeEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
kernel32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


class LVITEMW(ctypes.Structure):
    _fields_ = [
        ("mask", wintypes.UINT),
        ("iItem", ctypes.c_int),
        ("iSubItem", ctypes.c_int),
        ("state", wintypes.UINT),
        ("stateMask", wintypes.UINT),
        ("pszText", ctypes.c_void_p),
        ("cchTextMax", ctypes.c_int),
        ("iImage", ctypes.c_int),
        ("lParam", wintypes.LPARAM),
        ("iIndent", ctypes.c_int),
        ("iGroupId", ctypes.c_int),
        ("cColumns", wintypes.UINT),
        ("puColumns", ctypes.c_void_p),
        ("piColFmt", ctypes.c_void_p),
        ("iGroup", ctypes.c_int),
    ]


class DesktopIconsError(Exception):
    pass


@dataclass
class Icon:
    label: str
    left: int
    top: int
    right: int
    bottom: int

    @property
    def center(self) -> tuple[int, int]:
        return (self.left + self.right) // 2, (self.top + self.bottom) // 2


def set_dpi_aware() -> None:
    """Для консольного режима: координаты в физических пикселях, как у Qt."""
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass


def find_desktop_listview() -> int:
    progman = user32.FindWindowW("Progman", None)
    defview = user32.FindWindowExW(progman, None, "SHELLDLL_DefView", None) if progman else None
    if not defview:
        # Со слайд-шоу обоев значки живут в одном из окон WorkerW
        worker = None
        while True:
            worker = user32.FindWindowExW(None, worker, "WorkerW", None)
            if not worker:
                break
            defview = user32.FindWindowExW(worker, None, "SHELLDLL_DefView", None)
            if defview:
                break
    if not defview:
        raise DesktopIconsError("не найден рабочий стол Проводника")
    lv = user32.FindWindowExW(defview, None, "SysListView32", None)
    if not lv:
        raise DesktopIconsError("не найден список значков")
    return lv


def _send(hwnd, msg, wparam, lparam) -> int:
    result = ctypes.c_size_t()
    ok = user32.SendMessageTimeoutW(
        hwnd, msg, wparam, lparam, SMTO_ABORTIFHUNG, 2000, ctypes.byref(result)
    )
    if not ok:
        raise DesktopIconsError("Проводник не отвечает")
    return result.value


def read_icons() -> list[Icon]:
    lv = find_desktop_listview()
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(lv, ctypes.byref(pid))
    hproc = kernel32.OpenProcess(
        PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION,
        False,
        pid.value,
    )
    if not hproc:
        raise DesktopIconsError("нет доступа к процессу Проводника")
    size = 4096
    remote = kernel32.VirtualAllocEx(hproc, None, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
    if not remote:
        kernel32.CloseHandle(hproc)
        raise DesktopIconsError("не удалось выделить память в Проводнике")
    text_off = 1024
    icons: list[Icon] = []
    try:
        count = _send(lv, LVM_GETITEMCOUNT, 0, 0)
        origin = wintypes.POINT(0, 0)
        user32.ClientToScreen(lv, ctypes.byref(origin))
        for i in range(count):
            item = LVITEMW()
            item.mask = LVIF_TEXT
            item.iItem = i
            item.iSubItem = 0
            item.pszText = remote + text_off
            item.cchTextMax = 1024
            _write(hproc, remote, item)
            n = _send(lv, LVM_GETITEMTEXTW, i, remote)
            buf = ctypes.create_unicode_buffer(1024)
            _read(hproc, remote + text_off, buf, ctypes.sizeof(buf))
            label = buf.value[:n] if n else buf.value

            rect = wintypes.RECT(LVIR_BOUNDS, 0, 0, 0)
            _write(hproc, remote, rect)
            if not _send(lv, LVM_GETITEMRECT, i, remote):
                continue
            _read(hproc, remote, rect, ctypes.sizeof(rect))
            icons.append(
                Icon(
                    label,
                    rect.left + origin.x,
                    rect.top + origin.y,
                    rect.right + origin.x,
                    rect.bottom + origin.y,
                )
            )
    finally:
        kernel32.VirtualFreeEx(hproc, remote, 0, MEM_RELEASE)
        kernel32.CloseHandle(hproc)
    return icons


def _write(hproc, addr, obj) -> None:
    if not kernel32.WriteProcessMemory(hproc, addr, ctypes.byref(obj), ctypes.sizeof(obj), None):
        raise DesktopIconsError("ошибка записи в память Проводника")


def _read(hproc, addr, obj, size) -> None:
    if not kernel32.ReadProcessMemory(hproc, addr, ctypes.byref(obj), size, None):
        raise DesktopIconsError("ошибка чтения памяти Проводника")


def extensions_hidden() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        ) as k:
            return bool(winreg.QueryValueEx(k, "HideFileExt")[0])
    except OSError:
        return True


def possible_labels(entry: Path, hide_ext: bool) -> set[str]:
    """Как файл может быть подписан на рабочем столе."""
    name = entry.name
    labels = {name.lower()}
    stem, ext = os.path.splitext(name)
    if ext and (hide_ext or ext.lower() in (".lnk", ".url", ".pif")):
        labels.add(stem.lower())
    return labels


def names_in_zone(
    entries: list[Path],
    icons: list[Icon],
    zone: tuple[int, int, int, int],
    hide_ext: bool,
) -> set[str]:
    """Имена файлов рабочего стола, чьи значки стоят в зоне.

    Если одна подпись встречается у нескольких файлов (например, «Чертёж»
    при скрытых расширениях) и хоть один такой значок в зоне — защищаем все.
    """
    left, top, right, bottom = zone
    in_zone_labels = set()
    for ic in icons:
        cx, cy = ic.center
        if left <= cx <= right and top <= cy <= bottom:
            in_zone_labels.add(ic.label.lower())
    result = set()
    for e in entries:
        if possible_labels(e, hide_ext) & in_zone_labels:
            result.add(e.name)
    return result
