#!/usr/bin/env python3
"""Showrunner review-panel deciders — the script-owned side of the #211 data-flow refactor.

Architecture (#211): *decisions ride up, pointers ride down, content stays on disk.* The
Workflow sandbox has no I/O, so every byte between the JS orchestrator and the world crosses a
model-generated answer — and a model is not a wire. Five live runs proved the failure class:
every remaining review-loop escape was a *courier answer that scaled with run size* (a re-typed
8 KB blob, a stuttered 7.9 KB JSON, an API refusal on an opaque payload). Small, semantically
meaningful JSON — gates, verdicts, scalars — has never failed once.

So the durable `round-records.json` (skeletons, written every round via the *solved* down
direction) is the single source of truth, and these Python **deciders** read it (plus coverage
and the deferred set) and answer O(1) meaningful JSON: *what round, what schedule, what now,
where's the worklist* — never findings. The JS shell (`review_panel_shell.js`, cut over in the
stacked PR-2) holds no findings: it persists the reviewer's own generated answer down, then asks
these deciders "what now?" and makes its one branch.

This module owns NO policy of its own. The schedule comes from `review_round_policy.plan_round`,
the breaker from `circuit_breaker.check_circuit_breaker`, the terminal from
`panel_tally.decide_terminal`, the confirmation-bar economics from
`review_round_policy.confirmation_followup` / `is_cross_cutting`, recurrence from
`review_memory.recurrent_classes` — the same parity-locked twins the JS shell calls in memory
today. These deciders are a faithful port of the shell's in-memory record consumers (the #211
Phase-0 census: `resumeRound`, `buildPreviousDimensionState`, `carryForwardDimension`,
`confirmationReady`, `panelWindow`/`furtherConfirmationOwed`/`certificationSummary`,
`assembleRounds`→breaker, `buildFixContext`), reading the record content from disk instead of an
in-memory copy. The equivalence smoke pins decider ≡ shell over shared fixtures.

Two scalars ride DOWN from the shell as command args because they are *decisions the shell must
compute at the moment the reviewer answers arrive*, not content:
  - the **gate** (clean/blocking/cannot-certify + confidence + missing[]) — the durable skeleton
    strips each dim's `verificationReceipt`, so the confirmation-round gate cannot be faithfully
    recomputed from disk; the shell computes it from the live answers (receipts present) and
    discards the findings immediately after persisting them down.
  - **present-blocking** — the count of current (non-carried) blocking findings, likewise from
    the live answers.
Everything else (breaker, terminal, confirmation follow-up, certification) the deciders compute
from disk. Every fail-closed path in the shell stays fail-closed here.

Staging note: in this first stacked PR these deciders are DORMANT — the live shell still runs its
own in-memory copies, so nothing here decides a real run yet and there is no production drift. The
stacked PR-2 wires the shell to these deciders, deletes the in-memory record model, and lands the
decider ≡ shell equivalence smoke (Phase 4a) — the drift guard that pins this port against the
shell functions it replaces, where both paths coexist for the comparison. The unit tests here pin
each decider's answer against expected values derived from the shell's logic in the meantime.
"""
import argparse
import json
import os
import sys

import circuit_breaker
import panel_tally
import review_memory
import review_round_policy

SCHEMA_VERSION = 1
BLOCKING = {"Critical", "Important"}
_VERIFY_OK = {"pass", "skipped"}
# The breaker's recurring-finding / challenged-principle detail joins ALL recurring blocking class
# keys ("; ".join(sorted(keys))) — unbounded in the finding count. It rides both the answer's
# `reason` (on a breaker halt) and `breaker.detail`, so an N-class recurrence would grow the answer
# ~N × a clamped title, re-creating the #211 scaled-courier-payload class on the one verdict that
# most needs to reach the shell intact. Bound it in the ANSWER here (never in the shared twin, which
# other legs read in memory): the machine-readable `breaker.reason` code stays intact; the full id
# list stays on disk for the readout. The shell twin gets the matching clamp in PR-2 for parity.
_MAX_REASON = 480


def _clamp_reason(text):
    s = "" if text is None else str(text)
    if len(s) <= _MAX_REASON:
        return s
    return s[:_MAX_REASON].rstrip() + " …(truncated)"


# ── faithful ports of the shell's in-memory record consumers (Phase-0 census) ──
def _resume_round(records):
    """review_panel_shell.resumeRound — the next round to run = max persisted round + 1."""
    best = 0
    for rec in records or []:
        if not isinstance(rec, dict):
            continue
        try:
            n = int(rec.get("round"))
        except (TypeError, ValueError):
            continue
        if n > best:
            best = n
    return best + 1


def _previous_dimension_state(records):
    """review_panel_shell.buildPreviousDimensionState — fold every round's dimensions, later
    rounds overwriting earlier, into the `previous` map plan_round consumes."""
    previous = {}
    for rec in records or []:
        dims = rec.get("dimensions") if isinstance(rec, dict) else None
        if not isinstance(dims, dict):
            continue
        for name, dim in dims.items():
            previous[name] = dim
    return previous


def _carry_forward_dimension(records, name, carried_from_round):
    """review_panel_shell.carryForwardDimension — the most recent prior state for a skipped
    dimension, stamped skipped. Missing → a low-confidence empty skip."""
    for rec in reversed(records or []):
        dims = rec.get("dimensions") if isinstance(rec, dict) else None
        if isinstance(dims, dict) and isinstance(dims.get(name), dict):
            out = dict(dims[name])
            out["status"] = "skipped"
            out["carriedFromRound"] = carried_from_round
            return out
    return {"status": "skipped", "findings": [], "confidence": "low",
            "carriedFromRound": carried_from_round}


def _surfaced_blocking_severities(record):
    """review_panel_shell.surfacedBlockingSeverities — the NEW (non-carried) blocking severities
    a round surfaced."""
    if not isinstance(record, dict):
        return []
    findings = record.get("findings")
    if not isinstance(findings, list):
        return []
    return [f.get("severity") for f in findings
            if isinstance(f, dict) and f.get("severity") in BLOCKING]


def _confirmation_qualifies(record):
    """review_panel_shell.confirmationQualifies — a confirmation is a qualifying FULL panel only
    when every dimension ran FRESH at reviewer-deep with high confidence (#167 invariant)."""
    dims = record.get("dimensions") if isinstance(record, dict) else None
    if not isinstance(dims, dict) or not dims:
        return False
    return all(isinstance(d, dict) and d.get("status") == "run"
               and d.get("confidence") == "high" and d.get("tier") == "reviewer-deep"
               for d in dims.values())


def _rework_across(records):
    """review_panel_shell.reworkAcross — union of changedSubjects across records; any
    missing/non-array surface is unknown → None → cross-cutting (fail toward one more panel)."""
    out = []
    for rec in records or []:
        cs = rec.get("changedSubjects") if isinstance(rec, dict) else None
        if not isinstance(cs, list):
            return None
        out.extend(cs)
    return out


def _panel_window(records):
    """review_panel_shell.panelWindow — the qualifying confirmation panels and every record from
    the last one onward (findings/rework since the last panel land on THOSE rounds' records)."""
    allr = [r for r in (records or []) if isinstance(r, dict)]
    qualifying = [r for r in allr if r.get("kind") == "confirmation" and _confirmation_qualifies(r)]
    if not qualifying:
        return qualifying, []
    try:
        last_round = int(qualifying[-1].get("round") or 0)
    except (TypeError, ValueError):
        last_round = 0

    def _round_no(rec):
        try:
            return int(rec.get("round") or 0)
        except (TypeError, ValueError):
            return 0
    since = [r for r in allr if _round_no(r) >= last_round]
    return qualifying, since


def _further_confirmation_owed(records):
    """review_panel_shell.furtherConfirmationOwed — is a FURTHER full confirmation still owed?
    Before any qualifying panel the mandatory first one is owed; after, the #174 economics decide
    (Critical or cross-cutting under the cap re-arms; Critical at the cap parks)."""
    qualifying, since = _panel_window(records)
    if not qualifying:
        return {"owed": True, "park": False, "panels": 0}
    surfaced = []
    for rec in since:
        surfaced.extend(_surfaced_blocking_severities(rec))
    followup = review_round_policy.confirmation_followup(
        surfaced, len(qualifying), review_round_policy.is_cross_cutting(_rework_across(since)))
    return {"owed": followup["rearm"], "park": followup["park"],
            "panels": len(qualifying), "reason": followup["reason"]}


def _certification_summary(records):
    """review_panel_shell.certificationSummary — how many QUALIFYING full panels ran and whether
    any blocking finding surfaced since the last one (resolved by scoped verify, #174 req 4)."""
    qualifying, since = _panel_window(records)
    return {"fullPanels": len(qualifying),
            "lastPanelSurfacedResolved": any(len(_surfaced_blocking_severities(r)) > 0 for r in since)}


def _confirmation_ready(records, round_no, just_marked):
    """review_panel_shell.confirmationReady — whether THIS round is the full confirmation panel.

    `just_marked` is the shell's loop-local truth that a fix marked confirmation THIS iteration:
    it distinguishes the within-run mandatory intermediate re-review (round marked+1, cheap) from
    a resume that ended right after marking (enter the owed panel immediately). Disk state alone
    cannot tell them apart — both show the marker on round N and no record for N+1 — so the shell
    passes it explicitly. Every other input is read from disk."""
    if just_marked:
        return False
    marked = [r for r in (records or []) if isinstance(r, dict) and r.get("confirmationPending")]
    if not marked:
        return False
    if not _further_confirmation_owed(records)["owed"]:
        return False

    def _round_no(rec):
        try:
            return int(rec.get("round") or 0)
        except (TypeError, ValueError):
            return 0
    marked_round = max(_round_no(r) for r in marked)
    has_intermediate_after = any(_round_no(r) > marked_round for r in (records or []) if isinstance(r, dict))
    if not has_intermediate_after:
        return True
    return round_no > marked_round + 1


def _content_hash(text):
    return review_memory.content_hash(text)


def _load_records(path, dimensions):
    """Load the durable round-records skeletons via the shared loader (schema-v1 promotion +
    contentHash included). A load failure is surfaced to the caller to fail closed."""
    return review_memory.load_records_state(path, dimensions or [])


def _load_deferred_set(path):
    """review_panel_shell.loadDeferredSet — a missing/corrupt/odd-shaped deferred set reads as {}
    (advisory skip-set; record_deferred.py is the authoritative write path)."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _assemble_rounds(records, deferred_set):
    """review_panel_shell.assembleRounds — prior rounds shaped for the breaker, deferred findings
    removed so a deferral never counts toward recurrence or progress."""
    skip = set((deferred_set or {}).keys())
    out = []
    for rec in records or []:
        if not isinstance(rec, dict):
            continue
        findings = [f for f in (rec.get("findings") or [])
                    if circuit_breaker.finding_identity(f) not in skip]
        try:
            rnd = int(rec.get("round"))
        except (TypeError, ValueError):
            rnd = rec.get("round")
        out.append({"round": rnd, "findings": findings,
                    "dimensions": rec.get("dimensions"),
                    "coverageDecisions": rec.get("coverageDecisions")})
    out.sort(key=lambda r: r["round"] if isinstance(r.get("round"), int) else 0)
    return out


def _breaker_round_dimensions(dimensions):
    """review_panel_shell._breakerRoundDimensions — {name: {status}} from a round's dimensions."""
    out = {}
    for name, result in (dimensions or {}).items():
        if not isinstance(result, dict):
            continue
        out[name] = {"status": result.get("status") or "run"}
    return out


# ── argparse helpers ──
def _json_arg(value, default):
    if value is None:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _record_for_round(records, round_no):
    for rec in records or []:
        if isinstance(rec, dict) and rec.get("round") == round_no:
            return rec
    return None


# ── decider: entry-bootstrap (evolve #199) — the resume DECISION only ──
def entry_bootstrap(path, dimensions, extras_path=None):
    """The resume seam: read the durable records and answer only the resume DECISION — the round
    to run next, the CAS content hash, the last-round extras, and the confirmation-marker state —
    never stub records or findings (the #193 stub shape is retired). A load failure fails closed
    (ok:false) exactly as the shell's loadRoundRecords does; the caller cannot-certify."""
    state = _load_records(path, dimensions)
    if not state.get("ok"):
        return {"ok": False, "state": state.get("state", "unreadable"),
                "reason": state.get("reason") or "round-memory-unreadable",
                "contentHash": state.get("contentHash")}
    records = state.get("records") or []
    extras = None
    if extras_path:
        try:
            with open(extras_path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            extras = loaded if isinstance(loaded, dict) else None
        except (OSError, ValueError):
            extras = None
    marked = [r for r in records if isinstance(r, dict) and r.get("confirmationPending")]

    def _round_no(rec):
        try:
            return int(rec.get("round") or 0)
        except (TypeError, ValueError):
            return 0
    marked_round = max((_round_no(r) for r in marked), default=None)
    return {
        "ok": True,
        "state": state.get("state", "loaded"),
        "round": _resume_round(records),
        "contentHash": state.get("contentHash"),
        "extras": extras,
        "confirmationPending": bool(marked),
        "markedRound": marked_round,
        "roundCount": len(records),
    }


# ── decider: plan-round — the per-dimension schedule for the round about to run ──
def plan_round_decider(path, round_no, dimensions, changed_subjects, just_marked):
    """Answer the next round's schedule: whether it is the full confirmation panel, the run/skip/
    tier per dimension (via the plan_round twin over disk-read previous state), and the carried
    dimension state for each skip. Small, meaningful JSON — no findings beyond blocking-only
    carried skeletons. A load failure fails toward MORE review (run-all-deep, unknown surface)."""
    state = _load_records(path, dimensions)
    if not state.get("ok"):
        # Fail-closed direction: unreadable memory → run every dimension deep, no confirmation.
        return {
            "ok": True,
            "round": round_no,
            "roundKind": "intermediate",
            "enterConfirmation": False,
            "escalationPolicy": "deep-only",
            "memoryUnreadable": True,
            "dimensions": {d: {"action": "run", "tier": "reviewer-deep",
                               "reason": "round memory unreadable — run-all-deep"}
                           for d in (dimensions or [])},
            "carried": {},
        }
    records = state.get("records") or []
    enter_confirmation = _confirmation_ready(records, round_no, just_marked)
    plan = review_round_policy.plan_round({
        "round": round_no,
        "dimensions": dimensions or [],
        "changedSubjects": changed_subjects,
        "previous": _previous_dimension_state(records),
        "confirmation": enter_confirmation,
    })
    scheduled = plan.get("dimensions") or {}
    carried = {}
    for name, sched in scheduled.items():
        if isinstance(sched, dict) and sched.get("action") == "skip":
            carried[name] = _carry_forward_dimension(records, name, sched.get("carriedFromRound"))
    return {
        "ok": True,
        "round": round_no,
        "roundKind": plan.get("roundKind"),
        "enterConfirmation": enter_confirmation,
        "escalationPolicy": plan.get("escalationPolicy"),
        "dimensions": scheduled,
        "carried": carried,
    }


# ── decider: tally-round — the verdict, from disk + two ride-down scalars ──
def tally_round_decider(path, round_no, roster, max_rounds, gate, confidence, missing,
                        present_blocking, deferred_path, fix_status, verify_result,
                        enter_confirmation):
    """Answer the loop terminal: run the breaker over the durable rounds, apply the terminal
    precedence (`panel_tally.decide_terminal`), fold in the #174 confirmation-bar economics, and
    attach the honest certification summary on a certifying terminal. The gate + present-blocking
    ride down as scalars (see module docstring); everything else is read from disk. No findings in
    the answer. A missing roster or an exception fails closed (halted / cannot-certify)."""
    safe_missing = missing if isinstance(missing, list) else []
    if not roster:
        return {"ok": True, "schemaVersion": SCHEMA_VERSION, "terminal": "cannot-certify",
                "gate": "cannot-certify", "confidence": "low", "round": round_no,
                "missing": [], "breaker": {"halt": False},
                "reason": "empty reviewer set — nothing to certify"}
    state = _load_records(path, roster)
    if not state.get("ok"):
        return {"ok": True, "schemaVersion": SCHEMA_VERSION, "terminal": "cannot-certify",
                "gate": "cannot-certify", "confidence": "low", "round": round_no,
                "missing": safe_missing, "breaker": {"halt": False},
                "reason": "round-memory-" + (state.get("state") or "unreadable")}
    try:
        records = state.get("records") or []
        current = _record_for_round(records, round_no) or {}
        deferred_set = _load_deferred_set(deferred_path) if deferred_path else {}
        skip = set(deferred_set.keys())

        current_findings = [f for f in (current.get("findings") or [])
                            if isinstance(f, dict)]
        pdef = panel_tally.present_deferred(current_findings, deferred_set)

        prior = [r for r in _assemble_rounds(records, deferred_set)
                 if r.get("round") != round_no]
        prior_records = [r for r in records if isinstance(r, dict) and r.get("round") != round_no]
        coverage_decisions = current.get("coverageDecisions") or []
        this_round = {
            "round": round_no,
            "findings": [f for f in current_findings
                         if circuit_breaker.finding_identity(f) not in skip],
            "dimensions": _breaker_round_dimensions(current.get("dimensions")),
            "coverageDecisions": coverage_decisions,
            "generalizeRequired": review_memory.recurrent_classes(prior_records, coverage_decisions),
        }
        brk = circuit_breaker.check_circuit_breaker(prior + [this_round], max_rounds)
        breaker_halt = bool(brk.get("halt"))

        terminal, reason = panel_tally.decide_terminal(
            gate, present_blocking, pdef, fix_status, round_no, max_rounds, breaker_halt)
        if terminal == "halted" and breaker_halt and brk.get("detail"):
            reason = _clamp_reason(brk["detail"])
        if terminal in ("clean", "clean-with-skips") and verify_result is not None \
                and verify_result not in _VERIFY_OK:
            terminal = "halted"
            reason = ("verify command timed out — cannot certify clean"
                      if verify_result == "timeout"
                      else "verify command failed — cannot certify clean")
        if terminal == "cannot-certify" and safe_missing:
            reason = "coverage incomplete — missing review angle(s): " + ", ".join(safe_missing)

        marked_pending = any(isinstance(r, dict) and r.get("confirmationPending") for r in records)
        if terminal in ("clean", "clean-with-skips") and marked_pending and not enter_confirmation:
            owe = _further_confirmation_owed(records)
            if owe.get("park"):
                terminal = "halted"
                reason = owe.get("reason") or \
                    "Critical surfaced at the confirmation-panel cap — certification withheld"
            elif owe.get("owed"):
                terminal = "continue"
                reason = "awaiting final confirmation round"

        out = {
            "ok": True,
            "schemaVersion": SCHEMA_VERSION,
            "terminal": terminal,
            "reason": reason,
            "gate": gate,
            "confidence": confidence,
            "round": round_no,
            "missing": safe_missing,
            "presentBlocking": present_blocking,
            "presentDeferred": pdef,
            "breaker": {"halt": breaker_halt, "reason": brk.get("reason"),
                        "detail": _clamp_reason(brk.get("detail"))},
        }
        if terminal in ("clean", "clean-with-skips"):
            out["certification"] = _certification_summary(records)
        return out
    except Exception as exc:  # noqa: BLE001 — fail closed on any tally error, like the shell's catch
        return {"ok": True, "schemaVersion": SCHEMA_VERSION, "terminal": "halted",
                "gate": "cannot-certify", "confidence": "low", "round": round_no,
                "missing": safe_missing, "breaker": {"halt": False},
                "reason": "tally failed: " + str(exc)}


# ── decider: compose-fix-context — write the worklist, answer a pointer ──
def compose_fix_context(records_path, current_findings_path, coverage_path, coverage_mode,
                        round_no, dimensions, out_path):
    """Write the fixer's worklist to a runDir FILE and answer only {ok, path, bytes, sha256}.

    Content flows disk → the fixer's Read, never through a courier answer. The worklist mirrors
    `review_panel_shell.buildFixContext`: prior rounds' blocking-skeleton findings (from the
    durable records — the #193 hybrid already drops non-blocking prior findings, decision-neutral)
    PLUS this round's FULL findings (the shell staged the live reviewer answer down to
    `current_findings_path`), the classKeys, the recurrence-derived generalizeRequired, the union
    of changedSubjects, and the coverage decisions. A load failure fails closed (ok:false)."""
    state = _load_records(records_path, dimensions)
    if not state.get("ok"):
        return {"ok": False, "reason": state.get("reason") or "round-memory-unreadable"}
    records = state.get("records") or []

    coverage_decisions = []
    if coverage_path:
        try:
            import coverage_decisions as cov
            loaded = cov.load_decisions(coverage_path, coverage_mode or "code")
            if loaded.get("ok"):
                coverage_decisions = loaded.get("decisions") or []
        except Exception:  # noqa: BLE001 — coverage context is best-effort worklist enrichment
            coverage_decisions = []

    prior_findings = []
    changed_subjects = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if rec.get("round") == round_no:
            continue  # this round's full findings come from the staged file below
        for f in rec.get("findings") or []:
            if isinstance(f, dict):
                prior_findings.append(f)
        cs = rec.get("changedSubjects")
        if isinstance(cs, list):
            changed_subjects.extend(cs)

    current_findings = []
    if current_findings_path:
        try:
            with open(current_findings_path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, list):
                current_findings = [f for f in loaded if isinstance(f, dict)]
            elif isinstance(loaded, dict) and isinstance(loaded.get("findings"), list):
                current_findings = [f for f in loaded["findings"] if isinstance(f, dict)]
        except (OSError, ValueError):
            current_findings = []

    all_findings = prior_findings + current_findings
    worklist = {
        "schemaVersion": SCHEMA_VERSION,
        "round": round_no,
        "priorFindings": all_findings,
        "classKeys": [f.get("classKey") or review_memory.class_key(f) for f in all_findings],
        "generalizeRequired": review_memory.recurrent_classes(records, coverage_decisions),
        # insertion-order dedupe, matching the shell's Array.from(new Set(changedSubjects))
        "changedSubjects": list(dict.fromkeys(changed_subjects)),
        "coverageDecisions": coverage_decisions,
    }
    text = json.dumps(worklist, sort_keys=True)
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        tmp = out_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, out_path)
    except OSError as exc:
        return {"ok": False, "reason": "fix-context-write-failed: " + str(exc)}
    return {"ok": True, "path": out_path, "bytes": len(text.encode("utf-8")),
            "sha256": _content_hash(text)}


def _build_parser():
    p = argparse.ArgumentParser(description="Showrunner review-panel deciders (#211).")
    sub = p.add_subparsers(dest="cmd", required=True)

    eb = sub.add_parser("entry-bootstrap")
    eb.add_argument("--path", required=True)
    eb.add_argument("--dimensions", default="[]")
    eb.add_argument("--extras-path", default=None)

    pr = sub.add_parser("plan-round")
    pr.add_argument("--path", required=True)
    pr.add_argument("--round", required=True, type=int)
    pr.add_argument("--dimensions", default="[]")
    pr.add_argument("--changed-subjects", default=None,
                    help="JSON array of changed subjects; omit for unknown (run-all-deep)")
    pr.add_argument("--just-marked", action="store_true",
                    help="a fix marked confirmation THIS shell iteration (loop-local truth)")

    tr = sub.add_parser("tally-round")
    tr.add_argument("--path", required=True)
    tr.add_argument("--round", required=True, type=int)
    tr.add_argument("--roster", default="[]")
    tr.add_argument("--max-rounds", type=int, default=7)
    tr.add_argument("--gate", required=True)
    tr.add_argument("--confidence", required=True)
    tr.add_argument("--missing", default="[]")
    tr.add_argument("--present-blocking", type=int, default=0)
    tr.add_argument("--deferred-path", default=None)
    tr.add_argument("--fix-status", default="completed")
    tr.add_argument("--verify-result", default=None)
    tr.add_argument("--enter-confirmation", action="store_true")

    fc = sub.add_parser("compose-fix-context")
    fc.add_argument("--records-path", required=True)
    fc.add_argument("--current-findings-path", default=None)
    fc.add_argument("--coverage-path", default=None)
    fc.add_argument("--coverage-mode", default="code")
    fc.add_argument("--round", required=True, type=int)
    fc.add_argument("--dimensions", default="[]")
    fc.add_argument("--out-path", required=True)
    return p


def main(argv):
    args = _build_parser().parse_args(argv[1:])
    if args.cmd == "entry-bootstrap":
        result = entry_bootstrap(args.path, _json_arg(args.dimensions, []), args.extras_path)
    elif args.cmd == "plan-round":
        result = plan_round_decider(
            args.path, args.round, _json_arg(args.dimensions, []),
            _json_arg(args.changed_subjects, None) if args.changed_subjects is not None else None,
            args.just_marked)
    elif args.cmd == "tally-round":
        result = tally_round_decider(
            args.path, args.round, _json_arg(args.roster, []), args.max_rounds,
            args.gate, args.confidence, _json_arg(args.missing, []),
            args.present_blocking, args.deferred_path, args.fix_status,
            args.verify_result, args.enter_confirmation)
    elif args.cmd == "compose-fix-context":
        result = compose_fix_context(
            args.records_path, args.current_findings_path, args.coverage_path,
            args.coverage_mode, args.round, _json_arg(args.dimensions, []), args.out_path)
    else:  # pragma: no cover — argparse `required=True` forbids this
        sys.stderr.write("unknown command\n")
        return 2
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
