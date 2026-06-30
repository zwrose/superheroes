#!/usr/bin/env python3
# plugins/superheroes/lib/hero_setup.py
"""Per-hero setup state for superheroes:configure (#121 Part C). The route stays the
mandatory/optional split — review-crew missing routes to `fix` (configure_route); OPTIONAL
light-layer heroes never affect routing. This module is what the view tune-menu uses to OFFER a
skipped optional hero (FR-6), minus any the owner explicitly DECLINED so the offer appears once and
never nags. The decline list is machine-local in the project store; `offerable` is a pure read."""
import argparse
import json
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import core_md          # noqa: E402  (sibling)
import mode_registry    # noqa: E402  (sibling)
import store_core       # noqa: E402  (sibling)

# The light-layer heroes (mirrors core_md._HEROES). review-crew is MANDATORY — its absence is an
# incomplete set-up that configure_route sends to `fix`, so it is never an "offerable" optional.
HEROES = core_md._HEROES
MANDATORY = frozenset({"review-crew"})


def _declined_path(cwd, root=None):
    return os.path.join(mode_registry.project_store_dir(cwd, root), "declined-heroes.json")


def read_declined(cwd, root=None):
    """The set of heroes the owner explicitly declined. Fail-open: an unreadable/corrupt marker
    reads as no declines (the offer simply re-appears) rather than crashing the menu."""
    try:
        with open(_declined_path(cwd, root), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return set()
    if not isinstance(data, list):
        return set()
    # Keep only string elements: a non-string/non-hashable element (e.g. a dict) would make
    # set(data) raise TypeError and escape the fail-open contract (/code-review #4).
    return {x for x in data if isinstance(x, str)}


def mark_declined(cwd, hero, root=None):
    """Record that the owner declined `hero` (idempotent). Best-effort: an unknown hero is ignored;
    an unwritable store leaves the set unchanged (the offer reappears next run) — never raises."""
    if hero not in HEROES:
        return {"declined": sorted(read_declined(cwd, root))}
    current = read_declined(cwd, root)
    if hero in current:
        return {"declined": sorted(current)}
    if mode_registry.ensure_project_store(cwd, root) is None:
        return {"declined": sorted(current), "deferred": True}
    current.add(hero)
    try:
        store_core.atomic_write(_declined_path(cwd, root),
                                json.dumps(sorted(current), indent=2) + "\n")
    except OSError:
        return {"declined": sorted(read_declined(cwd, root)), "deferred": True}
    return {"declined": sorted(current)}


def _is_set_up(cwd, hero, root=None):
    """A hero is set up iff its light-layer file exists AND carries real content — an empty
    placeholder layer (an interrupted set-up) is NOT set up (/code-review #12). Reuses core_md's
    canonical layer-path + emptiness helpers rather than recomputing them (/code-review #13)."""
    return not core_md._layer_is_empty(core_md._layer_path(cwd, hero, root))


def offerable(cwd, root=None):
    """OPTIONAL light-layer heroes that are NOT set up and NOT declined — the ones the view
    tune-menu offers to set up (FR-6). The mandatory hero (review-crew) is excluded: when it is
    missing the route sends the project to `fix`, not the view, so it is never offered here."""
    dec = read_declined(cwd, root)
    return [h for h in HEROES
            if h not in MANDATORY and h not in dec and not _is_set_up(cwd, h, root)]


def main(argv):
    ap = argparse.ArgumentParser(prog="hero_setup")
    sub = ap.add_subparsers(dest="cmd", required=True)
    op = sub.add_parser("offerable")  # the optional heroes the tune-menu may offer
    op.add_argument("--cwd", default=".")
    op.add_argument("--root", default=None)
    dp = sub.add_parser("decline")  # record an explicit owner decline (suppresses re-offer)
    dp.add_argument("--cwd", default=".")
    dp.add_argument("--root", default=None)
    dp.add_argument("--hero", choices=HEROES, required=True)
    args = ap.parse_args(argv)
    try:
        if args.cmd == "offerable":
            out = {"offerable": offerable(args.cwd, args.root)}
        else:
            out = mark_declined(args.cwd, args.hero, args.root)
    except Exception as exc:  # fail-open like the other lib CLIs — never crash a consumer
        out = {"error": str(exc)}
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
