"""Безопасные операции с файлами.

Главные правила:
- любая операция сначала проходит через Guard: путь обязан лежать внутри
  разрешённого места и не попадать в защищённое (облако, Документы, Windows…);
- ссылки (junction/symlink) никогда не раскрываются: удаляется сама ссылка,
  а не то, на что она указывает;
- занятые файлы не ломают уборку — они просто пропускаются.
"""

from __future__ import annotations

import fnmatch
import os
import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path

FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_SYSTEM = 0x4
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class GuardError(Exception):
    """Попытка тронуть путь вне разрешённых мест."""


def _norm(p: Path | str) -> str:
    return os.path.normcase(os.path.abspath(str(p))).rstrip("\\/")


def is_within(path: Path | str, root: Path | str) -> bool:
    p, r = _norm(path), _norm(root)
    return p == r or p.startswith(r + os.sep)


class Guard:
    def __init__(self, allowed: list[Path], protected: list[Path]):
        self.allowed = [Path(a) for a in allowed]
        self.protected = [Path(p) for p in protected]

    def check(self, path: Path) -> None:
        for prot in self.protected:
            if is_within(path, prot) or is_within(prot, path):
                raise GuardError(f"Защищённое место: {path}")
        for root in self.allowed:
            # Сам корень (рабочий стол целиком) трогать нельзя — только содержимое
            if is_within(path, root) and _norm(path) != _norm(root):
                return
        raise GuardError(f"Вне разрешённых мест: {path}")


def matches_any(name: str, patterns: list[str]) -> bool:
    # Сначала точное имя: в именах бывают [ ] — для масок это спецсимволы
    low = name.lower()
    return any(
        low == p.lower() or fnmatch.fnmatchcase(low, p.lower()) for p in patterns if p.strip()
    )


def attrs(path: Path) -> int:
    try:
        return getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return 0


def is_reparse(path: Path) -> bool:
    return bool(attrs(path) & FILE_ATTRIBUTE_REPARSE_POINT)


def is_system(path: Path) -> bool:
    return bool(attrs(path) & FILE_ATTRIBUTE_SYSTEM)


def item_time(path: Path) -> float:
    """Возраст файла считаем по самой поздней из дат «изменён» и «создан».

    Распакованные установщики сохраняют старую дату изменения, поэтому
    одной mtime мало.
    """
    try:
        st = os.lstat(path)
        return max(st.st_mtime, st.st_ctime)
    except OSError:
        return 0.0


def tree_size(path: Path) -> tuple[int, int]:
    """(байт, файлов) без перехода по ссылкам."""
    try:
        st = os.lstat(path)
    except OSError:
        return 0, 0
    if is_reparse(path):
        return 0, 0
    if not stat.S_ISDIR(st.st_mode):
        return st.st_size, 1
    total, count = 0, 0
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
                        else:
                            total += st.st_size
                            count += 1
                    except OSError:
                        continue
        except OSError:
            continue
    return total, count


@dataclass
class OpResult:
    freed: int = 0
    done: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def add(self, other: "OpResult") -> None:
        self.freed += other.freed
        self.done += other.done
        self.skipped += other.skipped
        self.errors.extend(other.errors)


def _unlink(path: str) -> None:
    try:
        os.unlink(path)
    except PermissionError:
        # Снимаем «только чтение» и пробуем ещё раз
        os.chmod(path, stat.S_IWRITE)
        os.unlink(path)


def _remove_link(path: Path) -> None:
    # Junction и symlink на папку удаляются через rmdir, на файл — через unlink
    try:
        os.rmdir(path)
    except OSError:
        os.unlink(path)


def delete_path(path: Path, guard: Guard) -> OpResult:
    """Удалить файл или папку насовсем (ссылки — только саму ссылку)."""
    guard.check(path)
    res = OpResult()
    if is_reparse(path):
        try:
            _remove_link(path)
            res.done += 1
        except OSError as e:
            res.skipped += 1
            res.errors.append(f"{path}: {e}")
        return res
    if path.is_file():
        try:
            size = os.lstat(path).st_size
            _unlink(str(path))
            res.freed += size
            res.done += 1
        except OSError as e:
            res.skipped += 1
            res.errors.append(f"{path}: {e}")
        return res
    if path.is_dir():
        for root, dirs, files in os.walk(path, topdown=False, followlinks=False):
            for name in files:
                fp = os.path.join(root, name)
                try:
                    size = os.lstat(fp).st_size
                    _unlink(fp)
                    res.freed += size
                    res.done += 1
                except OSError as e:
                    res.skipped += 1
                    res.errors.append(f"{fp}: {e}")
            for name in dirs:
                dp = Path(root) / name
                try:
                    if is_reparse(dp):
                        _remove_link(dp)
                    else:
                        os.rmdir(dp)
                except OSError:
                    pass  # не пустая из-за занятых файлов — оставляем
        try:
            os.rmdir(path)
        except OSError:
            pass
    return res


def delete_old_in_dir(path: Path, cutoff: float, guard: Guard) -> OpResult:
    """Удалить внутри папки файлы старше cutoff и опустевшие старые подпапки."""
    guard.check(path)
    res = OpResult()
    if is_reparse(path):
        return res
    if path.is_file():
        if item_time(path) < cutoff:
            return delete_path(path, guard)
        return res
    for root, dirs, files in os.walk(path, topdown=False, followlinks=False):
        for name in files:
            fp = os.path.join(root, name)
            if item_time(Path(fp)) >= cutoff:
                continue
            try:
                size = os.lstat(fp).st_size
                _unlink(fp)
                res.freed += size
                res.done += 1
            except OSError:
                res.skipped += 1
        for name in dirs:
            dp = Path(root) / name
            if is_reparse(dp):
                continue
            try:
                if item_time(dp) < cutoff and not any(dp.iterdir()):
                    os.rmdir(dp)
            except OSError:
                pass
    try:
        if item_time(path) < cutoff and not any(path.iterdir()):
            os.rmdir(path)
    except OSError:
        pass
    return res


def unique_target(dst_dir: Path, name: str) -> Path:
    target = dst_dir / name
    if not os.path.lexists(target):
        return target
    p = Path(name)
    stem, suffix = (p.stem, p.suffix) if p.suffix and len(p.suffix) <= 10 else (name, "")
    n = 2
    while True:
        cand = dst_dir / f"{stem} ({n}){suffix}"
        if not os.path.lexists(cand):
            return cand
        n += 1


def move_path(src: Path, dst_dir: Path, guard: Guard) -> tuple[Path | None, str | None]:
    """Перенести файл/папку в dst_dir. Возвращает (куда, ошибка)."""
    guard.check(src)
    guard.check(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    target = unique_target(dst_dir, src.name)
    try:
        os.rename(src, target)
        return target, None
    except OSError as e:
        # Другой диск — копируем и удаляем; на том же диске это «файл занят»
        if getattr(e, "winerror", None) == 17:  # ERROR_NOT_SAME_DEVICE
            try:
                shutil.move(str(src), str(target))
                return target, None
            except OSError as e2:
                return None, str(e2)
        return None, _human_error(e)


def _human_error(e: OSError) -> str:
    code = getattr(e, "winerror", None)
    if code in (32, 33):
        return "файл открыт в другой программе"
    if code == 5:
        return "нет доступа (возможно, открыт в программе)"
    return str(e)
