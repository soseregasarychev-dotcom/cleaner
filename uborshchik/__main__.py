"""Запуск: `python -m uborshchik [--tray | --dry-run]`."""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser(prog="uborshchik")
    ap.add_argument("--tray", action="store_true", help="запуститься свёрнутым в трей")
    ap.add_argument("--dry-run", action="store_true", help="показать план в консоли и выйти")
    args = ap.parse_args()

    if args.dry_run:
        return dry_run()

    from .gui.app import run

    return run(start_hidden=args.tray)


def dry_run() -> int:
    from . import paths
    from .config import Settings
    from .desktop_icons import set_dpi_aware
    from .planner import Locations, build_plan
    from .util import human_size

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    set_dpi_aware()
    s = Settings.load(paths.app_data_dir() / "settings.json")
    loc = Locations.system(s)
    plan = build_plan(s, loc, progress=lambda m: print("…", m))
    print(f"\nАрхив: {plan.day_dir}")
    for w in plan.warnings:
        print("!", w)
    if plan.zone_kept:
        print(f"В зоне покоя ({len(plan.zone_kept)}): " + ", ".join(plan.zone_kept))
    for cat, acts in plan.by_category().items():
        size = sum(a.size for a in acts)
        print(f"\n== {cat}: {len(acts)} шт., {human_size(size)}")
        for a in sorted(acts, key=lambda a: -a.size)[:15]:
            print(f"   {human_size(a.size):>10}  {a.label}  {a.note}")
        if len(acts) > 15:
            print(f"   … и ещё {len(acts) - 15}")
    print(f"\nИтого: {human_size(plan.total_size)}. Ничего не изменено (--dry-run).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
