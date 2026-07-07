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
  - DOWNGRADE-FLAG (#186): NORMALIZE's other door. A finding the judge re-tiers from blocking
    (Critical/Important) down to non-blocking (Minor/Nit) still applies — the severity change is
    unchanged behavior — but it is recorded in `downgrades` so the readout surfaces it for the
    SAME scrutiny as a dropped blocker. A silent downgrade is functionally a silent drop (it no
    longer counts as blocking in any verdict/gate/confirmation decision); visibility only, so an
    over-confident judge cannot quietly demote a real blocker. Upgrades and non-blocking↔non-
    blocking re-tiers are not flagged (noise).

Single-reviewer legs never call this (FR-11). stdlib only; never raises on bad leaf output.
"""
import argparse
import json
import sys

import circuit_breaker

_TIERS = ("Critical", "Important", "Minor", "Nit")
_DEFAULT_BLOCKING_SEVERITY = "Important"
# #276: the blocking partition (was-tagged-blocking, blocking→non-blocking downgrade detection) routes
# through circuit_breaker.is_blocking — the single, case-normalized, fail-closed predicate — so this
# leg can never disagree with _partition / the breaker / the panel gate on what blocks.


def _identity(f):
    return circuit_breaker.finding_identity(f)


def _kept_severity(f, v):
    verdict_severity = v.get("severity") if isinstance(v, dict) else None
    if verdict_severity in _TIERS:
        return verdict_severity
    finding_severity = f.get("severity")
    if finding_severity in _TIERS:
        return finding_severity
    return _DEFAULT_BLOCKING_SEVERITY


def consume(merged, leaf_verdicts):
    """merged: the mechanically-merged finding list (each has file/title/severity). leaf_verdicts:
    list of {id, action, reason, severity} from the Opus leaf, keyed by finding identity
    (file::normalized_title). Returns {"findings", "drops", "downgrades"}."""
    by_id = {}
    if isinstance(leaf_verdicts, list):
        for v in leaf_verdicts:
            if isinstance(v, dict) and isinstance(v.get("id"), str):
                by_id[v["id"]] = v
    survivors, drops, downgrades = [], [], []
    for f in merged:
        identity = _identity(f)
        v = by_id.get(identity)
        if v is None and isinstance(f, dict) and isinstance(f.get("id"), str):
            v = by_id.get(f["id"])
        action = v.get("action") if isinstance(v, dict) else None
        reason = v.get("reason") if isinstance(v, dict) else None
        # DROP only on a clear, well-formed drop with a reason; everything else KEEPS.
        if action == "drop" and isinstance(reason, str) and reason.strip():
            drops.append({"id": identity, "file": f.get("file"), "title": f.get("title"),
                          "reason": reason.strip(),
                          "was_blocking_tagged": circuit_breaker.is_blocking(f.get("severity"))})
            continue
        kept = dict(f)
        kept["severity"] = _kept_severity(f, v)
        survivors.append(kept)
        # DOWNGRADE-FLAG (#186): a survivor re-tiered from blocking to non-blocking rides recorded
        # (severity outcome unchanged) so the readout can flag it like a dropped blocker.
        from_severity = f.get("severity")
        if circuit_breaker.is_blocking(from_severity) and not circuit_breaker.is_blocking(kept["severity"]):
            entry = {"id": identity, "file": f.get("file"), "title": f.get("title"),
                     "from": from_severity, "to": kept["severity"]}
            if isinstance(reason, str) and reason.strip():
                entry["reason"] = reason.strip()
            downgrades.append(entry)
    return {"findings": survivors, "drops": drops, "downgrades": downgrades}


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
