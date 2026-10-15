#!/usr/bin/env python3
"""Which of the project's risk areas a change touches (#1712): the one reader, no model call.

Stdlib and sibling lib modules only. A pure function of the stored risk areas and the given change
paths: it starts no process, opens no connection, dispatches no engine, and writes nothing. Risk
areas that are missing, empty, or cannot be read answer ``not-set`` with a reason and an empty
``touched`` — never a "touches none" that the stored areas did not earn."""
import argparse
import fnmatch
import json
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import core_md  # noqa: E402

REASON_MISSING = "missing"
REASON_EMPTY = "empty"
REASON_UNREADABLE = "unreadable"


def normalize_change_path(path):
    """A change path in the one form stored patterns match: ``/`` separators, no leading ``./``,
    no repeated ``/``. None for a non-string, an empty or absolute path, or one with a ``..``
    segment — such a path never matches."""
    if not isinstance(path, str):
        return None
    text = path.replace("\\", "/")
    if text.startswith("/"):
        return None
    while "//" in text:
        text = text.replace("//", "/")
    while text.startswith("./"):
        text = text[2:]
    if not text or text == ".":
        return None
    if ".." in text.split("/"):
        return None
    return text


def pattern_matches(pattern, path):
    """Case-sensitive cover test: ``path`` is covered by ``pattern`` when it equals it, lies beneath
    it as a folder, or matches it as a glob (``*`` crosses ``/``), and a glob that names folders
    also covers what is beneath them."""
    # axis: a normalised path that falls under a stored pattern is reported touched — see bite-proof record wo_a_1712_risk-areas
    return (path == pattern
            or path.startswith(pattern + "/")
            or fnmatch.fnmatchcase(path, pattern)
            or fnmatch.fnmatchcase(path, pattern + "/*"))


def _result(risk_areas, reason=None, detail=None, areas=None, touched_areas=None,
            unmatchable=None):
    return {
        "riskAreas": risk_areas,
        "reason": reason,
        "detail": detail,
        "areas": areas if areas is not None else [],
        "touched": touched_areas if touched_areas is not None else [],
        "unmatchable": unmatchable if unmatchable is not None else [],
    }


def touched(cwd, paths, root=None):
    """The risk areas that ``paths`` touch. ``riskAreas`` is ``set`` only when core.md holds a
    valid, non-empty list; every other state is ``not-set`` with ``reason`` ``missing``,
    ``empty`` or ``unreadable`` and ``touched`` empty."""
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        return _result("not-set", REASON_UNREADABLE, "paths-not-a-list-of-strings")
    stored = core_md.read_risk_areas(cwd, root=root)
    reason = stored.get("reason")
    # axis: an unreadable or malformed store is never reported as set or as touching none — see bite-proof record wo_a_1712_risk-areas
    if reason in (core_md.RISK_AREAS_REASON_MALFORMED, core_md.RISK_AREAS_REASON_UNREADABLE):
        detail = reason if not stored.get("detail") else "%s: %s" % (reason, stored["detail"])
        return _result("not-set", REASON_UNREADABLE, detail)
    # axis: a missing store (no core.md, or no riskAreas key) is not-set, never set-and-empty — see bite-proof record wo_a_1712_risk-areas
    if reason == "core-md-absent" or not stored.get("declared"):
        return _result("not-set", REASON_MISSING, reason)
    areas = stored.get("areas")
    if not isinstance(areas, list):
        return _result("not-set", REASON_UNREADABLE, "risk-areas-not-a-list")
    # axis: an empty list is not-set, never "touches none" — see bite-proof record wo_a_1712_risk-areas
    if not areas:
        return _result("not-set", REASON_EMPTY)

    normalised = []
    unmatchable = []
    for path in paths:
        norm = normalize_change_path(path)
        if norm is None:
            unmatchable.append(path)
        elif norm not in normalised:
            normalised.append(norm)
    hits = []
    for area in areas:
        matched = [p for p in normalised
                   if any(pattern_matches(pattern, p) for pattern in area["covers"])]
        if matched:
            hits.append({"area": area, "matched": matched})
    return _result("set", None, None, areas, hits, unmatchable)


def _read_paths_file(spec, nul=False):
    if spec == "-":
        text = sys.stdin.read()
    else:
        with open(spec, encoding="utf-8", newline="") as fh:
            text = fh.read()
    # NUL-delimited input is taken byte for byte (git ls-files -z): no quoting, no line splitting.
    parts = text.split("\0") if nul else text.splitlines()
    return [part for part in parts if part.strip()]


def main(argv):
    ap = argparse.ArgumentParser(prog="risk_areas")
    sub = ap.add_subparsers(dest="cmd", required=True)
    tp = sub.add_parser("touched")
    tp.add_argument("--cwd", default=".")
    tp.add_argument("--root", default=None)
    tp.add_argument("--path", action="append", default=[])
    tp.add_argument("--paths-file", default=None)
    tp.add_argument("--nul", action="store_true",
                    help="the paths file is NUL-delimited (git ls-files -z)")
    args = ap.parse_args(argv)

    paths = list(args.path)
    if args.paths_file is not None:
        try:
            paths.extend(_read_paths_file(args.paths_file, nul=args.nul))
        except (OSError, UnicodeDecodeError) as exc:
            sys.stdout.write(json.dumps(
                {"error": "paths-file-unreadable", "detail": "%s: %s" % (type(exc).__name__, exc)},
                indent=2) + "\n")
            return 2
    sys.stdout.write(json.dumps(touched(args.cwd, paths, root=args.root), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
