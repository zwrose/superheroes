#!/usr/bin/env python3
"""Front-half (#88) pure deciders + thin IO leaf-helpers for the showrunner engine.

Control-flow-only JS (showrunner.js) forwards every judgement here. Pure functions are
fail-closed (the band's phase_step/recover pattern); IO helpers (merge/record-deferred/
append-notify) are deterministic file writers the doc-leg leaf wrappers call. stdlib only,
plus the in-repo panel_tally / loop_readout libs. Never raises out of a CLI subcommand.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loop_readout  # in-repo #104 readout renderer — embedded, never forked
import panel_tally  # in-repo #104: compile_findings (mechanical identity-merge)


def gate_for_terminal(terminal):
    """Map a #104 loop terminal onto a definition-doc review gate value (FR-5).

    clean / clean-with-skips -> "passed"; every other or unknown terminal
    (cannot-certify, halted, continue, None, ...) -> "changes-requested" (fail-closed:
    an unrecognized terminal never advances). Reads the terminal #104 produced; it does
    not re-derive the decision from findings.
    """
    return "passed" if terminal in ("clean", "clean-with-skips") else "changes-requested"


# placeholder tokens forbidden in a finished definition-doc (writing-plans' No-Placeholders bar);
# "TODO" is deliberately omitted (it collides with legitimate code samples in tasks docs). The
# "similar to Task" form requires a following word char (e.g. "N"/"3") so it can't match plain prose
# or punctuation.
_PLACEHOLDER = re.compile(r"\{\{|<!--\s*AUTHOR GUIDANCE|\bTBD\b|similar to Task\s+\w", re.IGNORECASE)


def is_usable_draft(doc_text, completion_signal, expected_signal, required_sections=()):
    """Two-part 'usable draft' check (spec Glossary; separates FR-8 resume from UFR-4 re-produce).

    Usable iff BOTH:
      (a) the produce step recorded successful completion AND the signal is content-bound:
          `completion_signal` is truthy and equals `expected_signal` (e.g. the doc's content
          hash). A missing/empty signal, or a stale signal from an earlier run (mismatch),
          is NOT usable -> re-produce.
      (b) content is complete: frontmatter present and closed, a non-empty body, every
          `required_sections` heading present and non-empty, and no placeholder token.

    Fail-closed: any ambiguity returns False (re-produce). Pure; never raises.
    """
    # (a) content-bound completion signal
    if not completion_signal or not expected_signal or completion_signal != expected_signal:
        return False
    # (b) content completeness
    if not doc_text or not doc_text.strip() or not doc_text.startswith("---\n"):
        return False
    end = doc_text.find("\n---", 4)
    if end == -1:
        return False
    body = doc_text[end + 4:]
    if not body.strip():
        return False
    if _PLACEHOLDER.search(doc_text):
        return False
    for sec in required_sections:
        m = re.search(r"^#{1,6}\s+" + re.escape(sec) + r"\s*$", body, re.MULTILINE)
        if not m:
            return False
        rest = body[m.end():]
        nxt = re.search(r"^#{1,6}\s+", rest, re.MULTILINE)
        segment = rest[:nxt.start()] if nxt else rest
        if not segment.strip():
            return False
    return True


def render_run_outcome(outcome):
    """Compose the front-half's run-outcome envelope (FR-7): completed phases, where the docs
    landed, the park reason, the deduplicated produce/revise NOTIFY defaults (UFR-2), and each
    phase's #104 loop readout embedded verbatim (loop_readout.render). Flags an undelivered
    durable readout (UFR-6). Pure; never raises.

    outcome keys (all optional): completed_phases [str], docs {phase: path}, parked_phase str,
    park_reason str, notify [{phase, identity, message}], phase_records [{phase, record}],
    readout_record_ok bool.
    """
    o = outcome if isinstance(outcome, dict) else {}
    lines = ["# Front-half run outcome", ""]
    completed = o.get("completed_phases") or []
    lines += ["**Completed phases:** " + (", ".join(completed) if completed else "(none)"), ""]
    docs = o.get("docs") or {}
    if isinstance(docs, dict) and docs:
        lines += ["**Docs:**"] + ["- %s → %s" % (k, v) for k, v in docs.items()] + [""]
    if o.get("parked_phase"):
        lines += ["**Parked at:** %s — %s" % (o.get("parked_phase"), o.get("park_reason") or ""), ""]
    # deduplicated NOTIFY defaults (events.jsonl is per-work-item, so re-produce can repeat them).
    deduped, seen = [], set()
    for n in (o.get("notify") or []):
        if not isinstance(n, dict):
            continue
        # fall back to the message when no identity is given, so distinct un-identified NOTIFYs
        # don't collide on (phase, None) and collapse to one.
        key = (n.get("phase"), n.get("identity") or n.get("message"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(n)
    lines += ["**NOTIFY defaults (named — owner may veto):**"] + (
        ["- [%s] %s" % (n.get("phase", "?"), n.get("message", "")) for n in deduped]
        if deduped else ["- (none)"]) + [""]
    # embed each phase's #104 readout verbatim (do NOT fork loop_readout).
    for pr in (o.get("phase_records") or []):
        if not isinstance(pr, dict):
            continue
        lines += ["## %s — review loop readout" % pr.get("phase", "?"), "",
                  loop_readout.render(pr.get("record")), ""]
    if o.get("readout_record_ok") is False:
        lines += ["> ⚠️ The durable readout record could not be written — this outcome is "
                  "reported to the invoking session only; treat the durable copy as missing "
                  "(UFR-6).", ""]
    return "\n".join(lines).rstrip() + "\n"


def _round_dir(run_dir, rnd):
    return os.path.join(run_dir, "round-%d" % int(rnd))


def merge_findings(run_dir, rnd, roster):
    """Mechanical identity-merge of a round's findings-<reviewer>.json into round-<N>/merged.json
    via panel_tally.compile_findings (no judgement — that is the synthesis leaf's). Returns the
    merged-finding count. A missing/garbage findings file contributes nothing (fail-open per file)."""
    rd = _round_dir(run_dir, rnd)
    all_findings = []
    for r in (roster or []):
        p = os.path.join(rd, "findings-%s.json" % r)
        try:
            with open(p, encoding="utf-8") as fh_:
                data = json.load(fh_)
            if isinstance(data, list):
                all_findings.extend(data)
        except (OSError, ValueError):
            continue
    merged = panel_tally.compile_findings(all_findings)
    os.makedirs(rd, exist_ok=True)
    with open(os.path.join(rd, "merged.json"), "w", encoding="utf-8") as fh_:
        json.dump(merged, fh_)
    return len(merged) if isinstance(merged, list) else 0


def record_deferred(report, run_dir):
    """Append the round's deferred identities (+severity) to deferred-set.json, the {identity:
    severity} map panel_tally reads for present-∩-deferred (#104). Returns the count appended.
    Tolerant of an empty/None report."""
    deferred = (report or {}).get("deferred") if isinstance(report, dict) else None
    path = os.path.join(run_dir, "deferred-set.json")
    try:
        with open(path, encoding="utf-8") as fh_:
            existing = json.load(fh_)
        if not isinstance(existing, dict):
            existing = {}
    except (OSError, ValueError):
        existing = {}
    n = 0
    for d in (deferred or []):
        if isinstance(d, dict) and d.get("identity"):
            existing[d["identity"]] = d.get("severity")
            n += 1
    os.makedirs(run_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh_:
        json.dump(existing, fh_)
    return n


def append_notify(ledger_path, entries):
    """Append produce/revise NOTIFY defaults to the durable per-work-item NOTIFY ledger
    (a JSON array) that render_run_outcome reads + dedupes at the boundary (UFR-2). Each entry is
    {phase, identity, message}. Returns the new total. Tolerant of a missing/garbage ledger."""
    try:
        with open(ledger_path, encoding="utf-8") as fh_:
            existing = json.load(fh_)
        if not isinstance(existing, list):
            existing = []
    except (OSError, ValueError):
        existing = []
    for e in (entries or []):
        if isinstance(e, dict) and e.get("message"):
            existing.append({"phase": e.get("phase"), "identity": e.get("identity"),
                             "message": e.get("message")})
    os.makedirs(os.path.dirname(ledger_path) or ".", exist_ok=True)
    with open(ledger_path, "w", encoding="utf-8") as fh_:
        json.dump(existing, fh_)
    return len(existing)


def main(argv):
    ap = argparse.ArgumentParser(description="front-half (#88) deciders + leaf-helpers")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate-for-terminal")
    g.add_argument("--terminal", required=True)
    u = sub.add_parser("usable-draft")
    u.add_argument("--doc", required=True)
    u.add_argument("--completion-signal", default="")
    u.add_argument("--expected-signal", default="")
    u.add_argument("--sections", default="")
    r = sub.add_parser("render-outcome")
    r.add_argument("--outcome", required=True, help="path to the outcome JSON")
    m = sub.add_parser("merge")
    m.add_argument("--run-dir", required=True)
    m.add_argument("--round", type=int, required=True, dest="rnd")
    m.add_argument("--roster", required=True)
    rdf = sub.add_parser("record-deferred")
    rdf.add_argument("--run-dir", required=True)
    rdf.add_argument("--report", required=True, help="path to the fixStep report JSON")
    an = sub.add_parser("append-notify")
    an.add_argument("--ledger", required=True)
    an.add_argument("--entries", required=True, help="JSON array of {phase,identity,message}")
    args = ap.parse_args(argv[1:])

    if args.cmd == "gate-for-terminal":
        sys.stdout.write(json.dumps({"gate": gate_for_terminal(args.terminal)}) + "\n")
        return 0
    if args.cmd == "usable-draft":
        try:
            with open(args.doc, encoding="utf-8") as fh_:
                text = fh_.read()
        except OSError:
            text = ""  # unreadable -> not usable (fail-closed)
        secs = tuple(s for s in args.sections.split(",") if s)
        ok = is_usable_draft(text, args.completion_signal, args.expected_signal, secs)
        sys.stdout.write(json.dumps({"usable": bool(ok)}) + "\n")
        return 0
    if args.cmd == "render-outcome":
        try:
            with open(args.outcome, encoding="utf-8") as fh_:
                data = json.load(fh_)
        except (OSError, ValueError):
            data = None
        sys.stdout.write(render_run_outcome(data))
        return 0
    if args.cmd == "merge":
        roster = [r for r in args.roster.split(",") if r]
        n = merge_findings(args.run_dir, args.rnd, roster)
        sys.stdout.write(json.dumps({"ok": True, "merged": n}) + "\n")
        return 0
    if args.cmd == "record-deferred":
        try:
            with open(args.report, encoding="utf-8") as fh_:
                report = json.load(fh_)
        except (OSError, ValueError):
            report = None
        n = record_deferred(report, args.run_dir)
        sys.stdout.write(json.dumps({"ok": True, "deferred": n}) + "\n")
        return 0
    if args.cmd == "append-notify":
        try:
            entries = json.loads(args.entries)
        except (ValueError, TypeError):
            entries = []
        n = append_notify(args.ledger, entries)
        sys.stdout.write(json.dumps({"ok": True, "notify": n}) + "\n")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
