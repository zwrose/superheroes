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

import circuit_breaker
import finding_identity
import readout   # the same scrub seam journal.py/review_park.py use — see below

SCHEMA_VERSION = 1
FILENAME = "plan-handoff.json"


def _scrubbed_label(finding):
    # `text`/`identity` both derive from the finding's title/summary — free text a courier
    # round-tripped. Scrub HERE, at entry-composition time (review_park.py's `_decision()` does
    # the same for park payloads) so no unscrubbed secret reaches plan-handoff.json in either
    # field. Identity mirrors finding_identity's title-before-summary label selection on the
    # scrubbed copy so dedupe semantics stay aligned with the rest of the system.
    title_raw = finding.get("title") or ""
    summary_raw = finding.get("summary") or ""
    ident_finding = {"file": finding.get("file")}
    if title_raw:
        ident_finding["title"] = readout.scrub(title_raw)[0]
    elif summary_raw:
        ident_finding["summary"] = readout.scrub(summary_raw)[0]
    else:
        ident_finding["title"] = ""
    text = readout.scrub(summary_raw or title_raw)[0]
    return text, ident_finding


def _entry(finding):
    text, ident_finding = _scrubbed_label(finding)
    return {
        "identity": finding_identity.finding_identity(ident_finding),
        "planSection": finding.get("planSection") or finding.get("docSection") or "",
        "text": text,
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


def collect_blocking(records_path):
    """Read round-records.json and return open BLOCKING findings from the terminal round."""
    try:
        with open(records_path, encoding="utf-8") as fh:
            records = json.load(fh)
    except (OSError, ValueError) as exc:
        return {"ok": False, "reason": "unreadable: " + str(exc)}
    if not isinstance(records, list):
        return {"ok": True, "findings": []}
    rec = records[-1] if records else None
    findings = []
    for f in (rec or {}).get("findings") or []:
        if not isinstance(f, dict):
            continue
        if circuit_breaker.is_blocking(f.get("severity")):
            findings.append(dict(f))
    return {"ok": True, "findings": findings}


def collect_nonblocking(records_path):
    """Read round-records.json from disk and return non-blocking findings for plan-handoff staging.

    The blocking partition routes through circuit_breaker.is_blocking (case-normalized, fail-closed)
    — the same predicate the panel gate uses — so the hand-off list never disagrees with the
    terminal verdict on what was blocking vs non-blocking.
    """
    try:
        with open(records_path, encoding="utf-8") as fh:
            records = json.load(fh)
    except (OSError, ValueError) as exc:
        return {"ok": False, "reason": "unreadable: " + str(exc)}
    if not isinstance(records, list):
        return {"ok": True, "findings": []}
    findings = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        round_findings = rec.get("findings")
        if not isinstance(round_findings, list):
            continue
        for f in round_findings:
            if not isinstance(f, dict):
                continue
            if not circuit_breaker.is_blocking(f.get("severity")):
                entry = dict(f)
                entry["planSection"] = (
                    f.get("planSection") or f.get("docSection") or f.get("section")
                    or f.get("dimension") or ""
                )
                findings.append(entry)
    return {"ok": True, "findings": findings}


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
    c = sub.add_parser("collect")
    c.add_argument("--records-path", required=True)
    cb = sub.add_parser("collect-blocking")
    cb.add_argument("--records-path", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "write":
        with open(args.findings, encoding="utf-8") as fh:
            findings = json.load(fh)
        print(json.dumps(write_handoff(args.docs_dir, args.work_item, findings)))
    elif args.cmd == "collect":
        print(json.dumps(collect_nonblocking(args.records_path)))
    elif args.cmd == "collect-blocking":
        print(json.dumps(collect_blocking(args.records_path)))
    else:
        print(json.dumps(read_handoff(args.docs_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
