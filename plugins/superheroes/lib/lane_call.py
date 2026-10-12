#!/usr/bin/env python3
"""The lane floor: the one place a change's lane is held at or above its risk floor, no model call.

Stdlib and sibling lib modules only. A pure function of the stored risk areas, the given change
paths and an optional proposed lane: it starts no process, opens no connection, dispatches no
engine, and writes nothing. Every lane a change gets is at or above one floor, computed here. The
floor comes only from ``risk_areas.touched`` (never re-match a path against a pattern anywhere else).
A change whose risk is clear and that touches no risk area has no floor. Every other change has the
floor ``full``: one that touches a risk area, and one whose risk is unclear. Risk is unclear when the
risk areas are ``not-set`` for any reason, when the ``unmatchable`` list is not empty, or when no
changed paths are given. A proposed lane is taken only when it is at or above the floor; below it,
the floor wins. With no proposal the lane is ``full``.

CLI:
  lane_call.py call [--cwd .] [--root R] [--path P ...] [--paths-file F [--nul]] [--proposed LANE]
prints the result as JSON and exits 0; an unreadable paths file prints an error object and exits 2."""
import argparse
import json
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import risk_areas  # noqa: E402

LANES = ("micro", "light", "full")
FLOOR_FULL = "full"
WHY_SAMPLE = 3

# The reason-line tokens: each reason line this module authors starts with one of them. Every other module
# that reads, selects or bounds reason lines imports these (and the helpers below); none repeats a literal.
WHY_TOUCHES = "touches-risk-area:"
WHY_NOT_SET = "risk-unclear-not-set:"
WHY_UNMATCHABLE = "risk-unclear-unmatchable:"
WHY_NO_PATHS = "risk-unclear-no-paths:"
WHY_NO_FLOOR = "no-floor:"
WHY_NO_PROPOSAL = "no-proposal-defaults-full:"
WHY_PROPOSAL_INVALID = "proposal-invalid:"
WHY_PROPOSAL_BELOW = "proposal-below-floor:"
WHY_PROPOSAL_TAKEN = "proposal-taken:"
_AGAINST_AREA = " against an area"


def _sample(items, render=str):
    """The why-line form of a list: all of it when short, else the count and the first few."""
    shown = ", ".join(render(i) for i in items[:WHY_SAMPLE])
    return shown if len(items) <= WHY_SAMPLE else "%d paths: %s, ..." % (len(items), shown)


def is_touches_line(line):
    """Whether ``line`` is a touches-risk-area reason line."""
    return isinstance(line, str) and line.startswith(WHY_TOUCHES)


def touches_omitted_line(count):
    """The line that stands for ``count`` touches-risk-area lines cut from the reasons."""
    return "%d more %s lines omitted" % (count, WHY_TOUCHES.rstrip(":"))


def why_line_paths_stripped(line, names=()):
    """``line`` without its sample paths: a touches-risk-area line keeps the area name (one of ``names``
    when its prefix matches — the longest such name, so ``Payments (refunds)`` is not cut to ``Payments`` —
    else the text before the first `` (``); an unmatchable line keeps its count and loses the sample; any
    other line is returned unchanged."""
    if line.startswith(WHY_TOUCHES):
        name = max((n for n in names if line.startswith("%s %s (" % (WHY_TOUCHES, n))), key=len, default=None)
        return "%s %s" % (WHY_TOUCHES, name) if name is not None else line.split(" (", 1)[0]
    if line.startswith(WHY_UNMATCHABLE) and _AGAINST_AREA + " (" in line:
        return line.split(_AGAINST_AREA + " (", 1)[0] + _AGAINST_AREA
    return line


def rank(lane):
    """The lane's rank (micro < light < full); an unknown lane value ranks below every lane."""
    return LANES.index(lane) if isinstance(lane, str) and lane in LANES else -1


def call(cwd, paths, proposed=None, root=None):
    """The floor, the lane and the reasons for ``paths``. Never raises: a ``paths`` that is not a
    list of strings goes straight to ``risk_areas.touched``, which answers ``not-set``."""
    got = risk_areas.touched(cwd, paths, root=root)
    state, unmatchable = got["riskAreas"], got["unmatchable"]
    hits = [{"name": hit["area"]["name"], "matched": list(hit["matched"])} for hit in got["touched"]]
    floor, why = None, []

    # axis: a change that touches a risk area gets the floor full — see bite-proof record wo_a_1795_lane-call
    for hit in hits:
        floor = FLOOR_FULL
        why.append("%s %s (%s)" % (WHY_TOUCHES, hit["name"], _sample(hit["matched"])))
    # axis: risk areas that are not set (missing, empty or unreadable) get the floor full — see bite-proof record wo_a_1795_lane-call
    if state != "set":
        floor = FLOOR_FULL
        detail = "" if not got["detail"] else ": %s" % got["detail"]
        why.append("%s the project's risk areas are not set (%s%s)" % (WHY_NOT_SET, got["reason"], detail))
    # axis: a path no area can be matched against gets the floor full — see bite-proof record wo_a_1795_lane-call
    if unmatchable:
        floor = FLOOR_FULL
        why.append("%s %d changed path(s) cannot be matched%s (%s)"
                   % (WHY_UNMATCHABLE, len(unmatchable), _AGAINST_AREA, _sample(unmatchable, repr)))
    # axis: a change with no changed paths gets the floor full — see bite-proof record wo_a_1795_lane-call
    if isinstance(paths, list) and not paths:
        floor = FLOOR_FULL
        why.append(WHY_NO_PATHS + " no changed paths were given")
    if floor is None:
        why.append(WHY_NO_FLOOR + " the risk is clear and no risk area is touched")

    taken = False
    if proposed is None:
        lane = FLOOR_FULL
        why.append(WHY_NO_PROPOSAL + " no lane was proposed, so the lane is full")
    elif rank(proposed) < 0:
        lane = floor or FLOOR_FULL
        why.append("%s %r is not one of %s, so the lane is %s"
                   % (WHY_PROPOSAL_INVALID, proposed, ", ".join(LANES), lane))
    # axis: a proposal below the floor never lowers the lane — see bite-proof record wo_a_1795_lane-call
    elif floor is not None and rank(proposed) < rank(floor):
        lane = floor
        why.append("%s %s is below the floor %s, so the lane is %s" % (WHY_PROPOSAL_BELOW, proposed, floor, lane))
    else:
        lane, taken = proposed, True
        why.append("%s %s is at or above the floor" % (WHY_PROPOSAL_TAKEN, proposed))

    return {
        "floor": floor,
        "lane": lane,
        "why": why,
        "riskAreas": {"state": state, "reason": got["reason"], "detail": got["detail"]},
        "touched": hits,
        "unmatchable": unmatchable,
        "proposed": proposed,
        "proposalTaken": taken,
    }


def unavailable(why, proposed=None):
    """The fail-closed basis for a change whose risk areas or paths were never read: the same keys as
    ``call``, floor and lane ``full``, nothing read. Pure: it reads no store and starts no process."""
    reasons = [why]
    if proposed is not None and rank(proposed) < 0:
        lane_names = ", ".join(LANES)
        reasons.append("%s %r is not one of %s, so the lane is %s" % (WHY_PROPOSAL_INVALID, proposed, lane_names, FLOOR_FULL))
    elif proposed is not None and rank(proposed) < rank(FLOOR_FULL):
        reasons.append("%s %s is below the floor %s, so the lane is %s"
                       % (WHY_PROPOSAL_BELOW, proposed, FLOOR_FULL, FLOOR_FULL))
    return {
        # axis: a basis that was never read gets the floor full — see bite-proof record wo_c_1795_lane-basis
        "floor": FLOOR_FULL,
        "lane": FLOOR_FULL,
        "why": reasons,
        "riskAreas": {"state": "not-set", "reason": "unreadable", "detail": "not-read"},
        "touched": [],
        "unmatchable": [],
        "proposed": proposed,
        "proposalTaken": proposed == FLOOR_FULL,
    }


def main(argv):
    ap = argparse.ArgumentParser(prog="lane_call")
    sub = ap.add_subparsers(dest="cmd", required=True)
    cp = sub.add_parser("call")
    cp.add_argument("--cwd", default=".")
    cp.add_argument("--root", default=None)
    cp.add_argument("--path", action="append", default=[])
    cp.add_argument("--paths-file", default=None)
    cp.add_argument("--nul", action="store_true",
                    help="the paths file is NUL-delimited (git ls-files -z)")
    cp.add_argument("--proposed", default=None)
    args = ap.parse_args(argv)

    paths = list(args.path)
    if args.paths_file is not None:
        try:
            paths.extend(risk_areas._read_paths_file(args.paths_file, nul=args.nul))
        except (OSError, UnicodeDecodeError) as exc:
            sys.stdout.write(json.dumps(
                {"error": "paths-file-unreadable", "detail": "%s: %s" % (type(exc).__name__, exc)},
                indent=2) + "\n")
            return 2
    sys.stdout.write(json.dumps(
        call(args.cwd, paths, proposed=args.proposed, root=args.root), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
