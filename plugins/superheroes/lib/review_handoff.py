#!/usr/bin/env python3
"""#397 FR-2/FR-3/UFR-3/UFR-5: the plan-review -> tasks-author hand-off of non-blocking findings.

`write_handoff` dedupes by the deterministic finding-identity key (a reworded dup collapses;
the failure direction is a harmless redundant entry, never a dropped finding) and writes
`plan-handoff.json` into the work-item docs dir (the caller passes the resolved dir).
`read_handoff` returns the list or a structured {ok:false, reason} so the tasks phase can
disclose an absent/unreadable hand-off (UFR-5) rather than proceed silently.
"""

import argparse
import json
import os
import sys

import finding_identity
import readout   # the same scrub seam journal.py/review_park.py use — see below

SCHEMA_VERSION = 1
FILENAME = "plan-handoff.json"


def _entry(finding):
    # `text` is free text a courier round-tripped from the finding's title/summary — the exact
    # shape review_park.py's `_decision()` scrubs before it reaches a journal payload. This
    # writer's output is a DURABLE FILE (plan-handoff.json), not an event payload, but the risk
    # (an unscrubbed secret embedded in reworded finding text) is identical, so scrub HERE, at
    # entry-composition time, the same way — never write the raw text to disk.
    text = finding.get("summary") or finding.get("title") or ""
    return {
        "identity": finding_identity.finding_identity(finding),
        "planSection": finding.get("planSection") or finding.get("docSection") or "",
        "text": readout.scrub(text)[0],
    }


def write_handoff(docs_dir, work_item, findings):
    seen = {}
    order = []
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        e = _entry(f)
        if e["identity"] not in seen:
            seen[e["identity"]] = e
            order.append(e["identity"])
    entries = [seen[i] for i in order]
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "workItem": work_item,
        "findings": entries,
        "counts": {"distinct": len(entries)},
    }
    path = os.path.join(docs_dir, FILENAME)
    try:
        os.makedirs(docs_dir, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, sort_keys=True)
        os.replace(tmp, path)
    except OSError as exc:
        return {"ok": False, "reason": "handoff-write-failed: " + str(exc), "counts": payload["counts"]}
    return {"ok": True, "path": path, "counts": payload["counts"]}


def read_handoff(docs_dir):
    path = os.path.join(docs_dir, FILENAME)
    if not os.path.exists(path):
        return {"ok": False, "reason": "absent"}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return {"ok": False, "reason": "unreadable: " + str(exc)}
    findings = data.get("findings") if isinstance(data, dict) else None
    if not isinstance(findings, list):
        return {"ok": False, "reason": "malformed"}
    return {"ok": True, "findings": findings, "counts": (data.get("counts") or {})}


def main(argv):
    ap = argparse.ArgumentParser(description="#397 plan-review hand-off list")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--docs-dir", required=True)
    w.add_argument("--work-item", required=True)
    w.add_argument("--findings", required=True, help="path to a JSON array of findings")
    r = sub.add_parser("read")
    r.add_argument("--docs-dir", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "write":
        with open(args.findings, encoding="utf-8") as fh:
            findings = json.load(fh)
        print(json.dumps(write_handoff(args.docs_dir, args.work_item, findings)))
    else:
        print(json.dumps(read_handoff(args.docs_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
