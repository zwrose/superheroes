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
        why.append("touches-risk-area: %s (%s)" % (hit["name"], ", ".join(hit["matched"])))
    # axis: risk areas that are not set (missing, empty or unreadable) get the floor full — see bite-proof record wo_a_1795_lane-call
    if state != "set":
        floor = FLOOR_FULL
        detail = "" if not got["detail"] else ": %s" % got["detail"]
        why.append("risk-unclear-not-set: the project's risk areas are not set (%s%s)" % (got["reason"], detail))
    # axis: a path no area can be matched against gets the floor full — see bite-proof record wo_a_1795_lane-call
    if unmatchable:
        floor = FLOOR_FULL
        why.append("risk-unclear-unmatchable: %d changed path(s) cannot be matched against an area (%s)"
                   % (len(unmatchable), ", ".join(repr(p) for p in unmatchable)))
    # axis: a change with no changed paths gets the floor full — see bite-proof record wo_a_1795_lane-call
    if isinstance(paths, list) and not paths:
        floor = FLOOR_FULL
        why.append("risk-unclear-no-paths: no changed paths were given")
    if floor is None:
        why.append("no-floor: the risk is clear and no risk area is touched")

    taken = False
    if proposed is None:
        lane = FLOOR_FULL
        why.append("no-proposal-defaults-full: no lane was proposed, so the lane is full")
    elif rank(proposed) < 0:
        lane = floor or FLOOR_FULL
        why.append("proposal-invalid: %r is not one of %s, so the lane is %s"
                   % (proposed, ", ".join(LANES), lane))
    # axis: a proposal below the floor never lowers the lane — see bite-proof record wo_a_1795_lane-call
    elif floor is not None and rank(proposed) < rank(floor):
        lane = floor
        why.append("proposal-below-floor: %s is below the floor %s, so the lane is %s" % (proposed, floor, lane))
    else:
        lane, taken = proposed, True
        why.append("proposal-taken: %s is at or above the floor" % proposed)

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
