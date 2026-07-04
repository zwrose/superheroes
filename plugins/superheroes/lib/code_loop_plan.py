#!/usr/bin/env python3
"""review-code's script-owned round scheduler + continuation gate (#174 PR 2).

review-code used to run **all five specialists at fixed tiers every round** — a documented
"coverage uniformity" exception to the shared convergence levers (#125/#164). This module
reverses that exception on purpose, giving review-code the same script-owned schedule
`spec_loop_plan.py` gave review-spec (#167): round 1 is the full `reviewer-deep` panel,
intermediate rounds dispatch exactly the emitted `dims_to_run`, and no exit is honored until
a full `reviewer-deep` confirmation panel has run — the bound that makes cheap intermediate
skips safe (the "an IDOR slips through on the round we skipped security" worry is answered by
that invariant, not by re-running five reviewers on every delta round).

It owns NO policy of its own — identical in spirit to `spec_loop_plan.py`:
  - the continue/exit/halt action comes from `loop_state.decide` (imported, review-code's own
    `--fix-batch`/`--resolutions` inputs — the `arch-r2-001` contract is unchanged);
  - the per-dimension run/skip/tier schedule comes from `review_round_policy.plan_round`, the
    parity-locked twin of the spine's scheduler — ONE policy implementation;
  - the confirmation follow-up (#174 confirmation-bar economics, PR 1) comes from
    `review_round_policy.confirmation_followup` + `is_cross_cutting`;
  - the leg-agnostic loop-state plumbing (state I/O, plan rendering, carry-forward,
    confirmation-panel bookkeeping) is shared with review-spec via `loop_plan_common`.

The code-leg specifics this module adds:
  - **Round-scoped findings.** review-code writes `round-<N>/findings-<agent>.json`; the
    executed-evidence gate (#145) archives a stale/low result before an escalation so only a
    fresh deep re-dispatch can license a skip.
  - **Changed surface from what ACTUALLY changed (#157/#158).** The changed surface for the
    next round is derived from the git diff of the branch — `round-<N>/diff.txt` (what the
    reviewers saw) vs `round-<N>/head-diff.txt` (the post-fix tree, `git diff <base>...HEAD`
    written by the orchestrator right before the gate) — the FILES whose hunks differ, mapped
    to policy subjects through `round-<N>/compiled.json` (the reviewers' own findings, reusing
    the spine's file→subject mapping). NEVER the fixer's self-report. Any missing/unreadable
    input → "unknown" → run-all.

Every failure — corrupt scheduler state, unreadable fix-batch, missing diff — fails toward
MORE review (a full `reviewer-deep` round), never toward a skip or an exit. Tiers are
`model_tier_resolve` role names (`reviewer`/`reviewer-deep`), never model names. stdlib only.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loop_state  # noqa: E402
import review_round_policy  # noqa: E402
import loop_plan_common as common  # noqa: E402

DEEP = common.DEEP
CHEAP = common.CHEAP
DIMENSIONS = ["architecture-reviewer", "code-reviewer", "security-reviewer",
              "test-reviewer", "premortem-reviewer"]
AGENT_SUFFIX = {"architecture-reviewer": "architecture", "code-reviewer": "code",
                "security-reviewer": "security", "test-reviewer": "test",
                "premortem-reviewer": "premortem"}
_DIFF_GIT = re.compile(r"^diff --git a/(.*) b/(.*)$")


# --- session-dir plumbing (round-scoped) --------------------------------------

def _round_dir(session_dir, round_no):
    return os.path.join(session_dir, "round-%d" % round_no)


def _findings_path(session_dir, round_no, dimension):
    suffix = AGENT_SUFFIX.get(dimension) or str(dimension)
    return os.path.join(_round_dir(session_dir, round_no), "findings-%s.json" % suffix)


def _diff_path(session_dir, round_no):
    return os.path.join(_round_dir(session_dir, round_no), "diff.txt")


def _head_diff_path(session_dir, round_no):
    return os.path.join(_round_dir(session_dir, round_no), "head-diff.txt")


def _compiled_path(session_dir, round_no):
    return os.path.join(_round_dir(session_dir, round_no), "compiled.json")


def _archive_findings(session_dir, round_no, dimension, tag=None):
    """Move a dimension's findings file out of the live slot so only a file written AFTER this
    call can count as that dimension's next result (the executed-evidence gate)."""
    src = _findings_path(session_dir, round_no, dimension)
    if not os.path.exists(src):
        return
    archive_dir = os.path.join(_round_dir(session_dir, round_no), "archive")
    name = "findings-%s%s.json" % (AGENT_SUFFIX.get(dimension, dimension),
                                   (".%s" % tag) if tag else "")
    try:
        os.makedirs(archive_dir, exist_ok=True)
        os.replace(src, os.path.join(archive_dir, name))
    except OSError:
        # fail toward run-all, never toward a stale read: a file we cannot move must not remain
        # readable as a fresh result
        try:
            os.unlink(src)
        except OSError:
            pass


# --- changed-surface diff (git file-path derivation, #157/#158) ---------------

def _read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _files_in_diff(text):
    """Map each file in a unified diff to its per-file section text (index + hunks). Comparing
    a file's section between two diffs-vs-base tells us whether the fix touched it: the section
    (blob-hash `index` line included) differs iff the file's content changed."""
    files = {}
    path = None
    buf = []

    def _flush():
        if path is not None:
            files[path] = "\n".join(buf)

    for line in (text or "").splitlines():
        m = _DIFF_GIT.match(line)
        if m:
            _flush()
            path = m.group(2)
            buf = []
        elif path is not None:
            buf.append(line)
    _flush()
    return files


def _changed_files(old_text, new_text):
    old = _files_in_diff(old_text)
    new = _files_in_diff(new_text)
    return {p for p in set(old) | set(new) if old.get(p) != new.get(p)}


def _subjects_for_dimension(dimension):
    """Policy subjects mentioned by a compiled finding's dimension label — a single label
    ('Security') or a merged one ('Security + Code'). Reuses the shared twin's mapping so the
    prose path and the spine derive subjects the same way (never a second mapping)."""
    out = set()
    if not isinstance(dimension, str):
        return out
    for token in re.split(r"[^A-Za-z-]+", dimension):
        subject = review_round_policy._policy_subject(token)
        if subject:
            out.add(subject)
    return out


def _changed_subjects(session_dir, old_round, new_round):
    """The policy subjects the fix touched between `old_round`'s reviewed diff and the current
    (post-fix) tree captured in `new_round`'s head-diff, mapped through `new_round`'s compiled
    findings. Returns a KNOWN list (possibly empty) or None (unknown → the policy runs all
    dimensions). Any missing/unreadable diff or compiled file → None."""
    old_text = _read_text(_diff_path(session_dir, old_round))
    new_text = _read_text(_head_diff_path(session_dir, new_round))
    if old_text is None or new_text is None:
        return None
    changed = _changed_files(old_text, new_text)
    try:
        with open(_compiled_path(session_dir, new_round), encoding="utf-8") as fh:
            compiled = json.load(fh)
    except (OSError, ValueError):
        return None
    findings = compiled.get("findings") if isinstance(compiled, dict) else None
    if not isinstance(findings, list):
        return None
    subjects = set()
    for finding in findings:
        if isinstance(finding, dict) and finding.get("file") in changed:
            subjects |= _subjects_for_dimension(finding.get("dimension"))
    return sorted(subjects)


# --- verbs --------------------------------------------------------------------

def cmd_plan(session_dir, round_no, dimensions):
    state_ok, state = common.load_state(session_dir)
    entry = (state.get("rounds") or {}).get(str(round_no)) or {}
    plan = entry.get("plan") if state_ok else None
    plan_created = False
    if not isinstance(plan, dict) or not isinstance(plan.get("dimensions"), dict):
        if round_no <= 1:
            plan = review_round_policy.plan_round(
                {"round": 1, "dimensions": dimensions, "changedSubjects": [], "previous": {}})
        else:
            plan = common._run_all_plan(
                dimensions, "no persisted plan for round %d — fail toward run-all" % round_no)
        state = common._persist_plan(session_dir, state, round_no, plan, state_ok)
        plan_created = True
    if plan_created:
        state_ok, state = common.load_state(session_dir)
    entry = (state.get("rounds") or {}).get(str(round_no)) or {}
    plan = common._overlay_escalations(plan, entry.get("escalations") or {})
    dims_to_run, skipped = common._plan_lists(plan, dimensions)
    return {"ok": True, "round": round_no, "roundKind": plan.get("roundKind"),
            "dims_to_run": dims_to_run, "skipped": skipped}


def cmd_record(session_dir, round_no, dimensions):
    state_ok, state = common.load_state(session_dir)
    if not state_ok:
        state = {"schemaVersion": 1, "rounds": {}, "rebuilt": True}
    entry = common._round_entry(state, round_no)
    plan = entry.get("plan")
    if not isinstance(plan, dict) or not isinstance(plan.get("dimensions"), dict):
        plan = common._run_all_plan(dimensions, "no persisted plan — recorded as a full deep round")
        entry["plan"] = plan
    escalations = entry.setdefault("escalations", {})
    dims = entry.setdefault("dims", {})
    escalate = []
    for d in dimensions:
        sched = (plan.get("dimensions") or {}).get(d) or {"action": "run", "tier": DEEP}
        if sched.get("action") == "skip":
            dims[d] = common._carry_forward(state, d, round_no, sched)
            continue
        already = bool(escalations.get(d))
        tier = DEEP if already else (sched.get("tier") or DEEP)
        result = common.read_findings_file(_findings_path(session_dir, round_no, d), tier)
        needs_more = (not result["valid"]) or (tier == CHEAP and result["confidence"] != "high")
        if needs_more and not already:
            # one escalation/retry at reviewer-deep — archive the low/invalid result so only a
            # freshly-written file can count as the deep answer
            escalations[d] = {"from": tier}
            _archive_findings(session_dir, round_no, d,
                              tag="cheap" if tier == CHEAP else "retry")
            why = result.get("why") or ("low-confidence %s result" % CHEAP)
            escalate.append({"dimension": d, "tier": DEEP,
                             "reason": "%s — re-dispatch once at %s" % (why, DEEP)})
            dims[d] = {"dimension": d, "status": "escalation-pending", "round": round_no}
            continue
        if not result["valid"]:
            _archive_findings(session_dir, round_no, d, tag="invalid")
            dims[d] = {"dimension": d, "status": "missing", "confidence": "low",
                       "round": round_no}
            continue
        dims[d] = {"dimension": d, "status": "run", "tier": tier,
                   "confidence": result["confidence"], "hasFindings": result["hasFindings"],
                   "blockingCount": result["blocking"], "criticalCount": result["critical"],
                   "subjects": common._subjects(d, result["findings"]),
                   "escalated": already, "round": round_no}
    common.save_state(session_dir, state)
    return {"ok": True, "round": round_no, "escalate": escalate, "dimensions": dims}


def _further_confirmation_owed(session_dir, state, round_no, dimensions):
    """#174: is a FURTHER full confirmation panel owed? The mandatory first panel is always owed;
    after one QUALIFYING panel has run, the follow-up decision is computed over EVERYTHING SINCE
    THAT PANEL — the severities surfaced by the panel and every later scoped round, and the rework
    applied since (the changed file surface diffed from the panel's own diff, so multi-round rework
    and an unknown surface both fail toward one more panel). A Critical still owed at the cap parks."""
    confirmations = common._confirmation_rounds(state, dimensions)
    if not confirmations:
        return {"owed": True, "park": False, "panels": 0, "surfaced": False}
    last_round = confirmations[-1][0]
    surfaced = common._surfaced_severities_since(state, last_round)
    cross = review_round_policy.is_cross_cutting(
        _changed_subjects(session_dir, last_round, round_no))
    followup = review_round_policy.confirmation_followup(surfaced, len(confirmations), cross)
    return {"owed": followup["rearm"], "park": followup["park"], "panels": len(confirmations),
            "reason": followup["reason"], "surfaced": bool(surfaced)}


def _next_round_out(session_dir, state, state_ok, round_no, plan, action, mandatory, reason,
                    dimensions):
    dims_to_run, skipped = common._plan_lists(plan, dimensions)
    common._persist_plan(session_dir, state, round_no + 1, plan, state_ok)
    return {"action": action, "mandatory": mandatory, "reason": reason,
            "round": round_no, "nextRound": round_no + 1,
            "roundKind": plan.get("roundKind"),
            "dims_to_run": dims_to_run, "skipped": skipped}


def cmd_decide(session_dir, round_no, max_rounds, fix_batch, resolutions, breaker_halt,
               dimensions):
    state_ok, state = common.load_state(session_dir)
    try:
        blocking_fixed = (loop_state._blocking_fixed_from_fix_batch(fix_batch)
                          if fix_batch else 0)
        skipped_blocking = (loop_state._skipped_blocking_from_resolutions(resolutions)
                            if resolutions else 0)
    except (OSError, ValueError, TypeError, AttributeError, KeyError, json.JSONDecodeError) as exc:
        # fail SAFE toward more review, never toward a silent exit or a skip
        plan = review_round_policy.plan_round(
            {"round": round_no + 1, "dimensions": dimensions,
             "changedSubjects": None, "previous": {}})
        return _next_round_out(
            session_dir, state, state_ok, round_no, plan, "review", True,
            "could not read the round artifacts (%s) — defaulting to another full review "
            "round rather than risk a premature exit." % exc, dimensions)

    action, mandatory, reason = loop_state.decide(
        blocking_fixed, skipped_blocking, round_no, max_rounds, breaker_halt)

    if action in ("exit_clean", "exit_skipped"):
        if state_ok and common._full_deep_executed(state, round_no, dimensions):
            return {"action": action, "mandatory": mandatory, "reason": reason,
                    "round": round_no, "nextRound": None, "roundKind": None,
                    "dims_to_run": [], "skipped": [],
                    "certification": {"fullPanels": len(common._confirmation_rounds(state, dimensions)),
                                      "lastPanelSurfacedResolved": False}}
        # #174 confirmation-bar economics: once a QUALIFYING full confirmation panel has run, another
        # is owed ONLY when its follow-up (a Critical surfaced since — panel or later scoped round —
        # or cross-cutting rework, under the cap) demands it. When the obligation is satisfied,
        # certify off the scoped verify rather than ratcheting a fresh fully-clean panel; a Critical
        # still owed at the cap parks.
        owe = _further_confirmation_owed(session_dir, state, round_no, dimensions) if state_ok \
            else {"owed": True, "park": False, "panels": 0, "surfaced": False}
        if owe["park"]:
            return {"action": "halt", "mandatory": True,
                    "reason": "%s — report this round's findings; do NOT declare READY FOR PR."
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
                              "NOT declare READY FOR PR." % (max_rounds, DEEP),
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
        changed = _changed_subjects(session_dir, round_no, round_no) if state_ok else None
        previous = common._previous_dims(state, round_no) if state_ok else {}
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
        description="review-code's script-owned round scheduler + continuation gate")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "record", "decide"):
        p = sub.add_parser(name)
        p.add_argument("--session-dir", required=True)
        p.add_argument("--round", type=int, required=True, dest="rnd")
        p.add_argument("--dimensions", default=None,
                       help="JSON list of reviewer names (default: the five specialists)")
        if name == "decide":
            p.add_argument("--max-rounds", type=int, default=7)
            p.add_argument("--fix-batch", default=None,
                           help="round-<N>/fix-batch.json (derives blocking-fixed)")
            p.add_argument("--resolutions", default=None,
                           help="round-<N>/resolutions.json (derives skipped-blocking)")
            p.add_argument("--breaker-halt", choices=["yes", "no"], default="no")
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
        out = cmd_decide(args.session_dir, args.rnd, args.max_rounds, args.fix_batch,
                         args.resolutions, args.breaker_halt == "yes", dimensions)
    sys.stdout.write(json.dumps(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
