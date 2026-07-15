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
today. These deciders were ported faithfully from the shell's old in-memory record consumers (the
#211 Phase-0 census: `resumeRound`, `buildPreviousDimensionState`, `carryForwardDimension`,
`confirmationReady`, `panelWindow`/`furtherConfirmationOwed`/`certificationSummary`,
`assembleRounds`→breaker, `buildFixContext`), reading the record content from disk instead of an
in-memory copy. Those shell consumers are gone — the deciders are now the ONLY decision path.

Three scalars ride DOWN from the shell as command args because they are *decisions the shell must
compute at the moment the reviewer answers arrive*, not content:
  - the **gate** (clean/blocking/cannot-certify + confidence + missing[]) — the durable skeleton
    strips each dim's `verificationReceipt`, so the confirmation-round gate cannot be faithfully
    recomputed from disk; the shell computes it from the live answers (receipts present) and
    discards the findings immediately after persisting them down.
  - **present-blocking** — the count of current (non-carried) blocking findings, likewise from
    the live answers.
  - the **uncertified reason** (#212) — the named cannot-certify reason (seat + defect class) from
    `panel_tally.uncertified_reason` over the live per-seat results; the receipt-missing/stale/
    malformed flags it needs are stripped from the skeleton, so it too rides down.
Everything else (breaker, terminal, confirmation follow-up, certification) the deciders compute
from disk. Every fail-closed path in the shell stays fail-closed here.

Two folds keep the round to ONE new courier leaf (#118): plan-round optionally folds the per-round
coverage read (`--coverage-path`), and tally-round folds the fix-context compose (`--worklist-out-
path`) so the fixer worklist is written to disk here and only its pointer rides back.

These deciders are LIVE (#211 landed across three stacked PRs: deciders → shell cutover → this
fallback-hardening + cleanup). The shell dispatches reviewers and persists their answers down, then
asks the deciders "what now?" and receives small meaningful JSON — never findings. Their answers are
pinned by the unit tests here (against expected values derived from the shell's logic), the
parity fixtures, and the adversarial + scaling smokes. The transitional decider ≡ shell equivalence
smoke that guarded the port while both paths coexisted was removed once the decider path became the
only path.
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
# #276/#291: the blocking partition routes through circuit_breaker.is_blocking (case-normalized,
# fail-closed) — no local blocking set to drift.
_VERIFY_OK = {"pass", "skipped"}
# The breaker's recurring-finding / challenged-principle detail joins ALL recurring blocking class
# keys ("; ".join(sorted(keys))) — unbounded in the finding count. It rides both the answer's
# `reason` (on a breaker halt) and `breaker.detail`, so an N-class recurrence would grow the answer
# ~N × a clamped title, re-creating the #211 scaled-courier-payload class on the one verdict that
# most needs to reach the shell intact. Bound it in the ANSWER here (never in the shared twin, which
# other legs read in memory): the machine-readable `breaker.reason` code stays intact; the full id
# list stays on disk for the readout. The shell twin gets the matching clamp in PR-2 for parity.
_MAX_REASON = 480
# #279 honest verify-fail park reason: the untrusted verify-gate output head clamped at this sink
# (the reason flows into journal entries + readouts, so the clamp lives where the tail enters them).
_MAX_VERIFY_TAIL = 160


def _clamp_reason(text):
    s = "" if text is None else str(text)
    if len(s) <= _MAX_REASON:
        return s
    return s[:_MAX_REASON].rstrip() + " …(truncated)"


def _verify_tail(records_path, round_no):
    """A clamped, single-line head of the round's verify-gate output, for the #279 honest park reason.
    `records_path` is round-records.json; the verify result sits beside it as verify-result-r{N}.json
    ({"result","code","tail"}, written by verify_gate.py). The stored tail is already the LAST ~2000
    chars of the run's output, and test runners (jest/vitest/pytest) print the failure summary + error
    LAST — so keep the END of the tail, not the head (the head is lead-in progress noise). The tail is
    untrusted subprocess output, so collapse whitespace and clamp to _MAX_VERIFY_TAIL here at the sink.
    Fail-soft to '' — a missing or garbled verify file must never break the tally; the reason still
    parks, just without the breadcrumb."""
    try:
        beside = os.path.join(os.path.dirname(records_path),
                              "verify-result-r%d.json" % round_no)
        with open(beside, encoding="utf-8") as fh:
            tail = json.load(fh).get("tail")
        if not isinstance(tail, str):
            return ""
        collapsed = " ".join(tail.split())
        if len(collapsed) <= _MAX_VERIFY_TAIL:
            return collapsed
        return "…" + collapsed[-_MAX_VERIFY_TAIL:].lstrip()
    except Exception:  # noqa: BLE001 — a missing/garbled verify file must not break the tally
        return ""


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
    # #276/#291: route the blocking partition through the shared fail-closed predicate so a mis-cased
    # blocker (e.g. lowercase `critical`) reaches the surfaced list — the confirmation gate's
    # case-normalized Critical match then parks on it (was case-sensitive `in BLOCKING`, which dropped it).
    return [f.get("severity") for f in findings
            if isinstance(f, dict) and circuit_breaker.is_blocking(f.get("severity"))]


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


def _further_confirmation_owed(records, doc_mode=False):
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
        surfaced, len(qualifying), review_round_policy.is_cross_cutting(_rework_across(since)),
        doc_mode=doc_mode)
    return {"owed": followup["rearm"], "park": followup["park"],
            "panels": len(qualifying), "reason": followup["reason"]}


def _certification_summary(records):
    """review_panel_shell.certificationSummary — how many QUALIFYING full panels ran and whether
    any blocking finding surfaced since the last one (resolved by scoped verify, #174 req 4)."""
    qualifying, since = _panel_window(records)
    return {"fullPanels": len(qualifying),
            "lastPanelSurfacedResolved": any(len(_surfaced_blocking_severities(r)) > 0 for r in since)}


def _confirmation_ready(records, round_no, just_marked, doc_mode=False):
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
    if not _further_confirmation_owed(records, doc_mode=doc_mode)["owed"]:
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


def _latest_coverage_ids(records):
    """review_panel_shell's confirmation coverage-marker check reads the LATEST record's coverage
    decision ids (`records[records.length-1].coverageDecisions` → ids). The durable skeleton keeps
    coverageDecisions, so the plan decider surfaces this small scalar list for the shell to verify
    against the live coverage read (a decision lost between marking and confirmation → park)."""
    latest = None
    best = None
    for rec in records or []:
        if not isinstance(rec, dict):
            continue
        try:
            n = int(rec.get("round") or 0)
        except (TypeError, ValueError):
            n = 0
        if best is None or n >= best:
            best = n
            latest = rec
    ids = []
    for d in ((latest or {}).get("coverageDecisions") or []):
        if isinstance(d, dict) and d.get("id"):
            ids.append(d["id"])
    return ids


def _load_coverage_state(coverage_path, coverage_mode):
    """Fold the loop's per-round coverage read (coverage_decisions.load_decisions — decisions + the
    fence hash over the exact on-disk bytes, Python-side) into a plan-round answer so the round-entry
    read is ONE leaf (plan + coverage), not two (#118). Fail-closed shape is preserved verbatim so the
    shell parks on it exactly as it does on a standalone coverage-load helper."""
    try:
        import coverage_decisions as cov
        return cov.load_decisions(coverage_path, coverage_mode or "code")
    except Exception as exc:  # noqa: BLE001 — an unreadable coverage read fails closed like the helper
        return {"ok": False, "state": "unreadable", "reason": "coverage-load-failed: " + str(exc)}


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
def plan_round_decider(path, round_no, dimensions, changed_subjects, just_marked,
                       coverage_path=None, coverage_mode="code", doc_mode=False):
    """Answer the next round's schedule: whether it is the full confirmation panel, the run/skip/
    tier per dimension (via the plan_round twin over disk-read previous state), and the carried
    dimension state for each skip. Small, meaningful JSON — the carried dimension state carries NO
    findings: `plan_round` skips a dimension only when it is high-confidence AND has no findings
    (review_round_policy.plan_round), so a carried dim is structurally CLEAN and `carried[name]
    ["findings"]` is always empty. That is what keeps this answer O(1) — if the skip policy ever
    changed to skip dims WITH findings, the answer would silently start scaling with finding count,
    which the `carried[...]["findings"] == []` pin turns into a loud test failure. A load failure
    fails toward MORE review (run-all-deep, unknown surface).

    When `coverage_path` is given the per-round coverage read is FOLDED IN (#118): the answer carries
    `coverage` (decisions + fence hash, the coverage_decisions.load_decisions shape) so the shell's
    round-entry read is one leaf, not two. `latestCoverageDecisionIds` rides for the shell's
    confirmation coverage-marker check (a decision lost between marking and confirmation → park)."""
    coverage = _load_coverage_state(coverage_path, coverage_mode) if coverage_path else None
    state = _load_records(path, dimensions)
    if not state.get("ok"):
        # Fail-closed direction: unreadable memory → run every dimension deep, no confirmation.
        out = {
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
            "latestCoverageDecisionIds": [],
        }
        if coverage is not None:
            out["coverage"] = coverage
        return out
    records = state.get("records") or []
    enter_confirmation = _confirmation_ready(records, round_no, just_marked, doc_mode=doc_mode)
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
    out = {
        "ok": True,
        "round": round_no,
        "roundKind": plan.get("roundKind"),
        "enterConfirmation": enter_confirmation,
        "escalationPolicy": plan.get("escalationPolicy"),
        "dimensions": scheduled,
        "carried": carried,
        "latestCoverageDecisionIds": _latest_coverage_ids(records),
    }
    if coverage is not None:
        out["coverage"] = coverage
    return out


# ── decider: tally-round — the verdict, from disk + two ride-down scalars ──
def tally_round_decider(path, round_no, roster, max_rounds, gate, confidence, missing,
                        present_blocking, deferred_path, fix_status, verify_result,
                        enter_confirmation, uncertified_reason=None,
                        coverage_path=None, coverage_mode="code",
                        current_findings_path=None, worklist_out_path=None,
                        doc_mode=False):
    """Answer the loop terminal: run the breaker over the durable rounds, apply the terminal
    precedence (`panel_tally.decide_terminal`), fold in the #174 confirmation-bar economics, and
    attach the honest certification summary on a certifying terminal. The gate + present-blocking
    ride down as scalars (see module docstring); everything else is read from disk. No findings in
    the answer. A missing roster or an exception fails closed (halted / cannot-certify).

    Three more scalars ride DOWN because they are answer-time facts the durable skeleton can't hold:
      - `uncertified_reason` (#212): the NAMED cannot-certify reason (seat + defect class) computed
        by `panel_tally.uncertified_reason` over the LIVE per-seat results — the receipt-missing/stale/
        malformed flags are stripped from the skeleton, so it can't be recomputed from disk. Preferred
        over the missing-angle fallback; and a `cannot-certify` GATE rides the `uncertified` flag even
        when the round routes to the fix leg (terminal continue), exactly like the shell's #215 tally.
    And the fix-context compose is FOLDED into this leaf (#118): when the terminal is `continue` and
    `worklist_out_path` is given, the worklist is written to disk here (compose_fix_context) and only
    its POINTER (`worklistPath`) rides back — the fixer reads the findings from the file."""
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
        # #211 parity: the CURRENT round's breaker + present-deferred view is the synthesis-VERIFIED
        # set (the OLD shell's `compiled`) — drop findings synthesis could not verify (no keep verdict,
        # flagged `synthesisUnverified` at graft). Prior rounds + recurrence keep the full record
        # (unfiltered below), preserving the #174 generalize-grace's current=compiled / prior=record
        # asymmetry the OLD in-memory tally relied on.
        verified_current = [f for f in current_findings if not f.get("synthesisUnverified")]
        pdef = panel_tally.present_deferred(verified_current, deferred_set)

        prior = [r for r in _assemble_rounds(records, deferred_set)
                 if r.get("round") != round_no]
        prior_records = [r for r in records if isinstance(r, dict) and r.get("round") != round_no]
        coverage_decisions = current.get("coverageDecisions") or []
        this_round = {
            "round": round_no,
            "findings": [f for f in verified_current
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
            # #279 honest reason: name the failing stage + round + the verify error head, so the park
            # says WHICH gate failed (verify vs findings) and WHY, instead of a bare "halted".
            stage = "verify timed out" if verify_result == "timeout" else "verify failed"
            detail = _verify_tail(path, round_no)
            reason = ("%s r%d: %s" % (stage, round_no, detail) if detail
                      else "%s r%d — cannot certify clean" % (stage, round_no))
        if terminal == "cannot-certify":
            # #212 honest reason: the NAMED per-seat defect class (ridden down from the live results)
            # is preferred; the old missing-angle enrichment is the fallback when no seat classified.
            if uncertified_reason:
                reason = uncertified_reason
            elif safe_missing:
                reason = "coverage incomplete — missing review angle(s): " + ", ".join(safe_missing)

        marked_pending = any(isinstance(r, dict) and r.get("confirmationPending") for r in records)
        if terminal in ("clean", "clean-with-skips") and marked_pending and not enter_confirmation:
            owe = _further_confirmation_owed(records, doc_mode=doc_mode)
            if owe.get("park"):
                terminal = "halted"
                reason = owe.get("reason") or \
                    "Critical surfaced at the confirmation-panel cap — certification withheld"
            elif owe.get("owed"):
                terminal = "continue"
                reason = "awaiting final confirmation round"

        # #381 STRUCTURED cap-halt discriminator. The caller (build_phase's whole-branch final-review
        # gate) routes on this field, NEVER on the prose reason. Computed here at the verdict-assembly
        # site from the same structured inputs the terminal decision used — no prose regexing.
        #   'round-cap'  — the finding-churn cap: the breaker's max-iterations halt (round cap reached
        #                  with blockers still present) with verify NOT red AND the round CERTIFIED
        #                  (gate blocking + confidence high — never cannot-certify). This is the ONLY
        #                  halt kind the caller acts on instead of parking: build_phase dispatches its
        #                  ONE fix pass + a post-fix verify, and only when both land green hands off to
        #                  review-code (the stronger branch gate) — otherwise it downgrades the kind
        #                  to 'fix-failed'/'verify-fail' and parks. An uncertified cap halt is 'other'.
        #   'verify-fail'— verify went red (fail/timeout). A blocking round with a red verify halts via
        #                  the breaker WITHOUT tripping the clean→halted verify override above, so it is
        #                  classified explicitly here — the cap-halt proceed path must never swallow a
        #                  red verify (#381 fail-closed guard).
        #   'fix-failed' — the fix step did not complete.
        #   'other'      — breaker recurrence / no-net-progress / challenged-principle, confirmation-panel
        #                  cap park, or any fail-closed halt. All park.
        verify_red = verify_result is not None and verify_result not in _VERIFY_OK
        halt_kind = None
        if terminal == "halted":
            if verify_red:
                halt_kind = "verify-fail"
            elif fix_status == "failed":
                halt_kind = "fix-failed"
            elif breaker_halt and brk.get("reason") == "max-iterations":
                # #381: only a CERTIFIED blocking cap is the handoff kind — an uncertified/cannot-certify
                # gate parks regardless (the uncertified flag rides the verdict for the consumer guard).
                halt_kind = ("round-cap" if gate == "blocking" and confidence == "high"
                             else "other")
            else:
                halt_kind = "other"

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
        # #381 structured cap-halt discriminator (additive; the shell copies it onto the verdict).
        if halt_kind is not None:
            out["haltKind"] = halt_kind
        # #212 uncertified flag: a cannot-certify GATE rides the verdict even when this round routes
        # to the fix leg (terminal continue) — the readout/phase layer sees the coverage gap while
        # fixes land. Mirrors review_panel_shell.tallyRound's `if (gate === 'cannot-certify')`.
        if gate == "cannot-certify":
            out["uncertified"] = True
        # #118 fix-context fold: on a continue terminal, write the fixer worklist to disk here and
        # ride only its pointer back. A compose failure fails closed (worklistPath null + reason) —
        # the shell parks rather than dispatch a fixer with no worklist.
        if terminal == "continue" and worklist_out_path:
            fc = compose_fix_context(path, current_findings_path, coverage_path, coverage_mode,
                                     round_no, roster, worklist_out_path, doc_mode=doc_mode)
            if fc.get("ok"):
                out["worklistPath"] = fc.get("path")
                out["worklistBytes"] = fc.get("bytes")
                out["worklistSha256"] = fc.get("sha256")
            else:
                out["worklistPath"] = None
                out["worklistReason"] = fc.get("reason") or "fix-context-write-failed"
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
                        round_no, dimensions, out_path, doc_mode=False):
    """Write the fixer's worklist to a runDir FILE and answer only {ok, path, bytes, sha256}.

    Content flows disk → the fixer's Read, never through a courier answer. The worklist mirrors
    `review_panel_shell.buildFixContext`. Its `findings` array holds, in round order, every round's
    findings (all severities). When `current_findings_path` is given the current round's rows are the
    FULL-bodied staged answer (evidence carried); otherwise — the folded tally-round path, which
    writes NO large body down — every round including the current one is the durable SKELETON
    (file/line/title/severity/classKey survive; evidence BODIES stripped). Either way classKeys are
    preserved, so classKeys/generalizeRequired stay faithful and the fixer has the location + severity
    of every blocking finding (it reads the code detail itself via Read/Edit). The list is named
    `findings`, not `priorFindings`, because it holds the current round too. Alongside: the classKeys
    over all of them, the recurrence-derived generalizeRequired, the union of changedSubjects, and the
    coverage decisions. A load failure fails closed (ok:false)."""
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

    # When the caller staged this round's FULL-bodied findings to a file (current_findings_path),
    # the current round is taken from there and skipped in the on-disk records. When it did NOT
    # (the folded tally-round path — no large body-write crosses down), the current round's durable
    # SKELETON stands in: file/line/title/severity/classKey survive skeletonization, which is what
    # a fixer needs to locate and act (it has Read/Edit for the code detail). Either way changed
    # subjects fold over ALL rounds.
    have_current_file = bool(current_findings_path)
    prior_findings = []
    changed_subjects = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        cs = rec.get("changedSubjects")
        if isinstance(cs, list):
            changed_subjects.extend(cs)
        if have_current_file and rec.get("round") == round_no:
            continue  # this round's full-bodied findings come from the staged file below
        for f in rec.get("findings") or []:
            if isinstance(f, dict):
                prior_findings.append(f)

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

    if doc_mode:
        prior_findings = [f for f in prior_findings if circuit_breaker.is_blocking(f.get("severity"))]
        current_findings = [f for f in current_findings if circuit_breaker.is_blocking(f.get("severity"))]

    # round order: prior rounds' skeletons first, then this round's full-bodied findings.
    all_findings = prior_findings + current_findings
    worklist = {
        "schemaVersion": SCHEMA_VERSION,
        "round": round_no,
        "findings": all_findings,
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
    pr.add_argument("--coverage-path", default=None,
                    help="fold the per-round coverage read in (one round-entry leaf, #118)")
    pr.add_argument("--coverage-mode", default="code")
    pr.add_argument("--doc-mode", action="store_true")

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
    tr.add_argument("--uncertified-reason", default=None,
                    help="#212 named cannot-certify reason, computed from live per-seat results")
    tr.add_argument("--coverage-path", default=None)
    tr.add_argument("--coverage-mode", default="code")
    tr.add_argument("--current-findings-path", default=None,
                    help="optional staged full-bodied current findings for the folded fix-context")
    tr.add_argument("--worklist-out-path", default=None,
                    help="when set and terminal is continue, write the fixer worklist here (fold)")
    tr.add_argument("--doc-mode", action="store_true")

    fc = sub.add_parser("compose-fix-context")
    fc.add_argument("--records-path", required=True)
    fc.add_argument("--current-findings-path", default=None)
    fc.add_argument("--coverage-path", default=None)
    fc.add_argument("--coverage-mode", default="code")
    fc.add_argument("--round", required=True, type=int)
    fc.add_argument("--dimensions", default="[]")
    fc.add_argument("--out-path", required=True)
    fc.add_argument("--doc-mode", action="store_true")
    return p


def main(argv):
    args = _build_parser().parse_args(argv[1:])
    if args.cmd == "entry-bootstrap":
        result = entry_bootstrap(args.path, _json_arg(args.dimensions, []), args.extras_path)
    elif args.cmd == "plan-round":
        result = plan_round_decider(
            args.path, args.round, _json_arg(args.dimensions, []),
            _json_arg(args.changed_subjects, None) if args.changed_subjects is not None else None,
            args.just_marked, coverage_path=args.coverage_path, coverage_mode=args.coverage_mode,
            doc_mode=args.doc_mode)
    elif args.cmd == "tally-round":
        result = tally_round_decider(
            args.path, args.round, _json_arg(args.roster, []), args.max_rounds,
            args.gate, args.confidence, _json_arg(args.missing, []),
            args.present_blocking, args.deferred_path, args.fix_status,
            args.verify_result, args.enter_confirmation,
            uncertified_reason=args.uncertified_reason,
            coverage_path=args.coverage_path, coverage_mode=args.coverage_mode,
            current_findings_path=args.current_findings_path,
            worklist_out_path=args.worklist_out_path,
            doc_mode=args.doc_mode)
    elif args.cmd == "compose-fix-context":
        result = compose_fix_context(
            args.records_path, args.current_findings_path, args.coverage_path,
            args.coverage_mode, args.round, _json_arg(args.dimensions, []), args.out_path,
            doc_mode=args.doc_mode)
    else:  # pragma: no cover — argparse `required=True` forbids this
        sys.stderr.write("unknown command\n")
        return 2
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
