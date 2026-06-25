#!/usr/bin/env python3
"""Deterministic consumer of the panel synthesis leaf (FR-11/12/13, UFR-10).

Panel legs run a two-stage synthesis: (1) the mechanical identity-merge in
panel_tally.compile_findings, then (2) an Opus judgment leaf that decides, per merged finding,
whether it holds against the artifact (keep/drop + reason) and the rubric-justified severity.
THIS module is stage 3: it consumes the leaf's structured output deterministically so the
*accounting* stays reproducible even though a model made the judgments.

Hard rules:
  - KEEP-ON-UNCERTAIN (FR-12): a finding with no leaf verdict, or a malformed/ambiguous one,
    is KEPT at its pre-synthesis severity — a model's silence never drops a finding.
  - DROP-WITH-REASON (FR-12): a finding is dropped only on a clear `drop` verdict carrying a
    non-empty reason; the drop (id, reason) is recorded.
  - NORMALIZE (FR-13): a surviving finding takes the leaf's severity iff it is a valid rubric
    tier; otherwise it keeps its pre-synthesis severity.
  - UFR-10: a dropped finding whose (merged) severity is blocking — i.e. ANY reviewer tagged it
    Critical/Important (compile_findings keeps the max) — is flagged `was_blocking_tagged` so the
    readout surfaces it for human scrutiny; an all-drop or confidently-wrong leaf can never make
    a silent clean.

Single-reviewer legs never call this (FR-11). stdlib only; never raises on bad leaf output.
"""
import argparse
import json
import sys

import circuit_breaker

_TIERS = ("Critical", "Important", "Minor", "Nit")
_BLOCKING = ("Critical", "Important")


def _identity(f):
    return circuit_breaker.finding_identity(f)


def consume(merged, leaf_verdicts):
    """merged: the mechanically-merged finding list (each has file/title/severity). leaf_verdicts:
    list of {id, action, reason, severity} from the Opus leaf, keyed by finding identity
    (file::normalized_title). Returns {"findings", "drops"}."""
    by_id = {}
    if isinstance(leaf_verdicts, list):
        for v in leaf_verdicts:
            if isinstance(v, dict) and isinstance(v.get("id"), str):
                by_id[v["id"]] = v
    survivors, drops = [], []
    for f in merged:
        v = by_id.get(_identity(f))
        action = v.get("action") if isinstance(v, dict) else None
        reason = v.get("reason") if isinstance(v, dict) else None
        # DROP only on a clear, well-formed drop with a reason; everything else KEEPS.
        if action == "drop" and isinstance(reason, str) and reason.strip():
            drops.append({"id": _identity(f), "file": f.get("file"), "title": f.get("title"),
                          "reason": reason.strip(),
                          "was_blocking_tagged": f.get("severity") in _BLOCKING})
            continue
        kept = dict(f)
        sev = v.get("severity") if isinstance(v, dict) else None
        if sev in _TIERS:
            kept["severity"] = sev  # normalize iff a valid tier; else keep original
        survivors.append(kept)
    return {"findings": survivors, "drops": drops}


def _safe_read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def main(argv):
    ap = argparse.ArgumentParser(description="deterministic panel-synthesis consumer (review-crew)")
    ap.add_argument("--merged", required=True, help="merged findings JSON (array)")
    ap.add_argument("--leaf", required=True, help="Opus leaf verdicts JSON (array)")
    args = ap.parse_args(argv[1:])
    merged = _safe_read_json(args.merged, [])
    if not isinstance(merged, list):
        merged = []
    out = consume(merged, _safe_read_json(args.leaf, []))
    sys.stdout.write(json.dumps(out, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
