#!/usr/bin/env python3
"""Mechanical identity-merge of a review round's findings into merged.json (FR-8 mergeAgent).
Reuses panel_tally.compile_findings (the same file::normalized_title dedupe the deciders use) — no
new judgment. Reads round-<N>/findings-<reviewer>.json per roster name, writes round-<N>/merged.json
atomically. Fail-safe: a missing/malformed findings file contributes nothing, never crashes.
stdlib only."""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_tally  # noqa: E402  (reuse its public layout + compile helpers)


def _read(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def merge(run_dir, rnd, roster):
    findings = []
    for reviewer in roster:
        data = _read(panel_tally.findings_path(run_dir, rnd, reviewer), [])
        if isinstance(data, list):
            findings.extend(data)
    merged = panel_tally.compile_findings(findings)
    out_path = os.path.join(panel_tally.round_dir(run_dir, rnd), "merged.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, sort_keys=True)
    os.replace(tmp, out_path)
    return merged


def main(argv):
    ap = argparse.ArgumentParser(description="mechanical findings merge -> merged.json")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--round", type=int, required=True, dest="rnd")
    ap.add_argument("--roster", required=True, help="comma-separated reviewer names")
    args = ap.parse_args(argv[1:])
    roster = [r for r in args.roster.split(",") if r]
    merge(args.run_dir, args.rnd, roster)
    sys.stdout.write("ok\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
