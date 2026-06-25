#!/usr/bin/env python3
"""Uniform human-facing readout for the shared review-and-fix loop (FR-19/FR-20, UFR-10, FR-21).

Renders ONE readout, the same structure for every leg, from a run's terminal record: the
terminal + reason, the fixes made, the findings dropped (each with its reason), the non-blocking
findings deferred (each with its reason), and — distinctly — any dropped finding a reviewer had
tagged blocking (UFR-10, flagged for human scrutiny). When an escalated blocking finding traces
to an upstream phase, the readout names it (FR-21) and the loop never re-enters it. A record whose
`schemaVersion` the renderer does not understand is surfaced as "unknown record format" rather
than rendered partially. stdlib only; never raises.
"""
import argparse
import json
import sys

SCHEMA_VERSION = 1


def render(record):
    """record: the terminal record dict. Returns the readout string."""
    if not isinstance(record, dict):
        return "## Review loop — unreadable record\n\n(no terminal record was provided)\n"
    if record.get("schemaVersion") != SCHEMA_VERSION:
        return ("## Review loop — unknown record format\n\n"
                "This run's record schemaVersion (%r) is not understood by this readout renderer "
                "(expected %d). Inspect the raw records under the run directory.\n"
                % (record.get("schemaVersion"), SCHEMA_VERSION))
    lines = ["## Review loop — %s" % record.get("terminal", "unknown"), ""]
    if record.get("reason"):
        lines += [str(record["reason"]), ""]
    if record.get("recordMissing"):
        lines += ["> ⚠️ A durable record could not be written — this outcome is reported "
                  "from memory only; treat it as unverified.", ""]
    if record.get("parentOrigin"):
        lines += ["**Traces to an upstream phase:** %s (not re-entered automatically)."
                  % record["parentOrigin"], ""]
    fixes = record.get("fixes") or []
    lines += ["### Fixes made"] + (["- %s" % f for f in fixes] if fixes else ["- (none)"]) + [""]
    deferred = record.get("deferred") or []
    def _row(d):
        return ("- %s — %s" % (d.get("title", "?"), d.get("reason", "")) if isinstance(d, dict)
                else "- %s" % str(d))
    lines += ["### Deferred (non-blocking)"] + ([_row(d) for d in deferred] if deferred else ["- (none)"]) + [""]
    drops = record.get("drops") or []
    ordinary = [d for d in drops if isinstance(d, dict) and not d.get("was_blocking_tagged")]
    blocking = [d for d in drops if isinstance(d, dict) and d.get("was_blocking_tagged")]
    nondict = [d for d in drops if not isinstance(d, dict)]
    lines += ["### Dropped as unsubstantiated"] + (
        [_row(d) for d in ordinary] + ["- %s" % str(d) for d in nondict]
        if (ordinary or nondict) else ["- (none)"]) + [""]
    if blocking:
        lines += ["### ⚠️ Dropped findings a reviewer had tagged BLOCKING — review these",
                  "_A reviewer marked these Critical/Important; synthesis dropped them. Confirm the "
                  "loop did not discard a real blocker._"]
        lines += [_row(d) for d in blocking] + [""]
    return "\n".join(lines).rstrip() + "\n"


def main(argv):
    ap = argparse.ArgumentParser(description="uniform loop readout renderer (review-crew)")
    ap.add_argument("--record", required=True, help="path to the terminal record JSON")
    args = ap.parse_args(argv[1:])
    try:
        with open(args.record, encoding="utf-8") as fh:
            record = json.load(fh)
    except (OSError, ValueError):
        record = None
    sys.stdout.write(render(record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
