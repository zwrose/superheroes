#!/usr/bin/env python3
"""#397 FR-10/FR-11: compose the doc-review park decision list.

On a doc-review halt, read the terminal round's open BLOCKING findings from round-records.json
and turn each into a plain-language decision the owner can rule on: the statement, the doc
section it concerns, what accepting it would mean, and the two owner moves (direct a fix + a
fresh review, or accept the finding through the existing gate-approval step). The output is the
structured `payload` of the `parked` journal event and the readout block. Fail-soft: an
unreadable record still parks, with the reason and a note that the list could not be composed."""

import argparse
import json
import os
import sys

import circuit_breaker
import readout   # the same scrub seam journal.py itself uses — see below

MOVE_FIX = "Direct a fix, then re-review (the ordinary path): the review re-runs and this finding must clear the bar."
MOVE_ACCEPT = "Accept this finding through the existing gate-approval step: the gate reads passed with it recorded as accepted."


def _decision(finding):
    # `statement`/`accepting_means` are built from the finding's own title/summary — free text a
    # courier round-tripped, potentially embedding a copied secret. This payload becomes the
    # `parked` journal event's `payload` verbatim, and journal.append writes `payload` as-is (no
    # scrub — only `detail`/`world` are on that path). Scrub HERE, at composition time, so no
    # caller of compose_park can forget to and no unscrubbed finding text ever reaches the event.
    section = finding.get("docSection") or finding.get("planSection") or finding.get("section") or ""
    statement = readout.scrub(finding.get("summary") or finding.get("title") or "")[0]
    return {
        "statement": statement,
        "docSection": section,
        "accepting_means": "The build proceeds as the document stands on this point; "
                           + (statement or "this concern") + " is left as-is.",
        "moves": [MOVE_FIX, MOVE_ACCEPT],
    }


def compose_park(records_path, round_no, doc, reason):
    payload = {"doc": doc, "round": round_no, "reason": reason, "decisions": [], "note": ""}
    try:
        with open(records_path, encoding="utf-8") as fh:
            data = json.load(fh)
        # round-records.json is a bare list on disk (review_memory.load_records_state's shape) —
        # match it exactly rather than tolerating a second, never-produced wrapped shape.
        records = data if isinstance(data, list) else []
        rec = next((r for r in (records or []) if isinstance(r, dict) and r.get("round") == round_no), None)
        if rec is None and records:
            rec = records[-1]
        findings = (rec or {}).get("findings") or []
    except (OSError, ValueError, TypeError):
        payload["note"] = "the open-findings list could not be composed (round record unreadable)"
        return {"ok": True, "payload": payload}
    payload["decisions"] = [_decision(f) for f in findings
                            if isinstance(f, dict) and circuit_breaker.is_blocking(f.get("severity"))]
    if not payload["decisions"]:
        payload["note"] = "no open blocking findings were recorded for the terminal round"
    return {"ok": True, "payload": payload}


def main(argv):
    ap = argparse.ArgumentParser(description="#397 doc-review park composer")
    ap.add_argument("--path", required=True, help="round-records.json")
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--doc", required=True, choices=["plan", "tasks"])
    ap.add_argument("--reason", required=True)
    args = ap.parse_args(argv)
    print(json.dumps(compose_park(args.path, args.round, args.doc, args.reason)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
