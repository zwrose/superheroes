#!/usr/bin/env python3
"""Decide whether the review auto-fix loop is stuck and should halt.

Faithful port of circuit-breaker.ts. `rounds` are chronological (round 1 first);
each round's findings are that round's compiled findings with deliberately-skipped
findings already removed, so a skipped finding never counts toward recurrence or
progress. Un-sensitive by design: normal 2-3 round convergence never trips it.
"""
import json
import os
import re
import sys

from review_memory import clamp_title, canonical_class_key, class_key_aliases

BLOCKING = {"Critical", "Important"}

_NON_WORD = re.compile(r"[^\w\s]", re.ASCII)   # JS \w is ASCII-only — match it
_WS = re.compile(r"\s+", re.ASCII)


def normalize_title(title):
    t = title.lower()
    t = _NON_WORD.sub("", t)
    t = _WS.sub(" ", t)
    return t.strip()


def finding_label(finding):
    return finding.get("title") or finding.get("summary") or ""


def finding_identity(finding):
    return f"{finding.get('file') or ''}::{normalize_title(clamp_title(finding_label(finding)))}"


def recurrence_key(finding):
    if finding.get("dimension") or finding.get("taxonomy"):
        return canonical_class_key(finding)
    if finding.get("classKey"):
        return finding["classKey"]
    return finding_identity(finding)


def recurrence_aliases(finding):
    aliases = {recurrence_key(finding)}
    if finding.get("dimension") or finding.get("taxonomy"):
        aliases |= class_key_aliases(finding)
    return aliases


def _blocking(round_findings):
    return [f for f in round_findings["findings"] if f["severity"] in BLOCKING]


def _round_recorded_fix(round_rec):
    """True when this round's fixer actually recorded applied fixes (rec['fix']['fixes']).
    The cap-halt is evaluated right after a review round and BEFORE that round's fix leg, so the
    latest round normally carries no fix — its findings are still unaddressed. Used to keep the
    max-iterations detail honest instead of always claiming the fixes were committed."""
    fix = round_rec.get("fix")
    if not isinstance(fix, dict):
        return False
    return bool(fix.get("fixes"))


def _generalize_keys(round_rec):
    return {g.get("classKey") for g in round_rec.get("generalizeRequired", [])
            if isinstance(g, dict) and g.get("classKey")}


def _blocking_count_excluding_generalize(round_rec):
    """Count blocking findings not covered by this round's coverage-decision grace."""
    generalize = _generalize_keys(round_rec)
    blocking = _blocking(round_rec)
    if not generalize:
        return len(blocking)
    return len([f for f in blocking if not (recurrence_aliases(f) & generalize)])


def _round_reviewed(round_rec):
    dims = round_rec.get("dimensions")
    if not isinstance(dims, dict) or not dims:
        return True
    return any(isinstance(d, dict) and d.get("status") == "run" for d in dims.values())


def _reviewed_rounds(rounds):
    return [r for r in rounds if _round_reviewed(r)]


def check_circuit_breaker(rounds, max_rounds):
    n = len(rounds)
    if n == 0:
        return {"halt": False, "reason": None, "detail": "no rounds yet"}

    latest_blocking = _blocking(rounds[n - 1])

    # Criterion 3: max iterations (only halts while blocking findings remain).
    if n >= max_rounds and len(latest_blocking) > 0:
        # Honest halt detail (#212 class): name the ACTUAL round reached (n) alongside the cap — a
        # resume can run past the cap, so n may exceed max_rounds — and only claim "fixes committed"
        # when the final round actually recorded a fix. The cap-halt fires right after a review and
        # before that round's fixer runs, so the latest round usually carries no fix; saying otherwise
        # misreads a park that needs a fix-then-relaunch as one that only needs a re-review.
        if _round_recorded_fix(rounds[n - 1]):
            tail = "the final round's fixes are committed but not yet re-reviewed"
        else:
            tail = "no fix was applied this round — the finding(s) remain unaddressed"
        # Don't overstate how many REAL reviews ran: n counts every recorded round (the gate uses it),
        # but a transport-failed / all-missing round inflates it. When fewer rounds were actually
        # reviewed than recorded, say so — the same honesty `_reviewed_rounds` gives criteria 1-2.
        cap_note = f"cap {max_rounds}"
        reviewed_n = len(_reviewed_rounds(rounds))
        if reviewed_n < n:
            cap_note += f", {reviewed_n} reviewed"
        return {
            "halt": True,
            "reason": "max-iterations",
            "detail": (f"Reached round {n} ({cap_note}); the latest review still showed "
                       f"{len(latest_blocking)} blocking finding(s) ({tail})."),
        }

    # Criterion 2: no net progress across two consecutive round-transitions.
    # Exclude generalize-pending classKeys from each round's count so grace at round 3
    # is not preempted by a flat single-class recurrence (Criterion 1's job).
    reviewed = _reviewed_rounds(rounds)
    rn = len(reviewed)
    if rn >= 3:
        c_n = _blocking_count_excluding_generalize(reviewed[rn - 1])
        c_n1 = _blocking_count_excluding_generalize(reviewed[rn - 2])
        c_n2 = _blocking_count_excluding_generalize(reviewed[rn - 3])
        if c_n > 0 and c_n >= c_n1 and c_n1 >= c_n2:
            return {
                "halt": True,
                "reason": "no-net-progress",
                "detail": f"Blocking-finding count did not decrease over two rounds ({c_n2} → {c_n1} → {c_n}).",
            }

    # Criterion 1: recurring finding across the two most recent rounds.
    if rn >= 2:
        latest_rec = reviewed[rn - 1]
        latest_generalize = {g.get("classKey") for g in latest_rec.get("generalizeRequired", []) if isinstance(g, dict)}
        challenged = {d.get("classKey") for d in latest_rec.get("coverageDecisions", []) if isinstance(d, dict) and d.get("challengedBy")}
        latest_blocking = _blocking(latest_rec)
        prev_ids = set()
        for f in _blocking(reviewed[rn - 2]):
            prev_ids |= recurrence_aliases(f)
        recurring = [f for f in latest_blocking if recurrence_aliases(f) & prev_ids]
        challenged_recurring = [f for f in recurring if recurrence_aliases(f) & challenged]
        if challenged_recurring:
            ids = "; ".join(recurrence_key(f) for f in challenged_recurring)
            return {"halt": True, "reason": "challenged-principle-recurring", "detail": f"{len(challenged_recurring)} challenged coverage decision class recurred after being recorded: {ids}"}
        if recurring:
            keys = {recurrence_key(f) for f in recurring}
            if keys & latest_generalize:
                return {"halt": False, "reason": None, "detail": "recurrence pending coverage decision"}
            ids = "; ".join(sorted(keys))
            return {"halt": True, "reason": "recurring-finding", "detail": f"{len(recurring)} blocking finding(s) recurred after a fix was committed: {ids}"}

    return {"halt": False, "reason": None, "detail": "progressing"}


def load_rounds(session_dir):
    """Read round-N/compiled.json for every round in numeric order; remove any
    finding identity that was skipped in ANY round's resolutions.json."""
    entries = []
    for name in os.listdir(session_dir):
        if os.path.isdir(os.path.join(session_dir, name)) and re.fullmatch(r"round-\d+", name):
            entries.append((name, int(name[len("round-"):])))
    entries.sort(key=lambda e: e[1])

    skipped = set()
    for name, _num in entries:
        rp = os.path.join(session_dir, name, "resolutions.json")
        if not os.path.exists(rp):
            continue
        with open(rp) as fh:
            res = json.load(fh)
        for r in res.get("resolutions", []):
            if r.get("action") == "skip":
                skipped.add(finding_identity({"file": r.get("file") or "", "title": r.get("title") or ""}))

    rounds = []
    for name, num in entries:
        cp = os.path.join(session_dir, name, "compiled.json")
        if not os.path.exists(cp):
            continue
        with open(cp) as fh:
            compiled = json.load(fh)
        findings = [f for f in compiled["findings"] if finding_identity(f) not in skipped]
        rounds.append({"round": num, "findings": findings})
    return {"rounds": rounds, "skipped": skipped}


def main(argv):
    args = argv[1:]
    if not args:
        sys.stderr.write("Usage: circuit_breaker.py <session-dir> [max-rounds=7]\n")
        return 2
    session_dir = args[0]
    max_rounds = int(args[1]) if len(args) > 1 else 7
    result = check_circuit_breaker(load_rounds(session_dir)["rounds"], max_rounds)
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
