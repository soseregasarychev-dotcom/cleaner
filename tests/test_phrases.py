import re

import pytest

from uborshchik import phrases

SAMPLE = dict(
    size="1,5 ГБ", moved="3 объекта", days=90, left="2 дня", summary="в архив: 3 шт.",
    when="5 ноября в 09:00", date="30 июля", more="",
)


@pytest.fixture(autouse=True)
def reset():
    yield
    phrases.configure(True, "")


@pytest.mark.parametrize("key", sorted(phrases.FUN))
def test_every_fun_phrase_formats(key):
    phrases.configure(True, "")
    for _ in range(30):  # перебрать варианты
        text = phrases.pick(key, **SAMPLE)
        assert "{" not in text and text[:1] == text[:1].upper()


@pytest.mark.parametrize("key", sorted(phrases.PLAIN))
def test_plain_has_no_jokes(key):
    phrases.configure(False)
    text = phrases.pick(key, **SAMPLE)
    assert text == phrases.PLAIN[key].format(**SAMPLE)[:1].upper() + phrases.PLAIN[key].format(**SAMPLE)[1:]


def test_every_fun_key_has_plain_version():
    assert set(phrases.FUN) <= set(phrases.PLAIN)


def test_fixed_address_and_case():
    phrases.configure(True, "Господин ГИП")
    for _ in range(20):
        t = phrases.pick("greeting")
        # С большой в начале, с маленькой в середине — «ГИП» не ломается
        assert "Господин ГИП" in t or "господин ГИП" in t


def test_no_immediate_repeat():
    phrases.configure(True, "")
    seq = [phrases.pick("done_title") for _ in range(20)]
    assert all(a != b for a, b in zip(seq, seq[1:]))


def test_buttons_switch():
    phrases.configure(True)
    assert phrases.btn("clean_now") == "Вызвать бригаду"
    phrases.configure(False)
    assert phrases.btn("clean_now") == "Убрать сейчас"
    assert all(re.search(r"\S", f) and re.search(r"\S", p) for f, p in phrases.BUTTONS.values())
