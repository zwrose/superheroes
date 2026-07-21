#!/usr/bin/env python3
"""review-spec's script-owned round scheduler + continuation gate (#164).

review-spec is the one review leg that can never run on the showrunner spine (it runs in
Discovery, pre-approval), so the #125 convergence levers — skip clean untouched dimensions,
start intermediate rounds at `reviewer` and escalate, full `reviewer-deep` confirmation
before exit — were prose the orchestrator had to apply, and a numbered "re-dispatch the five
specialists" mandate beat a trailing contract pointer every time. This module makes the
schedule a script decision, exactly like `loop_state.py` made the continue/exit decision one.

It deliberately owns NO policy of its own:
  - the continue/exit/halt action comes from `loop_state.decide` (imported, same inputs);
  - the per-dimension run/skip/tier schedule comes from `review_round_policy.plan_round`,
    the parity-locked Python twin of the spine's scheduler — ONE policy implementation,
    shared with `review_panel_shell.js`, so the prose path cannot drift from the spine
    (#145 paid for that drift once already).

What it adds is the evidence plumbing the prose path was missing:
  - **Executed-evidence gate.** When a dimension is scheduled to run, its previous
    `findings-*.json` is archived first; only a file written after that counts. A
    prompt-dropped agent that burned no tokens leaves no fresh file, so its stale "clean"
    can never license a skip (the 2026-07-03 zero-token-stub class). A valid findings file
    (any shape or tier) is high-confidence; only a missing or unparseable (transport)
    result fails.
  - **Changed surface from the script's own snapshots.** Each round's spec copy is
    snapshotted (`spec-r<N>.md`); the changed surface for round N+1 is the diff of the
    script's snapshots — section headings whose text differs — never the reviser's
    self-report (#158's lesson: derive the surface from what actually changed). Any
    diff/shape failure yields "unknown" → run-all.
  - **Escalation semantic (#145).** A missing/unparseable result retries ONCE at
    `reviewer-deep`; after that it is recorded as missing — never a loop.
  - **Confirmation invariant.** `exit_clean`/`exit_skipped` are honored only off a round
    whose every dimension ran fresh at `reviewer-deep` with high confidence; otherwise one
    full-deep confirmation round is scheduled (that bound is what makes cheap skips safe).
    At the round cap the exit degrades to `halt`, never to an unconfirmed SPEC READY.

Every failure — corrupt scheduler state, unreadable compiled.json, missing snapshot —
fails toward MORE review (run-all at `reviewer-deep`), never toward a skip or an exit.
Tiers are `model_tier_resolve` role names (`reviewer`/`reviewer-deep`), never model names.
stdlib only.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loop_state  # noqa: E402
import review_round_policy  # noqa: E402
import loop_plan_common  # noqa: E402,F401
# The leg-agnostic loop-state plumbing (state I/O, plan rendering, carry-forward, and the
# #174 confirmation-panel bookkeeping) lives in loop_plan_common, shared verbatim with
# code_loop_plan.py (#174 PR 2). Imported into this module's namespace so the verbs below —
# and the tests that reach for these names — read exactly as before the extraction.
from loop_plan_common import (  # noqa: E402,F401
    DEEP, CHEAP, BLOCKING, load_state, save_state, _round_entry, _previous_dims,
    _run_all_plan, _plan_lists, _overlay_escalations, _persist_plan, _subjects,
    _carry_forward, _confirmation_rounds, _surfaced_severities,
    _surfaced_severities_since, _full_deep_executed)

DIMENSIONS = ["architecture-reviewer", "code-reviewer", "security-reviewer",
              "test-reviewer", "premortem-reviewer"]
AGENT_SUFFIX = {"architecture-reviewer": "architecture", "code-reviewer": "code",
                "security-reviewer": "security", "test-reviewer": "test",
                "premortem-reviewer": "premortem"}
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


# --- session-dir plumbing ---------------------------------------------------

def _findings_path(session_dir, dimension):
    suffix = AGENT_SUFFIX.get(dimension) or str(dimension)
    return os.path.join(session_dir, "findings-%s.json" % suffix)


def _snapshot_path(session_dir, round_no):
    return os.path.join(session_dir, "spec-r%d.md" % round_no)


def _snapshot(session_dir, round_no, overwrite=False):
    """Copy the session spec surface to the per-round snapshot the diff reads."""
    dst = _snapshot_path(session_dir, round_no)
    if os.path.exists(dst) and not overwrite:
        return True
    try:
        with open(os.path.join(session_dir, "spec.md"), encoding="utf-8") as fh:
            text = fh.read()
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(text)
        return True
    except OSError:
        return False


def _archive_findings(session_dir, dimension, round_no, tag=None):
    """Move a dimension's findings file out of the live slot so only a file written AFTER
    this call can count as that dimension's next result (the executed-evidence gate)."""
    src = _findings_path(session_dir, dimension)
    if not os.path.exists(src):
        return
    archive_dir = os.path.join(session_dir, "rounds", "r%d" % round_no)
    name = "findings-%s%s.json" % (AGENT_SUFFIX.get(dimension, dimension),
                                   (".%s" % tag) if tag else "")
    try:
        os.makedirs(archive_dir, exist_ok=True)
        os.replace(src, os.path.join(archive_dir, name))
    except OSError:
        # fail toward run-all, never toward a stale read: a file we cannot move must not
        # remain readable as a fresh result
        try:
            os.unlink(src)
        except OSError:
            pass


# --- findings-file evidence ---------------------------------------------------

def _read_findings(session_dir, dimension, tier):
    """Spec-leg findings live flat in the session dir; the confidence rule is shared."""
    return loop_plan_common.read_findings_file(_findings_path(session_dir, dimension), tier)


# --- confirmation follow-up (spec-leg changed-surface) ------------------------

def _further_confirmation_owed(session_dir, state, dimensions):
    """#174: is a FURTHER full confirmation panel owed? The mandatory first panel is always owed;
    after one QUALIFYING panel has run, the follow-up decision is computed over EVERYTHING SINCE THAT
    PANEL — the severities surfaced by the panel and every later scoped round, and the rework applied
    since (the changed spec surface diffed from the panel's own snapshot, so multi-round rework and
    an unknown surface both fail toward one more panel). A Critical still owed at the cap parks."""
    confirmations = _confirmation_rounds(state, dimensions)
    if not confirmations:
        return {"owed": True, "park": False, "panels": 0, "surfaced": False}
    last_round, _ = confirmations[-1]
    surfaced = _surfaced_severities_since(state, last_round)
    cross = review_round_policy.is_cross_cutting(_diff_changed_surface(session_dir, last_round))
    followup = review_round_policy.confirmation_followup(surfaced, len(confirmations), cross)
    return {"owed": followup["rearm"], "park": followup["park"], "panels": len(confirmations),
            "reason": followup["reason"], "surfaced": bool(surfaced)}


# --- changed-surface diff -------------------------------------------------------

def _sections(text):
    out, order = {}, []
    title, buf = "(preamble)", []

    def _push():
        key, n = title, 2
        while key in out:
            key = "%s (%d)" % (title, n)
            n += 1
        out[key] = "\n".join(buf)
        order.append(key)

    for line in text.splitlines():
        m = _HEADING.match(line)
        if m:
            _push()
            title, buf = m.group(2).strip(), []
        else:
            buf.append(line)
    _push()
    return out, order


def changed_sections(old_text, new_text):
    """Section headings whose text differs between two spec snapshots — the spec-side
    changed-surface vocabulary. Content before the first heading is '(preamble)'.
    Returns a KNOWN list (possibly empty); callers map any failure to None (unknown)."""
    old, _old_order = _sections(old_text)
    new, new_order = _sections(new_text)
    changed = [k for k in new_order if new[k] != old.get(k, None)]
    changed.extend(k for k in _old_order if k not in new)
    return changed


def _diff_changed_surface(session_dir, prev_round):
    """Diff the script's own snapshots (never the reviser's self-report). Any read failure
    → None (unknown surface → the policy runs all dimensions)."""
    try:
        with open(_snapshot_path(session_dir, prev_round), encoding="utf-8") as fh:
            old_text = fh.read()
        with open(os.path.join(session_dir, "spec.md"), encoding="utf-8") as fh:
            new_text = fh.read()
    except OSError:
        return None
    return changed_sections(old_text, new_text)


# --- verbs ----------------------------------------------------------------------

def cmd_plan(session_dir, round_no, dimensions):
    state_ok, state = load_state(session_dir)
    entry = (state.get("rounds") or {}).get(str(round_no)) or {}
    plan = entry.get("plan") if state_ok else None
    plan_created = False
    if not isinstance(plan, dict) or not isinstance(plan.get("dimensions"), dict):
        if round_no <= 1:
            plan = review_round_policy.plan_round(
                {"round": 1, "dimensions": dimensions, "changedSubjects": [], "previous": {}})
            _snapshot(session_dir, 1)
        else:
            plan = _run_all_plan(dimensions,
                                 "no persisted plan for round %d — fail toward run-all" % round_no)
            _snapshot(session_dir, round_no)
            for d in dimensions:
                sched = (plan.get("dimensions") or {}).get(d) or {}
                if sched.get("action") != "skip":
                    _archive_findings(session_dir, d, round_no - 1)
        state = _persist_plan(session_dir, state, round_no, plan, state_ok)
        plan_created = True
    if plan_created:
        state_ok, state = load_state(session_dir)
    entry = (state.get("rounds") or {}).get(str(round_no)) or {}
    plan = _overlay_escalations(plan, entry.get("escalations") or {})
    dims_to_run, skipped = _plan_lists(plan, dimensions)
    return {"ok": True, "round": round_no, "roundKind": plan.get("roundKind"),
            "dims_to_run": dims_to_run, "skipped": skipped}


def _carry_forward(state, dimension, round_no, sched):
    """The prose twin of the shell's carryForwardDimension: a skipped dimension keeps its
    latest recorded state; with nothing to carry it is low-confidence (never skip-eligible
    again until it actually runs)."""
    previous = _previous_dims(state, round_no - 1)
    prior = previous.get(dimension)
    if isinstance(prior, dict):
        rec = dict(prior)
    else:
        rec = {"confidence": "low", "hasFindings": False, "blockingCount": 0,
               "subjects": _subjects(dimension, [])}
    rec.update({"dimension": dimension, "status": "skipped", "round": round_no,
                "carriedFromRound": sched.get("carriedFromRound") or rec.get("round")})
    return rec


def cmd_record(session_dir, round_no, dimensions):
    state_ok, state = load_state(session_dir)
    if not state_ok:
        state = {"schemaVersion": 1, "rounds": {}, "rebuilt": True}
    entry = _round_entry(state, round_no)
    plan = entry.get("plan")
    if not isinstance(plan, dict) or not isinstance(plan.get("dimensions"), dict):
        plan = _run_all_plan(dimensions, "no persisted plan — recorded as a full deep round")
        entry["plan"] = plan
    _snapshot(session_dir, round_no)  # safety net: the round surface, pre-revision
    escalations = entry.setdefault("escalations", {})
    dims = entry.setdefault("dims", {})
    escalate = []
    for d in dimensions:
        sched = (plan.get("dimensions") or {}).get(d) or {"action": "run", "tier": DEEP}
        if sched.get("action") == "skip":
            dims[d] = _carry_forward(state, d, round_no, sched)
            continue
        already = bool(escalations.get(d))
        tier = DEEP if already else (sched.get("tier") or DEEP)
        result = _read_findings(session_dir, d, tier)
        needs_more = not result["valid"]
        if needs_more and not already:
            # one escalation/retry at reviewer-deep — archive the invalid result so
            # only a freshly-written file can count as the deep answer
            escalations[d] = {"from": tier}
            _archive_findings(session_dir, d, round_no, tag="retry")
            why = result.get("why")
            escalate.append({"dimension": d, "tier": DEEP,
                             "reason": "%s — re-dispatch once at %s" % (why, DEEP)})
            dims[d] = {"dimension": d, "status": "escalation-pending", "round": round_no}
            continue
        if not result["valid"]:
            _archive_findings(session_dir, d, round_no, tag="invalid")
            dims[d] = {"dimension": d, "status": "missing", "confidence": "low",
                       "round": round_no}
            continue
        dims[d] = {"dimension": d, "status": "run", "tier": tier,
                   "confidence": result["confidence"], "hasFindings": result["hasFindings"],
                   "blockingCount": result["blocking"], "criticalCount": result["critical"],
                   "subjects": _subjects(d, result["findings"]),
                   "escalated": already, "round": round_no}
    save_state(session_dir, state)
    return {"ok": True, "round": round_no, "escalate": escalate, "dimensions": dims}


def _next_round_out(session_dir, state, state_ok, round_no, plan, action, mandatory, reason,
                    dimensions):
    _snapshot(session_dir, round_no + 1, overwrite=True)
    dims_to_run, skipped = _plan_lists(plan, dimensions)
    for d in dimensions:
        _archive_findings(session_dir, d, round_no)
    _persist_plan(session_dir, state, round_no + 1, plan, state_ok)
    return {"action": action, "mandatory": mandatory, "reason": reason,
            "round": round_no, "nextRound": round_no + 1,
            "roundKind": plan.get("roundKind"),
            "dims_to_run": dims_to_run, "skipped": skipped}


def cmd_decide(session_dir, round_no, max_rounds, compiled, skipped_blocking, dimensions):
    state_ok, state = load_state(session_dir)
    try:
        present = loop_state._blocking_present_from_compiled(compiled)
        blocking_fixed = max(0, present - skipped_blocking)
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
        # fail SAFE toward more review, never toward a silent exit or a skip
        plan = review_round_policy.plan_round(
            {"round": round_no + 1, "dimensions": dimensions,
             "changedSubjects": None, "previous": {}})
        return _next_round_out(
            session_dir, state, state_ok, round_no, plan, "review", True,
            "could not read the round artifacts (%s) — defaulting to another full review "
            "round rather than risk a premature exit." % exc, dimensions)

    action, mandatory, reason = loop_state.decide(
        blocking_fixed, skipped_blocking, round_no, max_rounds, False)

    if action in ("exit_clean", "exit_skipped"):
        if state_ok and _full_deep_executed(state, round_no, dimensions):
            return {"action": action, "mandatory": mandatory, "reason": reason,
                    "round": round_no, "nextRound": None, "roundKind": None,
                    "dims_to_run": [], "skipped": [],
                    "certification": {"fullPanels": len(_confirmation_rounds(state, dimensions)),
                                      "lastPanelSurfacedResolved": False}}
        # #174 confirmation-bar economics: once a QUALIFYING full confirmation panel has run, another
        # is owed ONLY when its follow-up (a Critical surfaced since — panel or later scoped round —
        # or cross-cutting rework, under the cap) demands it. When the obligation is satisfied,
        # certify off the scoped verify rather than ratcheting a fresh fully-clean panel; a Critical
        # still owed at the cap parks.
        owe = _further_confirmation_owed(session_dir, state, dimensions) if state_ok \
            else {"owed": True, "park": False, "panels": 0, "surfaced": False}
        if owe["park"]:
            return {"action": "halt", "mandatory": True,
                    "reason": "%s — report this round's findings; do NOT declare SPEC READY."
                              % owe.get("reason", "confirmation-panel cap reached with a Critical"),
                    "round": round_no, "nextRound": None, "roundKind": None,
                    "dims_to_run": [], "skipped": [],
                    "certification": {"fullPanels": owe["panels"],
                                      "lastPanelSurfacedResolved": owe["surfaced"]}}
        if owe["panels"] >= 1 and not owe["owed"]:
            return {"action": action, "mandatory": mandatory,
                    "reason": "%s (%d full confirmation panel(s) ran; findings surfaced since the "
                              "last panel were resolved with scoped verification)."
                              % (reason, owe["panels"]),
                    "round": round_no, "nextRound": None, "roundKind": None,
                    "dims_to_run": [], "skipped": [],
                    "certification": {"fullPanels": owe["panels"],
                                      "lastPanelSurfacedResolved": owe["surfaced"]}}
        if round_no >= max_rounds:
            return {"action": "halt", "mandatory": True,
                    "reason": "round cap (%d) reached before the mandatory full "
                              "%s confirmation round — report this round's findings; do "
                              "NOT declare SPEC READY." % (max_rounds, DEEP),
                    "round": round_no, "nextRound": None, "roundKind": None,
                    "dims_to_run": [], "skipped": []}
        plan = review_round_policy.plan_round(
            {"round": round_no + 1, "dimensions": dimensions, "confirmation": True,
             "changedSubjects": None, "previous": {}})
        return _next_round_out(
            session_dir, state, state_ok, round_no, plan, "review", True,
            "MANDATORY: this round was reduced or under-evidenced (skipped dimensions, "
            "%s-tier results, missing receipts, or unreadable scheduler state) — a full "
            "%s confirmation round must come back clean before exit." % (CHEAP, DEEP),
            dimensions)

    if action == "review":
        changed = _diff_changed_surface(session_dir, round_no) if state_ok else None
        previous = _previous_dims(state, round_no) if state_ok else {}
        plan = review_round_policy.plan_round(
            {"round": round_no + 1, "dimensions": dimensions,
             "changedSubjects": changed, "previous": previous})
        return _next_round_out(session_dir, state, state_ok, round_no, plan,
                               action, mandatory, reason, dimensions)

    return {"action": action, "mandatory": mandatory, "reason": reason,
            "round": round_no, "nextRound": None, "roundKind": None,
            "dims_to_run": [], "skipped": []}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="review-spec's script-owned round scheduler + continuation gate")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "record", "decide"):
        p = sub.add_parser(name)
        p.add_argument("--session-dir", required=True)
        p.add_argument("--round", type=int, required=True, dest="rnd")
        p.add_argument("--dimensions", default=None,
                       help="JSON list of reviewer names (default: the five specialists)")
        if name == "decide":
            p.add_argument("--max-rounds", type=int, default=7)
            p.add_argument("--compiled", required=True)
            p.add_argument("--skipped-blocking", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        dimensions = json.loads(args.dimensions) if args.dimensions else list(DIMENSIONS)
        if not isinstance(dimensions, list) or not dimensions:
            dimensions = list(DIMENSIONS)
    except ValueError:
        dimensions = list(DIMENSIONS)
    if args.cmd == "plan":
        out = cmd_plan(args.session_dir, args.rnd, dimensions)
    elif args.cmd == "record":
        out = cmd_record(args.session_dir, args.rnd, dimensions)
    else:
        out = cmd_decide(args.session_dir, args.rnd, args.max_rounds, args.compiled,
                         args.skipped_blocking, dimensions)
    sys.stdout.write(json.dumps(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
