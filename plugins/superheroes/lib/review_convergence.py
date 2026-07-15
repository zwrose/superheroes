#!/usr/bin/env python3
"""#397 FR-15: the per-review convergence record — rounds used, per-round blocking vs
routed-forward finding counts, and the outcome — emitted at every doc-review terminal (pass,
accepted pass, park) so a park-wall or demotion-wall is visible across runs as data.

Read-only over round-records.json; never mutates anything. Fail-soft: an unreadable or
malformed records file still returns a payload (`roundsUsed: 0`, `perRound: []`) so a
convergence-record write failure never blocks the terminal itself (UFR-1 disclosure is the
caller's job, same as Tasks 15/18's write paths)."""

import argparse
import json
import sys

import circuit_breaker


def compose_convergence(records_path, doc, outcome):
    try:
        with open(records_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {"doc": doc, "outcome": outcome, "roundsUsed": 0, "perRound": []}
    # round-records.json is a bare list on disk (review_memory.load_records_state's shape).
    records = data if isinstance(data, list) else []
    per_round = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        findings = [f for f in (rec.get("findings") or []) if isinstance(f, dict)]
        blocking = sum(1 for f in findings if circuit_breaker.is_blocking(f.get("severity")))
        per_round.append({"round": rec.get("round"), "blocking": blocking,
                          "routedForward": len(findings) - blocking})
    return {"doc": doc, "outcome": outcome, "roundsUsed": len(records), "perRound": per_round}


def main(argv):
    ap = argparse.ArgumentParser(description="#397 per-review convergence record")
    ap.add_argument("--path", required=True, help="round-records.json")
    ap.add_argument("--doc", required=True, choices=["plan", "tasks"])
    ap.add_argument("--outcome", required=True)
    args = ap.parse_args(argv)
    print(json.dumps(compose_convergence(args.path, args.doc, args.outcome)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
