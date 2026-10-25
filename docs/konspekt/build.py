"""Собрать konspekt.html из konspekt.src.html: подставить цикл-схему «петли проектировщика».

    python build.py   →  konspekt.html (дальше render.py из скилла alpha-konspekt)
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = Path.home() / ".claude" / "skills" / "alpha-konspekt" / "scripts"
sys.path.insert(0, str(SKILL))

from cycle import cycle_svg  # noqa: E402

LIGHTNING = "path:M13 2L4 14h7l-1 8 9-12h-7z"
FULL = "path:M3 5h18v14H3zM3 9h18M7 13h3M7 16h6M14 13h3"
TRASH = "path:M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6"

loop = cycle_svg(
    [
        ("Настроил", "Порядок. Красота", "compass"),
        ("Пользуюсь", "Доволен собой", "check"),
        ("Аврал", "Пятница, 18:00", LIGHTNING),
        ("Хаос", "Потом разберусь", "bricks"),
        ("Места нет", "Диск C: красный", FULL),
        ("Снёс всё", "И заново", TRASH),
    ],
    size=640,
    radius=0.37,
)

src = (HERE / "konspekt.src.html").read_text(encoding="utf-8")
(HERE / "konspekt.html").write_text(src.replace("{{LOOP}}", loop), encoding="utf-8")
print(HERE / "konspekt.html")
