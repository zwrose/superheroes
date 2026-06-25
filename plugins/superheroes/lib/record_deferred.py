#!/usr/bin/env python3
"""Consumer-side deferral + readout-enrichment recorder for the native review-code phase
(FR-6 / FR-8 recordDeferred). From the code-fixer's report it (1) merges deferred finding
identities (+severity) into deferred-set.json (the channel #104's tally reads); (2) read-merge-writes
a run-scoped keyed {identity: phase} parent-origin accumulator; (3) derives the deduped, stable-joined
parentOrigin string and writes the readout enrichment to extras.json ({fixes, parentOrigin?}) that
the shell forwards to the tally. All writes atomic; never raises. No loop-decision logic. stdlib only."""
import argparse
import json
import os
import sys


def _read(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _atomic(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, sort_keys=True)
    os.replace(tmp, path)


def record(run_dir, report):
    report = report if isinstance(report, dict) else {}
    deferred = report.get("deferred") if isinstance(report.get("deferred"), list) else []
    dset = _read(os.path.join(run_dir, "deferred-set.json"), {})
    if not isinstance(dset, dict):
        dset = {}
    porigin = _read(os.path.join(run_dir, "parent-origin.json"), {})
    if not isinstance(porigin, dict):
        porigin = {}
    for d in deferred:
        if not isinstance(d, dict):
            continue
        ident = d.get("id")
        if not ident:
            continue
        dset[ident] = d.get("severity")
        phase = d.get("parentOrigin")
        if phase:
            porigin[ident] = phase
    _atomic(os.path.join(run_dir, "deferred-set.json"), dset)
    _atomic(os.path.join(run_dir, "parent-origin.json"), porigin)
    phases = []
    for phase in porigin.values():           # stable, deduped: insertion order of distinct phases
        if phase and phase not in phases:
            phases.append(phase)
    extras = {"fixes": report.get("fixed") if isinstance(report.get("fixed"), list) else []}
    if phases:
        extras["parentOrigin"] = ", ".join(phases)
    _atomic(os.path.join(run_dir, "extras.json"), extras)
    return {"ok": True, "parentOrigin": extras.get("parentOrigin"), "deferred": len(deferred)}


def main(argv):
    ap = argparse.ArgumentParser(description="record deferrals + readout enrichment (review-code)")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--report", required=True, help="the code-fixer report JSON")
    args = ap.parse_args(argv[1:])
    try:
        report = json.loads(args.report)
    except (ValueError, json.JSONDecodeError):
        report = {}
    sys.stdout.write(json.dumps(record(args.run_dir, report)) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
