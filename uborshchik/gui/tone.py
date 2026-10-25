"""Подписи кнопок, которые меняются вместе с тоном общения без перезапуска."""

from __future__ import annotations

import weakref

from shiboken6 import isValid

from .. import phrases

_bound: list[tuple[weakref.ref, str, str]] = []


def bind(widget, key: str, prefix: str = ""):
    """Подписать кнопку/пункт меню ключом из phrases.BUTTONS и запомнить для смены тона."""
    widget.setText(prefix + phrases.btn(key))
    _bound.append((weakref.ref(widget), key, prefix))
    return widget


def retone() -> None:
    alive = []
    for ref, key, prefix in _bound:
        w = ref()
        if w is not None and isValid(w):
            w.setText(prefix + phrases.btn(key))
            alive.append((ref, key, prefix))
    _bound[:] = alive
