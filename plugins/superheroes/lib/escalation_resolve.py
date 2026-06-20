#!/usr/bin/env python3
"""Skill-facing wrapper for the escalation core (F5).

The skills call THIS (at a known ${CLAUDE_PLUGIN_ROOT}/lib path), never the core
directly — exactly as they call gate_write.py. In the consolidated one-plugin tree the
core (`escalation.py`) is a same-tree sibling, so this wrapper imports it directly (no
cross-plugin resolution, no subprocess) and owns the fail-closed degradation: on ANY core
error it falls back to the conservative posture (GATE / on-floor / refuse), never to a
silent proceed/allow. Output: JSON to stdout with a `degraded` flag so the skill can note
the fallback.
"""
import argparse
import json
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
import escalation  # noqa: E402  (same-tree sibling; no architect_lib, no subprocess)

_PLUGIN_ROOT = os.path.dirname(_LIB_DIR)               # the consolidated superheroes plugin root
_RUBRIC = ("rubric", "escalation-base.md")


def _say(detail):
    sys.stderr.write(detail + "\n")


def _safe(fn, conservative, **kw):
    """Call the core directly; on ANY error return the conservative fail-closed default.

    Returns (result, degraded): `degraded` is True iff the conservative fallback was used.
    """
    try:
        return fn(**kw), False
    except Exception:
        return conservative, True


def _band_roots(root):
    """Resolved plugin roots to anchor the canonical-path guard against: this (single)
    superheroes install, and — when --root is given (dogfood / in-repo) — the in-repo plugin
    dir. The guard refuses a safety-named file under ANY of them, so a like-named file in the
    target repo (outside these roots) is NOT falsely refused. The three per-plugin roots
    collapsed to the one merged plugin root when the band consolidated into one plugin.
    """
    roots = [_PLUGIN_ROOT]
    if root:
        cand = os.path.join(root, "plugins", "superheroes")
        if os.path.isdir(cand):
            roots.append(cand)
    return roots


def _resolve_rubric(root):
    """Resolve rubric/escalation-base.md under the plugin root directly (no architect_lib).
    In-repo (root/plugins/superheroes/...) wins; else the wrapper's own plugin root."""
    if root:
        cand = os.path.join(root, "plugins", "superheroes", *_RUBRIC)
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    cand = os.path.join(_PLUGIN_ROOT, *_RUBRIC)
    if os.path.isfile(cand):
        return os.path.abspath(cand)
    return None


def _build_parser():
    ap = argparse.ArgumentParser(description="escalation core wrapper (superheroes)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_root(parser):
        parser.add_argument("--root", default=None)

    r = sub.add_parser("route"); add_root(r)
    for f in ("--on-floor", "--ground-truth-locus", "--owner-weighable",
              "--reversible", "--confidence"):
        r.add_argument(f, required=True)
    c = sub.add_parser("classify"); add_root(c); c.add_argument("--action", required=True)
    g = sub.add_parser("guard"); add_root(g); g.add_argument("--path", required=True)
    rb = sub.add_parser("rubric"); add_root(rb)
    return ap


def _as_bool(s):
    if s in ("true", "True", "1", "yes"):
        return True
    if s in ("false", "False", "0", "no"):
        return False
    return s   # pass through so route() fail-closes on a bad value


def main(argv):
    args = _build_parser().parse_args(argv[1:])          # --root lives on each subparser

    if args.cmd == "rubric":
        path = _resolve_rubric(args.root)
        if path is None:
            _say("escalation-base.md not resolvable — the skill must apply the embedded "
                 "fail-closed posture (apply the floor; GATE anything owner-weighable).")
            sys.stdout.write(json.dumps({"path": None, "degraded": True}) + "\n")
            return 0
        sys.stdout.write(json.dumps({"path": path, "degraded": False}) + "\n")
        return 0

    if args.cmd == "route":
        axes = {"on_floor": _as_bool(args.on_floor),
                "ground_truth_locus": args.ground_truth_locus,
                "owner_weighable": _as_bool(args.owner_weighable),
                "reversible": _as_bool(args.reversible),
                "confidence": args.confidence}
        mode, degraded = _safe(escalation.route, "gate", axes=axes)  # fail closed -> gate
        if degraded:
            _say("escalation.route errored — applying the conservative fallback (GATE).")
        sys.stdout.write(json.dumps({"mode": mode, "degraded": degraded}) + "\n")
        return 0

    if args.cmd == "classify":
        on_floor, degraded = _safe(escalation.classify_floor, True, descriptor=args.action)
        sys.stdout.write(json.dumps({"on_floor": on_floor, "degraded": degraded}) + "\n")
        return 0

    if args.cmd == "guard":
        # conservative=True (treat as safety machinery -> refuse) on any core error.
        safety, degraded = _safe(escalation.is_safety_machinery, True,
                                 path=args.path, band_roots=_band_roots(args.root))
        allow = not safety   # fail closed: error -> safety True -> allow False (refuse)
        sys.stdout.write(json.dumps({"allow": allow, "degraded": degraded}) + "\n")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
