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
    can never license a skip (the 2026-07-03 zero-token-stub class). Dimension confidence
    is derived from the findings JSON shape (the spine's legacy-array rule: an array is
    high-confidence unless it is a non-empty `reviewer`-tier result), never from prose.
  - **Changed surface from the script's own snapshots.** Each round's spec copy is
    snapshotted (`spec-r<N>.md`); the changed surface for round N+1 is the diff of the
    script's snapshots — section headings whose text differs — never the reviser's
    self-report (#158's lesson: derive the surface from what actually changed). Any
    diff/shape failure yields "unknown" → run-all.
  - **Escalation semantic (#145).** A low-confidence `reviewer` result escalates ONCE to
    `reviewer-deep`; a missing/malformed result retries ONCE at `reviewer-deep`; after
    that it is recorded as missing (low confidence) — never a loop, and a low-confidence
    executed result stays recorded.
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
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loop_state  # noqa: E402
import review_round_policy  # noqa: E402

DEEP = "reviewer-deep"
CHEAP = "reviewer"
BLOCKING = ("Critical", "Important")
DIMENSIONS = ["architecture-reviewer", "code-reviewer", "security-reviewer",
              "test-reviewer", "premortem-reviewer"]
AGENT_SUFFIX = {"architecture-reviewer": "architecture", "code-reviewer": "code",
                "security-reviewer": "security", "test-reviewer": "test",
                "premortem-reviewer": "premortem"}
STATE_FILE = "loop-state.json"
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


# --- session-dir plumbing ---------------------------------------------------

def _state_path(session_dir):
    return os.path.join(session_dir, STATE_FILE)


def _findings_path(session_dir, dimension):
    suffix = AGENT_SUFFIX.get(dimension) or str(dimension)
    return os.path.join(session_dir, "findings-%s.json" % suffix)


def _snapshot_path(session_dir, round_no):
    return os.path.join(session_dir, "spec-r%d.md" % round_no)


def load_state(session_dir):
    """(ok, state). Missing file is ok (fresh); unreadable/corrupt is NOT ok — the caller
    fails toward run-all and rebuilds. Prior records are never clobbered by a failed read:
    only an explicit save writes."""
    path = _state_path(session_dir)
    if not os.path.exists(path):
        return True, {"schemaVersion": 1, "rounds": {}}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return False, {"schemaVersion": 1, "rounds": {}}
    if not isinstance(data, dict) or not isinstance(data.get("rounds"), dict):
        return False, {"schemaVersion": 1, "rounds": {}}
    return True, data


def save_state(session_dir, state):
    """Atomic replace so a crash mid-write cannot corrupt prior round records."""
    path = _state_path(session_dir)
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".loop-state-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
        return True
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return False


def _round_entry(state, round_no):
    return state["rounds"].setdefault(str(round_no), {})


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
    """Derive a dimension result from its findings JSON. Confidence is the spine's
    legacy-array rule (`_shapeReviewerResult`): an array is high-confidence unless it is a
    non-empty `reviewer`-tier result; an object may carry its own {findings, confidence}."""
    path = _findings_path(session_dir, dimension)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {"valid": False, "why": "missing"}
    except (OSError, ValueError):
        return {"valid": False, "why": "malformed"}
    if isinstance(data, list):
        findings = [f for f in data if isinstance(f, dict)]
        confidence = "low" if (tier == CHEAP and len(findings) > 0) else "high"
    elif isinstance(data, dict) and isinstance(data.get("findings"), list):
        findings = [f for f in data["findings"] if isinstance(f, dict)]
        confidence = str(data.get("confidence") or "").lower()
        if confidence not in ("high", "low"):
            return {"valid": False, "why": "malformed"}
    else:
        return {"valid": False, "why": "malformed"}
    return {
        "valid": True,
        "findings": findings,
        "confidence": confidence,
        "hasFindings": len(findings) > 0,
        "blocking": sum(1 for f in findings if f.get("severity") in BLOCKING),
    }


def _subjects(dimension, findings):
    subjects = {f.get("dimension") for f in findings
                if isinstance(f.get("dimension"), str) and f.get("dimension")}
    fallback = review_round_policy.SUBJECT_FALLBACK.get(
        str(dimension or "").split("-")[0].lower())
    if fallback:
        subjects.add(fallback)
    return sorted(subjects)


# --- plans --------------------------------------------------------------------

def _run_all_plan(dimensions, reason):
    return {"roundKind": "intermediate",
            "dimensions": {d: {"action": "run", "tier": DEEP, "reason": reason}
                           for d in dimensions},
            "escalationPolicy": "deep-only"}


def _plan_lists(plan, dimensions):
    dims_to_run, skipped = [], []
    scheduled = plan.get("dimensions") or {}
    for d in dimensions:
        info = scheduled.get(d) or {"action": "run", "tier": DEEP, "reason": "unscheduled — fail toward run"}
        if info.get("action") == "skip":
            skipped.append({"dimension": d, "reason": info.get("reason"),
                            "carriedFromRound": info.get("carriedFromRound")})
        else:
            dims_to_run.append({"dimension": d, "tier": info.get("tier") or DEEP,
                                "reason": info.get("reason")})
    return dims_to_run, skipped


def _overlay_escalations(plan, escalations):
    """Return a copy of *plan* with pending escalations emitted at reviewer-deep."""
    if not escalations:
        return plan
    overlay = {"roundKind": plan.get("roundKind"),
               "dimensions": dict(plan.get("dimensions") or {}),
               "escalationPolicy": plan.get("escalationPolicy")}
    for d in escalations:
        info = overlay["dimensions"].get(d)
        if isinstance(info, dict) and info.get("action") == "run":
            updated = dict(info)
            updated["tier"] = DEEP
            reason = updated.get("reason") or ""
            if " (pending escalation)" not in reason:
                updated["reason"] = "%s (pending escalation)" % reason
            overlay["dimensions"][d] = updated
    return overlay


def _persist_plan(session_dir, state, round_no, plan, state_ok):
    if not state_ok:
        state = {"schemaVersion": 1, "rounds": {}, "rebuilt": True}
    _round_entry(state, round_no)["plan"] = plan
    save_state(session_dir, state)
    return state


def _previous_dims(state, upto_round):
    """The latest recorded state per dimension across rounds ≤ upto_round — the twin of the
    shell's buildPreviousDimensionState (later rounds overwrite earlier ones)."""
    previous = {}
    for key in sorted(state.get("rounds") or {}, key=lambda k: int(k) if str(k).isdigit() else 0):
        if not str(key).isdigit() or int(key) > upto_round:
            continue
        dims = (state["rounds"][key] or {}).get("dims") or {}
        for name, rec in dims.items():
            if isinstance(rec, dict):
                previous[name] = rec
    return previous


def _full_deep_executed(state, round_no, dimensions):
    """True only when round N's every dimension ran FRESH at reviewer-deep with high
    confidence — the round shape the contract requires before any exit."""
    entry = (state.get("rounds") or {}).get(str(round_no)) or {}
    dims = entry.get("dims") or {}
    for d in dimensions:
        rec = dims.get(d)
        if not isinstance(rec, dict):
            return False
        if rec.get("status") != "run" or rec.get("confidence") != "high" or rec.get("tier") != DEEP:
            return False
    return True


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
        needs_more = (not result["valid"]) or (tier == CHEAP and result["confidence"] != "high")
        if needs_more and not already:
            # one escalation/retry at reviewer-deep — archive the low/invalid result so
            # only a freshly-written file can count as the deep answer
            escalations[d] = {"from": tier}
            _archive_findings(session_dir, d, round_no,
                              tag="cheap" if tier == CHEAP else "retry")
            why = result.get("why") or ("low-confidence %s result" % CHEAP)
            escalate.append({"dimension": d, "tier": DEEP,
                             "reason": "%s — re-dispatch once at %s" % (why, DEEP)})
            dims[d] = {"dimension": d, "status": "escalation-pending", "round": round_no}
            continue
        if not result["valid"]:
            dims[d] = {"dimension": d, "status": "missing", "confidence": "low",
                       "round": round_no}
            continue
        dims[d] = {"dimension": d, "status": "run", "tier": tier,
                   "confidence": result["confidence"], "hasFindings": result["hasFindings"],
                   "blockingCount": result["blocking"],
                   "subjects": _subjects(d, result["findings"]),
                   "escalated": already, "round": round_no}
    save_state(session_dir, state)
    return {"ok": True, "round": round_no, "escalate": escalate, "dimensions": dims}


def _next_round_out(session_dir, state, state_ok, round_no, plan, action, mandatory, reason,
                    dimensions):
    _snapshot(session_dir, round_no + 1, overwrite=True)
    dims_to_run, skipped = _plan_lists(plan, dimensions)
    for item in dims_to_run:
        _archive_findings(session_dir, item["dimension"], round_no)
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
                    "dims_to_run": [], "skipped": []}
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
