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

from review_memory import canonical_class_key, class_key_aliases
from finding_identity import (
    clamp_title, normalize_title, finding_label, finding_identity,
)

BLOCKING = {"Critical", "Important"}
# The ONLY severities that demote a finding to non-blocking: the rubric's non-blocking tiers
# (Minor/Nit — SSOT §11, guarded by test_ssot_drift). `is_blocking` is the single, case-normalized,
# FAIL-CLOSED blocking predicate every severity consumer routes through (#276): a foreign scale
# (`blocker`/`high`/`medium`), an unknown tier, a mis-cased `critical`, or a missing severity is
# treated as blocking — an unrecognized severity means blocking, never a silent demotion. Consumers
# keep BLOCKING for rank/identity/"was-tagged-blocking" bookkeeping but ask `is_blocking` the
# partition question, so _partition, the breaker's own stuck-detection, the panel gate, and the
# build legs can never disagree on what blocks.
_NON_BLOCKING = frozenset({"minor", "nit"})

def is_blocking(severity):
    return str("" if severity is None else severity).strip().lower() not in _NON_BLOCKING


def is_critical(severity):
    # #291: the TIER-specific Critical match (case-normalized), single-sourced alongside is_blocking so
    # the confirmation re-arm/park gate can't miss a mis-cased `critical`. Distinct from is_blocking:
    # Important is blocking but NOT critical.
    return str("" if severity is None else severity).strip().lower() == "critical"


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
    return [f for f in round_findings["findings"] if is_blocking(f.get("severity"))]


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


# --- audit-keyed stall detection (#507) --------------------------------------
#
# The code leg's delta rounds replace finding-COUNT comparison with per-finding fix audits: the
# same finding failing audit twice is the stall signal, not a flat count. `check_audit_breaker`
# consumes the effective (post-fail-closed) rulings from `audits.apply_audit_results`, keyed by
# `finding_identity`, and never consults counts — a run that adds MORE discharged findings each
# round is progressing, not stuck. Un-sensitive by design and fail-closed: a malformed round or
# outcome counts toward the stall (a real not-discharged must never uncount into a silent pass).

_MALFORMED_ROUND = "<malformed-audit-round>"
_MALFORMED_OUTCOME = "<malformed-audit-outcome>"


def _audit_outcome_aliases(outcome):
    """Alias set for one audit outcome — the literal `identity` plus, ONLY when the outcome
    carries dimension/taxonomy/classKey, the recurrence class-key aliases (so a retitled finding
    that keeps its class can't dodge the stall signal, exactly like the recurring-finding check).
    A dimension-less outcome contributes only its identity string — never the empty "::" key a
    bare recurrence_aliases would synthesize."""
    if not isinstance(outcome, dict):
        return set()
    aliases = set()
    ident = outcome.get("identity")
    if isinstance(ident, str) and ident:
        aliases.add(ident)
    if outcome.get("dimension") or outcome.get("taxonomy") or outcome.get("classKey"):
        aliases |= recurrence_aliases(outcome)
    return aliases


def _round_not_discharged(round_rec):
    """Alias-sets for every NOT-DISCHARGED outcome in one audit round. Fail-closed: a malformed
    round (not a dict / no outcomes list) or a malformed outcome (not a dict / no identity /
    unknown ruling) yields a synthetic not-discharged marker so it counts toward the stall rather
    than silently passing. A `discharged` / `discharged-but-new-issue` outcome clears (drops out)."""
    if not isinstance(round_rec, dict):
        return [{_MALFORMED_ROUND}]
    outcomes = round_rec.get("outcomes")
    if not isinstance(outcomes, list):
        return [{_MALFORMED_ROUND}]
    out = []
    for o in outcomes:
        if not isinstance(o, dict):
            out.append({_MALFORMED_OUTCOME})
            continue
        if o.get("ruling") in ("discharged", "discharged-but-new-issue"):
            continue
        aliases = _audit_outcome_aliases(o)
        out.append(aliases or {_MALFORMED_OUTCOME})
    return out


def check_audit_breaker(audit_rounds, max_rounds):
    """Audit-keyed stall detector for the code leg's delta rounds (#507).

    `audit_rounds` — chronological list of {"round": N, "outcomes": [{identity, ruling}]}, the
    effective rulings from `audits.apply_audit_results`. Halt conditions, checked in order:
      1. `max-iterations` — round count >= max_rounds while any latest-round outcome is
         not-discharged.
      2. `audit-stall` — some identity is not-discharged in two CONSECUTIVE audit rounds
         (alias-tolerant, so a retitled-but-same-class finding still stalls).

    Never consults finding counts. Fail-closed on malformed input; empty history → no halt.
    """
    if not isinstance(audit_rounds, list) or not audit_rounds:
        return {"halt": False, "reason": None, "detail": "no audit rounds yet",
                "stalledIdentities": []}

    per_round = [_round_not_discharged(r) for r in audit_rounds]
    n = len(per_round)
    latest = per_round[-1]

    # Criterion 1: round cap reached with an open (not-discharged) finding this round.
    if n >= max_rounds and latest:
        open_ids = sorted({a for aliases in latest for a in aliases})
        return {
            "halt": True,
            "reason": "max-iterations",
            "detail": ("Reached audit round %d (cap %d) with %d finding(s) still not discharged."
                       % (n, max_rounds, len(latest))),
            "stalledIdentities": open_ids,
        }

    # Criterion 2: the same finding failing audit in two consecutive rounds.
    stalled = set()
    for i in range(1, n):
        prev = per_round[i - 1]
        cur = per_round[i]
        for cur_aliases in cur:
            for prev_aliases in prev:
                shared = cur_aliases & prev_aliases
                if shared:
                    stalled |= shared
    if stalled:
        ids = sorted(stalled)
        return {
            "halt": True,
            "reason": "audit-stall",
            "detail": ("%d finding(s) failed audit in two consecutive rounds: %s"
                       % (len(ids), "; ".join(ids))),
            "stalledIdentities": ids,
        }

    return {"halt": False, "reason": None, "detail": "progressing", "stalledIdentities": []}


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
