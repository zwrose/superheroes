#!/usr/bin/env python3
"""Deterministic per-round + loop-terminal tally for the review-panel Workflow pattern.

The single source of truth for the panel's per-round gate/confidence and the four loop
terminals. It layers the spec's normalized vocabulary (`clean` / `blocking` / `cannot-certify`;
loop terminals `continue` / `clean` / `clean-with-skips` / `cannot-certify` / `halted`) over the
REUSED libs: it imports `loop_state.decide` (the continue/clean/skip/halt accounting),
`circuit_breaker.finding_identity` (the `file::normalized_title` identity), and
`review_result.write_result` (the atomic durable record) UNCHANGED. Every terminal is decided
here, never in the JS shell; every read is fail-safe (a missing/malformed input biases to a
non-clean outcome, never a silent `clean`). stdlib only.
"""
import argparse
import json
import os
import sys

import circuit_breaker
import loop_state
import review_result
import re

SCHEMA_VERSION = 1
_ROUND_RE = re.compile(r"^round-(\d+)$")
_VERIFY_OK = (None, "pass", "skipped")  # None=doc leg; skipped=unverified project; pass=ok

BLOCKING = ("Critical", "Important")
SEV_RANK = {"Critical": 0, "Important": 1, "Minor": 2, "Nit": 3}


# ── run-key dir layout (panel_tally owns these; no scattered literals) ──
def round_dir(run_dir, rnd):
    return os.path.join(run_dir, "round-%d" % rnd)


def findings_path(run_dir, rnd, reviewer):
    return os.path.join(round_dir(run_dir, rnd), "findings-%s.json" % reviewer)


def verdict_path(run_dir, rnd):
    return os.path.join(round_dir(run_dir, rnd), "verdict.json")


def deferred_set_path(run_dir):
    return os.path.join(run_dir, "deferred-set.json")


def result_path(run_dir):
    return os.path.join(run_dir, "result.json")


def assemble_rounds(run_dir):
    """Build circuit_breaker's [{round, findings}] from the panel's own verdict.json records,
    excluding any identity in the run's deferred-set (mirrors load_rounds' skip-exclusion, but
    reads the panel layout — verdict.json/deferred-set.json — not compiled.json/resolutions.json)."""
    deferred = _safe_read_json(deferred_set_path(run_dir), {})
    skip = set(deferred.keys()) if isinstance(deferred, dict) else set()
    try:
        names = os.listdir(run_dir)
    except OSError:
        return []
    nums = []
    for name in names:
        m = _ROUND_RE.match(name)
        if m and os.path.isdir(os.path.join(run_dir, name)):
            nums.append(int(m.group(1)))
    nums.sort()
    rounds = []
    for n in nums:
        v = _safe_read_json(verdict_path(run_dir, n), None)
        if not isinstance(v, dict):
            continue
        findings = [f for f in v.get("findings", [])
                    if circuit_breaker.finding_identity(f) not in skip]
        rounds.append({"round": n, "findings": findings})
    return rounds


def resume_round(run_dir):
    """UFR-7: the round to (re)start at = max(N : round-N/verdict.json is valid JSON) + 1, or 1.
    A round is 'fully saved' iff its verdict.json exists and parses; a partial round (dir but no
    verdict) is discarded and re-run."""
    best = 0
    try:
        names = os.listdir(run_dir)
    except OSError:
        return 1
    for name in names:
        m = _ROUND_RE.match(name)
        if m and isinstance(_safe_read_json(verdict_path(run_dir, int(m.group(1))), None), dict):
            best = max(best, int(m.group(1)))
    return best + 1


# ── compile / dedupe (FR-3) ──
def _identity(f):
    return circuit_breaker.finding_identity(f)


def _merge_dims(a, b):
    parts = []
    for src in (a.get("dimension"), b.get("dimension")):
        if not src:
            continue
        for p in str(src).split("+"):
            p = p.strip()
            if p and p not in parts:
                parts.append(p)
    return " + ".join(parts)


def compile_findings(findings, context_files=None):
    """Merge by identity (file::normalized_title): keep the higher severity, union dimensions.
    Drop uncited findings (file/line None) and, when context_files is given, any finding whose
    file is outside the reviewed material."""
    by_id = {}
    for f in findings:
        if f.get("file") is None or f.get("line") is None:
            continue
        if context_files is not None and f.get("file") not in context_files:
            continue
        fid = _identity(f)
        if fid in by_id:
            ex = by_id[fid]
            dims = _merge_dims(ex, f)
            if SEV_RANK.get(f.get("severity"), 99) < SEV_RANK.get(ex.get("severity"), 99):
                merged = dict(f)
            else:
                merged = dict(ex)
            merged["dimension"] = dims
            by_id[fid] = merged
        else:
            by_id[fid] = dict(f)
    out = list(by_id.values())
    for f in out:  # FR-4: deterministic mechanical/judgment classification (no action taken)
        f["classification"] = "judgment" if f.get("tradeoff") else "mechanical"
    return out


# ── per-round gate + confidence (FR-5/6/7) ──
def round_gate(compiled, expected_roster, completed_roster):
    """Deterministic per-round verdict from the compiled findings + completion state.
    Precedence: any reviewer that did not complete → `cannot-certify` (coverage gap). Returns
    the `missing` (incomplete) reviewers too, so the verdict can NAME the missing review angles
    (FR-5/UFR-2)."""
    incomplete = [r for r in expected_roster if r not in completed_roster]
    has_blocker = any(f.get("severity") in BLOCKING for f in compiled)
    if incomplete:
        gate = "cannot-certify"
    elif has_blocker:
        gate = "blocking"
    else:
        gate = "clean"
    all_verifiable = all(bool(f.get("evidence")) for f in compiled)
    confidence = "high" if (not incomplete and all_verifiable) else "low"
    return gate, confidence, incomplete


def _current_blocking_findings(results):
    out = []
    for result in (results or {}).values():
        if not isinstance(result, dict) or result.get("status") != "run":
            continue
        for f in result.get("findings") or []:
            if not isinstance(f, dict) or f.get("carried"):
                continue
            if f.get("severity") in BLOCKING:
                out.append(f)
    return out


def present_blocking_from_dimension_results(results):
    return len(_current_blocking_findings(results))


def blocking_findings_from_dimension_results(results):
    return [dict(f) for f in _current_blocking_findings(results)]


def compile_dimension_results(results):
    findings = []
    for name, result in (results or {}).items():
        if not isinstance(result, dict):
            continue
        for f in result.get("findings") or []:
            if not isinstance(f, dict):
                continue
            item = dict(f)
            if "dimension" not in item:
                item["dimension"] = result.get("dimension") or name
            if result.get("status") == "skipped":
                item["carried"] = True
                item["sourceRound"] = result.get("carriedFromRound")
            findings.append(item)
    return compile_findings(findings)


def _valid_final_receipt(result, receipt_context=None):
    receipt = result.get("verificationReceipt")
    chain = receipt.get("chain") if isinstance(receipt, dict) else None
    required = {"citation", "reachability", "missing-check", "tooling"}
    if not isinstance(receipt, dict) or not receipt.get("artifact"):
        return False
    if not isinstance(receipt.get("coverageDecisionIds"), list):
        return False
    ctx = receipt_context or {}
    if ctx.get("artifact") and receipt.get("artifact") != ctx.get("artifact"):
        return False
    needed_ids = set(ctx.get("coverageDecisionIds") or [])
    if needed_ids and not needed_ids.issubset(set(receipt.get("coverageDecisionIds") or [])):
        return False
    seen = set()
    for step in chain or []:
        if not isinstance(step, dict):
            return False
        if not step.get("evidence"):
            return False
        seen.add(step.get("step"))
    return required.issubset(seen)


def round_gate_from_dimension_results(results, expected_roster, final_confirmation=False, receipt_context=None):
    completed = [name for name, result in (results or {}).items() if result.get("status") in ("run", "skipped")]
    compiled = compile_dimension_results(results)
    gate, confidence, missing = round_gate(compiled, expected_roster, completed)
    for name in expected_roster:
        result = (results or {}).get(name) or {}
        if result.get("confidence") != "high":
            return "cannot-certify", "low", missing
    if final_confirmation:
        for name in expected_roster:
            result = (results or {}).get(name) or {}
            # externalReview (#38/receipt-fabrication fix): an external-engine reviewer has no
            # native chain-of-verification receipt to offer, but it IS a real independent review —
            # accept it as an alternate, honestly-labeled confirmation path instead of demanding a
            # receipt shape it structurally can't produce.
            if result.get("externalReview"):
                continue
            if not _valid_final_receipt(result, receipt_context):
                return "cannot-certify", "low", missing
    if gate == "clean" and _current_blocking_findings(results):
        return "blocking", confidence, missing
    return gate, confidence, missing


# ── honest cannot-certify reason (FR-5/UFR-2, #212) ──
# The defect-class phrasing that names WHY a seat could not certify. Each class is a DISTINCT string
# so a park diagnoses the failure instead of anonymizing it ("a reviewer did not complete").
_SEAT_PHRASE = {
    "receipt-missing": "%s returned no verification receipt after retry (receipt-missing — uncertifiable)",
    "receipt-stale": "%s returned a stale verification receipt after retry (receipt-stale — uncertifiable)",
    "malformed": "%s did not return a usable result after retry (malformed — uncertifiable)",
    "genuinely-incomplete": "%s reported low confidence after retry (genuinely-incomplete — uncertifiable)",
    "coverage-gap": "%s did not complete after its retry (coverage-gap — uncertifiable)",
}


def _seat_defect_class(result):
    """Classify a single seat's certification defect (or None when it certified). A high-confidence
    seat, or an externally-reviewed seat (its own honestly-labeled confirmation path), certifies."""
    if not isinstance(result, dict):
        return "coverage-gap"                       # seat absent entirely
    if result.get("externalReview"):
        return None
    if result.get("confidence") == "high":
        return None
    if result.get("receiptMissing"):
        return "receipt-missing"
    if result.get("receiptStale"):
        return "receipt-stale"
    if result.get("status") not in ("run", "skipped") or result.get("malformed"):
        return "malformed"
    if result.get("status") == "skipped":
        return "coverage-gap"                       # carried forward without a certified prior
    return "genuinely-incomplete"                   # ran, honest low confidence, no receipt defect


def uncertified_reason(results, expected_roster):
    """The honest cannot-certify reason: name every seat that blocks certification AND why (#212).
    A round is cannot-certify when a seat did not certify — receipt-missing/stale after retry, a
    malformed/absent seat, or an honest low-confidence answer. Returns a `;`-joined phrase naming
    each uncertifiable seat + its DISTINCT defect class, or None when every seat certified (the
    caller then keeps the generic terminal reason). Pure; both twins operate on the same results
    map so the parity fixtures pin the phrasing."""
    results = results or {}
    parts = []
    for name in expected_roster or []:
        cls = _seat_defect_class(results.get(name))
        if cls:
            parts.append(_SEAT_PHRASE[cls] % name)
    return "; ".join(parts) if parts else None


# ── deferral accounting (FR-10) ──
def present_deferred(compiled, deferred_set):
    """present-∩-deferred: count present BLOCKING findings whose identity was deferred and whose
    current severity is no GREATER than the severity it was deferred at (a higher-severity or
    different-substance re-flag is a new, non-deferred blocker). Mirrors loop_state's cumulative
    present-∩-skip contract: a deferral for a finding no longer re-flagged simply stops counting."""
    n = 0
    for f in compiled:
        if f.get("severity") not in BLOCKING:
            continue
        deferred_sev = deferred_set.get(_identity(f))
        if deferred_sev is None:
            continue
        if SEV_RANK.get(f.get("severity"), 99) >= SEV_RANK.get(deferred_sev, 99):
            n += 1
    return n


# ── terminal decision (FR-8/9): strict precedence, delegating to loop_state ──
_ACTION_TO_TERMINAL = {
    "review": "continue",
    "exit_clean": "clean",
    "exit_skipped": "clean-with-skips",
    "halt": "halted",
}
_TERMINAL_TO_ACTION = {
    "continue": "review",
    "clean": "exit_clean",
    "clean-with-skips": "exit_skipped",
    "cannot-certify": "halt",
    "halted": "halt",
}


def _terminal_to_action(terminal):
    """Map the panel terminal to a loop_state-vocabulary action so the durable record stays
    readable through review_result.read_result's closed allow-list (the precise terminal rides
    in the verdict's own field + the record's reason)."""
    return _TERMINAL_TO_ACTION.get(terminal, "halt")


def decide_terminal(gate, present_blocking, present_deferred_count, fix_status, rnd, max_rounds, breaker_halt):
    """FR-9 precedence (first match wins):
      (1) cannot-certify with NO fixable blocking finding → PARK immediately (coverage is the sole
          gap; there is nothing to fix). This is the ONLY cannot-certify path that parks here.
      (1b/#212 fix-before-park) A cannot-certify round that STILL holds unresolved blockers is NOT
          parked: its findings are real regardless of the uncertified seat, so it routes to the fix
          leg exactly like a `blocking` round (falling through to steps 2-3). This is gate-based, so
          it covers EVERY entrance to cannot-certify uniformly — receipt-missing/stale seats, a seat
          that ended `missing` (malformed after both retries), and coverage-gap rounds that hold
          blockers from the seats that DID run. Certification stays WITHHELD: the next round's gate
          re-dooms the still-uncertified seat, so exit_clean is unreachable until a fully-certified
          clean panel (the #174 confirmation bar is untouched).
      (2) halted on a failed fix step.
      (3) loop_state's cap-halt / clean-with-skips / clean / continue.
    Never returns `clean` while coverage is incomplete or a non-deferred blocker is unresolved. When
    routed to the fix leg (1b) loop_state can only return `review` (under cap) or `halt` (cap/breaker)
    — never a clean exit — because blocking_fixed > 0 there."""
    blocking_fixed = max(0, present_blocking - present_deferred_count)
    if gate == "cannot-certify" and blocking_fixed == 0:
        return "cannot-certify", "coverage not certified — a review seat did not certify after its retry"
    if fix_status == "failed":
        return "halted", "the fix step did not complete (failed or timed out)"
    action, _mandatory, reason = loop_state.decide(
        blocking_fixed, present_deferred_count, rnd, max_rounds, bool(breaker_halt))
    return _ACTION_TO_TERMINAL[action], reason


# ── fail-safe reads + persistence ──
def _safe_read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _atomic_write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, sort_keys=True)
    os.replace(tmp, path)


def _persist(run_dir, rnd, verdict):
    _atomic_write_json(verdict_path(run_dir, rnd), verdict)
    # durable terminal record via the review_result helper (unchanged); action in loop_state
    # vocabulary keeps read_result happy, the precise terminal + reason ride in `reason`.
    review_result.write_result(
        result_path(run_dir), _terminal_to_action(verdict["terminal"]), rnd,
        "%s: %s" % (verdict["terminal"], verdict.get("reason", "")))


def _persist_or_failclosed(run_dir, rnd, verdict, compiled, missing):
    """Persist the verdict; on a durable-write failure fail CLOSED to `halted` (UFR-9), and if
    even the halt record cannot be written, flag `recordMissing` on the returned result."""
    try:
        _persist(run_dir, rnd, verdict)
        return verdict
    except Exception as exc:
        halted = {"schemaVersion": SCHEMA_VERSION, "gate": "cannot-certify", "confidence": "low",
                  "findings": compiled, "missing": missing, "drops": verdict.get("drops", []),
                  "terminal": "halted",
                  "reason": "durable record write failed (%s) — failing closed" % exc}
        for k in ("fixes", "deferred", "parentOrigin"):
            if k in verdict:
                halted[k] = verdict[k]
        try:
            _persist(run_dir, rnd, halted)
        except Exception:
            halted["recordMissing"] = True
        return halted


def tally(run_dir, rnd, roster, max_rounds=7, breaker_halt=False, fix_status="completed",
          context_files=None, synthesized=None, verify_result=None, extras=None):
    """Deterministic per-round tally. Fail-safe across EVERY read — a missing/malformed input
    biases to a non-clean terminal, never a silent `clean`. On panel legs `synthesized`
    (loop_synthesis output) replaces the raw compile; `verify_result` gates a code leg's clean
    terminal (FR-17/UFR-4); the circuit breaker is computed internally from this run's verdicts
    (UFR-2); `extras` (fixes/deferred/parentOrigin) ride into the record for the readout. A
    durable-write failure fails closed to `halted` with `recordMissing` (UFR-9)."""
    extras = extras if isinstance(extras, dict) else {}
    # Only readout-enrichment keys ride in from the caller — never the decision/terminal fields,
    # so a caller's extras can't overwrite a fail-closed `halted` (UFR-9) or any gate field.
    safe_extras = {k: extras[k] for k in ("fixes", "deferred", "parentOrigin") if k in extras}
    try:
        if not roster:
            verdict = {"schemaVersion": SCHEMA_VERSION, "gate": "cannot-certify",
                       "confidence": "low", "findings": [], "missing": [], "drops": [],
                       "terminal": "cannot-certify",
                       "reason": "empty reviewer set — nothing to certify"}
            verdict.update(safe_extras)
            return _persist_or_failclosed(run_dir, rnd, verdict, [], [])
        # Completion is derived from the round's findings files regardless of leg, so a panel
        # leg with a missing reviewer still trips cannot-certify (UFR-1), not a false clean on
        # incomplete coverage.
        completed = [r for r in roster
                     if isinstance(_safe_read_json(findings_path(run_dir, rnd, r), None), list)]
        if isinstance(synthesized, dict):                      # panel leg: judgment already done
            compiled = synthesized.get("findings", [])
            drops = synthesized.get("drops", [])
        else:                                                  # single-reviewer leg: compile raw
            all_findings = []
            for reviewer in completed:
                data = _safe_read_json(findings_path(run_dir, rnd, reviewer), [])
                if isinstance(data, list):
                    all_findings.extend(data)
            compiled = compile_findings(all_findings, context_files)
            drops = []
        gate, confidence, missing = round_gate(compiled, roster, completed)
        deferred_set = _safe_read_json(deferred_set_path(run_dir), {})
        if not isinstance(deferred_set, dict):
            deferred_set = {}
        present_blocking = sum(1 for f in compiled if f.get("severity") in BLOCKING)
        pdef = present_deferred(compiled, deferred_set)
        # Internal circuit breaker (UFR-2): prior rounds from disk + this round's findings,
        # skip-set excluded — computed here (protected) so the breaker decision isn't in the shell.
        skip = set(deferred_set.keys())
        # Exclude THIS round from the disk-read history (it may already be persisted from a
        # prior idempotent call) and append the current findings exactly once — otherwise a
        # re-call would double-count round rnd and trip a false recurrence-halt.
        prior = [r for r in assemble_rounds(run_dir) if r["round"] != rnd]
        history = prior + [{"round": rnd, "findings": [
            f for f in compiled if circuit_breaker.finding_identity(f) not in skip]}]
        brk = circuit_breaker.check_circuit_breaker(history, max_rounds)
        breaker_halt = bool(breaker_halt) or brk["halt"]
        terminal, reason = decide_terminal(
            gate, present_blocking, pdef, fix_status, rnd, max_rounds, breaker_halt)
        # Verify gate (FR-17/UFR-4): a code leg's clean terminal requires verify to have passed.
        if terminal in ("clean", "clean-with-skips") and verify_result not in _VERIFY_OK:
            terminal = "halted"
            reason = ("verify command timed out — cannot certify clean" if verify_result == "timeout"
                      else "verify command failed — cannot certify clean")
        if terminal == "cannot-certify" and missing:
            reason = "coverage incomplete — missing review angle(s): %s" % ", ".join(missing)
        verdict = {"schemaVersion": SCHEMA_VERSION, "gate": gate, "confidence": confidence,
                   "findings": compiled, "missing": missing, "drops": drops,
                   "terminal": terminal, "reason": reason}
        verdict.update(safe_extras)
        return _persist_or_failclosed(run_dir, rnd, verdict, compiled, missing)
    except Exception as exc:  # absolute fail-safe — any unforeseen error halts, never clean
        verdict = {"schemaVersion": SCHEMA_VERSION, "gate": "cannot-certify", "confidence": "low",
                   "findings": [], "missing": [], "drops": [], "terminal": "halted",
                   "reason": "tally failed: %s" % exc}
        verdict.update(safe_extras)
        try:
            _persist(run_dir, rnd, verdict)
        except Exception:
            verdict["recordMissing"] = True
        return verdict


_EMIT_FNS = {
    "compile_findings": compile_findings,
    "round_gate": round_gate,
    "present_deferred": present_deferred,
    "decide_terminal": decide_terminal,
}


def _emit_main(argv):
    """Subcommand: --emit <fn> --input <json-array> → json.dumps(fn(*args), sort_keys=True).
    round_gate returns a tuple; emitted as {gate, confidence, incomplete} so the JS twin
    contract is an object.  No existing function is modified."""
    ap = argparse.ArgumentParser(description="emit subcommand for parity testing")
    ap.add_argument("--emit", required=True, choices=list(_EMIT_FNS))
    ap.add_argument("--input", required=True, help="JSON array of positional args")
    args = ap.parse_args(argv[1:])
    fn = _EMIT_FNS[args.emit]
    fn_args = json.loads(args.input)
    result = fn(*fn_args)
    if args.emit == "round_gate":
        gate, confidence, incomplete = result
        result = {"gate": gate, "confidence": confidence, "incomplete": incomplete}
    elif args.emit == "decide_terminal":
        terminal, reason = result
        result = {"reason": reason, "terminal": terminal}
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0


def main(argv):
    # Dispatch to the --emit subcommand when present (additive; existing tally path unchanged).
    if len(argv) > 1 and argv[1] == "--emit":
        return _emit_main(argv)
    ap = argparse.ArgumentParser(description="deterministic review-panel tally (review-crew)")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--round", type=int, required=True, dest="rnd")
    ap.add_argument("--roster", required=True, help="comma-separated reviewer names")
    ap.add_argument("--max-rounds", type=int, default=7)
    ap.add_argument("--breaker-halt", choices=["yes", "no"], default="no")
    ap.add_argument("--fix-status", choices=["completed", "failed"], default="completed")
    ap.add_argument("--context-files", default=None, help="comma-separated reviewed-file allowlist")
    ap.add_argument("--synthesized", default=None, help="loop_synthesis output JSON (panel legs)")
    ap.add_argument("--verify-result", default=None, help="pass|fail|timeout|skipped (code legs)")
    ap.add_argument("--extras", default=None, help="extras JSON (fixes/deferred/parentOrigin)")
    args = ap.parse_args(argv[1:])
    roster = [r for r in args.roster.split(",") if r]
    context_files = args.context_files.split(",") if args.context_files else None
    synthesized = _safe_read_json(args.synthesized, None) if args.synthesized else None
    extras = _safe_read_json(args.extras, None) if args.extras else None
    verdict = tally(args.run_dir, args.rnd, roster, args.max_rounds,
                    args.breaker_halt == "yes", args.fix_status, context_files,
                    synthesized=synthesized, verify_result=args.verify_result, extras=extras)
    sys.stdout.write(json.dumps(verdict, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
