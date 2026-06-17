#!/usr/bin/env python3
"""Deterministic core of the superheroes escalation rubric (F5).

Paired with the prose rubric `the-architect/rubric/escalation-base.md` exactly as
`review-base.md` is paired with `loop_state.py`: the model supplies the fuzzy axis
judgments, this module owns the deterministic floor + routing table + the fixer
file-scope guard. See docs/superpowers/specs/2026-06-16-escalation-rubric-design.md.
"""
import argparse
import json
import os
import re
import sys

_MODE_GATE = "gate"
_MODE_NOTIFY = "notify"
_MODE_PROCEED = "proceed"

_LOCUS = ("agent", "owner")
_CONFIDENCE = ("high", "low")


def route(axes):
    """Pure routing table: axis judgments -> 'gate' | 'notify' | 'proceed'.

    Fails CLOSED (-> 'gate') on anything missing, null, or ill-formed — the same
    fail-safe-on-malformed-input posture loop_state.py uses. `on_floor` short-circuits
    to 'gate' unconditionally (the floor is step 1, checked before any other axis).
    """
    if not isinstance(axes, dict):
        return _MODE_GATE
    # 1. Hard floor — unconditional, regardless of every other axis.
    if axes.get("on_floor") is True:
        return _MODE_GATE
    if axes.get("on_floor") is not False:        # must be an explicit bool
        return _MODE_GATE
    locus = axes.get("ground_truth_locus")
    if locus not in _LOCUS:
        return _MODE_GATE
    # 2. Ground truth the agent can verify -> verify-and-proceed (asking is friction).
    if locus == "agent":
        return _MODE_PROCEED
    # locus == "owner": the remaining axes must be well-formed, else fail closed.
    owner_weighable = axes.get("owner_weighable")
    reversible = axes.get("reversible")
    confidence = axes.get("confidence")
    if not isinstance(owner_weighable, bool) or not isinstance(reversible, bool) \
            or confidence not in _CONFIDENCE:
        return _MODE_GATE
    # 3a. Engineering-internal (no owner-weighable trade-off) -> record-only proceed.
    if not owner_weighable:
        return _MODE_PROCEED
    # 3b. Owner-weighable AND (hard to reverse OR can't be safely defaulted = low conf) -> gate.
    if not reversible or confidence == "low":
        return _MODE_GATE
    # 3c. Owner-relevant but reversible and high-confidence -> act-then-notify.
    return _MODE_NOTIFY


# Recognizable on-floor action descriptors. COARSE AND CONSERVATIVE by design
# (§4 bound-1: unsure -> the skill treats as on-floor; this catches the clearly
# recognizable ones). The model classifies anything not matched here.
FLOOR_PATTERNS = [
    ("force-push", re.compile(r"\bgit\s+push\b.*(--force|-f\b|force-with-lease)", re.I)),
    ("push",       re.compile(r"\bgit\s+push\b", re.I)),
    ("merge",      re.compile(r"\bgit\s+(merge|rebase)\b", re.I)),
    ("deploy",     re.compile(r"\b(deploy|kubectl\s+apply|terraform\s+apply|"
                              r"\w+\s+deploy(\s|$)|--prod\b)", re.I)),
    ("destructive-data", re.compile(r"\b(DROP\s+(TABLE|COLUMN|DATABASE|INDEX)|"
                                    r"DELETE\s+FROM|TRUNCATE)\b", re.I)),
    ("delete",     re.compile(r"\brm\s+-[a-z]*r[a-z]*f|\brm\s+-rf\b", re.I)),
    ("spend",      re.compile(r"\b(paid|billing|charge|stripe|purchase|invoice)\b", re.I)),
    ("egress",     re.compile(r"\b(external|outbound|webhook|exfiltrat\w*|"
                              r"upload\s+to|POST\b.*\bexternal)\b", re.I)),
]


def classify_floor(descriptor):
    """True iff `descriptor` matches a recognizable hard-floor action class.

    Deterministic + coarse. A False here does NOT mean off-floor — it means
    'not recognized by the classifier'; the skill's conservative default and the
    F3 action-boundary enforcer handle the rest (§4 bound-1).
    """
    if not isinstance(descriptor, str):
        return False
    for _name, pat in FLOOR_PATTERNS:
        if pat.search(descriptor):
            return True
    return False


# The safety-machinery set (§4 bound-2). INCLUSION CRITERION (the source of truth): any module
# whose edit could disable a floor / gate / halt / escalation guarantee. Includes
# escalation_resolve.py — the review-crew-local wrapper that OWNS the fail-closed verdict
# (review caught this; without it a fixer could neuter the guard). Read-only proposers
# (decisions.py) are excluded; identifiers.py was run through the criterion and EXCLUDED (it
# mints slugs but can't itself disable a guarantee — its misuse surfaces via gate_write's
# canonical guard, which IS pinned). review-base.md is included because editing severity
# reclassifies what counts as a blocker (a gate input).
SAFETY_MACHINERY = (
    "escalation.py",
    "escalation_resolve.py",
    "loop_state.py",
    "circuit_breaker.py",
    "gate_write.py",
    "architect_lib.py",
    "definition_doc.py",
    "escalation-base.md",
    "review-base.md",
)


def is_safety_machinery(path, band_roots):
    """True iff `path` is a safety-machinery file — KEYED BY RESOLVED CANONICAL PATH, not bare
    basename (§4: the set spans both plugins and must match the right copy whether installed or
    dogfooded-in-repo, WITHOUT false-positiving a like-named file in the target repo under
    review). Protected iff the resolved basename is in SAFETY_MACHINERY AND the path resolves
    under one of `band_roots` (the resolved review-crew / the-architect plugin dirs the wrapper
    supplies). Fails CLOSED: an unparseable path, or no band_roots to anchor against, is treated
    as protected.
    """
    if not isinstance(path, str) or not path:
        return True
    rp = os.path.realpath(path)
    if os.path.basename(rp) not in SAFETY_MACHINERY:
        return False
    roots = [os.path.realpath(r) for r in (band_roots or []) if r]
    if not roots:
        return True   # cannot anchor -> fail closed (protect)
    return any(rp == r or rp.startswith(r + os.sep) for r in roots)


def _as_bool(s):
    if s in ("true", "True", "1", "yes"):
        return True
    if s in ("false", "False", "0", "no"):
        return False
    return s   # pass through so route() fail-closes on a bad value


def _build_parser():
    p = argparse.ArgumentParser(description="superheroes escalation rubric — deterministic core")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("route", help="axis judgments -> proceed/notify/gate")
    r.add_argument("--on-floor", required=True)
    r.add_argument("--ground-truth-locus", required=True)
    r.add_argument("--owner-weighable", required=True)
    r.add_argument("--reversible", required=True)
    r.add_argument("--confidence", required=True)
    c = sub.add_parser("classify", help="action descriptor -> on_floor true/false")
    c.add_argument("--action", required=True)
    g = sub.add_parser("guard", help="path -> allow/refuse (fixer file-scope guard)")
    g.add_argument("--path", required=True)
    g.add_argument("--band-root", action="append", default=[],
                   help="a resolved plugin root to anchor the canonical-path match (repeatable)")
    return p


def main(argv):
    args = _build_parser().parse_args(argv[1:])
    if args.cmd == "route":
        axes = {"on_floor": _as_bool(args.on_floor),
                "ground_truth_locus": args.ground_truth_locus,
                "owner_weighable": _as_bool(args.owner_weighable),
                "reversible": _as_bool(args.reversible),
                "confidence": args.confidence}
        sys.stdout.write(json.dumps({"mode": route(axes)}) + "\n")
        return 0
    if args.cmd == "classify":
        sys.stdout.write(json.dumps({"on_floor": classify_floor(args.action)}) + "\n")
        return 0
    if args.cmd == "guard":
        sys.stdout.write(json.dumps(
            {"allow": not is_safety_machinery(args.path, args.band_root)}) + "\n")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
