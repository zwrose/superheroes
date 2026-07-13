#!/usr/bin/env python3
"""#397 FR-14: deterministic prefilter + consumer for accepted doc findings at re-review.

The synthesis judge confirms sameness for hash-matched candidates only; keep-on-uncertain
means NOT the same (judged afresh). This module never suppresses on hash alone."""

import argparse
import json
import sys

import circuit_breaker
import finding_identity
import loop_synthesis

# Verdict actions the acceptance sameness judge may emit for hash-matched candidates.
_SAMENESS_ACTIONS = frozenset({"same", "different"})


def prefilter_for_judge(merged, candidates):
    """Return finding identities offered to the acceptance sameness judge (hashMatches only)."""
    match_ids = {
        c.get("identity")
        for c in (candidates or [])
        if isinstance(c, dict) and c.get("hashMatches") and c.get("identity")
    }
    offered = []
    for f in merged or []:
        if not isinstance(f, dict):
            continue
        ident = finding_identity.finding_identity(f)
        if ident in match_ids:
            offered.append(ident)
    return offered


def _split_verdicts(leaf_verdicts, offered):
    offered_set = set(offered or [])
    acceptance, normal = [], []
    if not isinstance(leaf_verdicts, list):
        return acceptance, normal
    for v in leaf_verdicts:
        if not isinstance(v, dict):
            continue
        vid = v.get("id")
        if vid in offered_set:
            acceptance.append(v)
        else:
            normal.append(v)
    return acceptance, normal


def _acceptance_drops(merged, acceptance_verdicts, offered):
    offered_set = set(offered or [])
    by_id = {}
    for v in acceptance_verdicts or []:
        if isinstance(v, dict) and isinstance(v.get("id"), str):
            by_id[v["id"]] = v
    drops = []
    survivors = []
    for f in merged or []:
        if not isinstance(f, dict):
            continue
        ident = finding_identity.finding_identity(f)
        if ident not in offered_set:
            survivors.append(f)
            continue
        v = by_id.get(ident)
        action = v.get("action") if isinstance(v, dict) else None
        reason = v.get("reason") if isinstance(v, dict) else None
        # keep-on-uncertain: only a clear "same" with reason demotes to accepted (drop).
        if action == "same" and isinstance(reason, str) and reason.strip():
            drops.append({
                "id": ident,
                "file": f.get("file"),
                "title": f.get("title"),
                "reason": reason.strip(),
                "was_blocking_tagged": circuit_breaker.is_blocking(f.get("severity")),
                "accepted": True,
            })
        else:
            survivors.append(f)
    return survivors, drops


def consume_with_acceptance(merged, leaf_verdicts, candidates):
    """Apply acceptance sameness for hash-matched candidates, then normal synthesis for the rest."""
    offered = prefilter_for_judge(merged, candidates)
    acc_verdicts, normal_verdicts = _split_verdicts(leaf_verdicts, offered)
    survivors, acc_drops = _acceptance_drops(merged, acc_verdicts, offered)
    normal_out = loop_synthesis.consume(survivors, normal_verdicts)
    return {
        "findings": normal_out.get("findings") or [],
        "drops": (acc_drops or []) + (normal_out.get("drops") or []),
        "downgrades": normal_out.get("downgrades") or [],
    }


def main(argv):
    ap = argparse.ArgumentParser(description="#397 acceptance re-review consumer")
    ap.add_argument("--merged", required=True)
    ap.add_argument("--leaf", required=True)
    ap.add_argument("--candidates", required=True, help="JSON array from review_acceptance candidates")
    args = ap.parse_args(argv[1:])
    with open(args.merged, encoding="utf-8") as fh:
        merged = json.load(fh)
    with open(args.leaf, encoding="utf-8") as fh:
        leaf = json.load(fh)
    with open(args.candidates, encoding="utf-8") as fh:
        candidates = json.load(fh)
    if not isinstance(merged, list):
        merged = []
    if not isinstance(candidates, list):
        candidates = []
    leaf_verdicts = leaf if isinstance(leaf, list) else (leaf.get("verdicts") if isinstance(leaf, dict) else [])
    out = consume_with_acceptance(merged, leaf_verdicts, candidates)
    sys.stdout.write(json.dumps(out, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
