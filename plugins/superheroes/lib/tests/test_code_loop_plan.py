"""Tests for `code_loop_plan` — review-code's script-owned round scheduler + continuation
gate (#174 PR 2). The deliberate policy reversal: review-code no longer runs all five
specialists at fixed tiers every round; the schedule is script-decided, exactly like
review-spec's (#167).

These pin:
  - round 1 = full reviewer-deep baseline panel (the reversal upgrades round 1 to all-deep);
  - rounds ≥2 dispatch exactly the emitted dims_to_run — clean untouched dimensions skip,
    touched / prior-finding dimensions re-run cheap-first;
  - delegation to the parity-locked shared policy (`review_round_policy.plan_round`) and the
    continuation gate (`loop_state.decide`) — policy lives ONLY in the twins;
  - changedSubjects derived from what ACTUALLY changed — the git diff of `round-<N>/diff.txt`
    vs `round-<N>/head-diff.txt`, mapped to policy subjects through the compiled findings,
    NEVER the fixer's self-report (#157/#158);
  - the confirmation invariant + #174 confirmation-bar economics (Critical/cross-cutting
    re-arm, cap 2, Critical-at-cap parks, honest certification);
  - the review-code `--fix-batch`/`--resolutions` continuation contract is preserved as-is;
  - fail-safe direction: every corruption / unreadable input fails toward MORE review.
"""
import importlib.util
import json
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CLP = _load(os.path.join(_HERE, "..", "code_loop_plan.py"), "code_loop_plan")

DIMS = ["architecture-reviewer", "code-reviewer", "security-reviewer",
        "test-reviewer", "premortem-reviewer"]
SUFFIX = {"architecture-reviewer": "architecture", "code-reviewer": "code",
          "security-reviewer": "security", "test-reviewer": "test",
          "premortem-reviewer": "premortem"}
DEEP = "reviewer-deep"
CHEAP = "reviewer"


# --- fixtures -----------------------------------------------------------------

def _session(tmp_path):
    d = tmp_path / "sess"
    d.mkdir()
    return str(d)


def _round_dir(session_dir, round_no):
    d = os.path.join(session_dir, "round-%d" % round_no)
    os.makedirs(d, exist_ok=True)
    return d


def _write_findings(session_dir, round_no, dim, findings):
    _round_dir(session_dir, round_no)
    path = os.path.join(session_dir, "round-%d" % round_no, "findings-%s.json" % SUFFIX[dim])
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(findings, fh)
    return path


def _mk_diff(sections):
    """sections: list of (path, body). Build a git-style unified diff."""
    out = []
    for path, body in sections:
        out.append("diff --git a/%s b/%s" % (path, path))
        out.append("index 1111111..2222222 100644")
        out.append("--- a/%s" % path)
        out.append("+++ b/%s" % path)
        out.append(body)
    return "\n".join(out) + "\n"


def _write_diff(session_dir, round_no, sections):
    _round_dir(session_dir, round_no)
    with open(os.path.join(session_dir, "round-%d" % round_no, "diff.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(_mk_diff(sections))


def _write_head_diff(session_dir, round_no, sections):
    _round_dir(session_dir, round_no)
    with open(os.path.join(session_dir, "round-%d" % round_no, "head-diff.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(_mk_diff(sections))


def _write_compiled(session_dir, round_no, findings):
    _round_dir(session_dir, round_no)
    with open(os.path.join(session_dir, "round-%d" % round_no, "compiled.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"summary": "s", "verdict": "v", "findings": findings}, fh)


def _write_fix_batch(session_dir, round_no, findings):
    _round_dir(session_dir, round_no)
    path = os.path.join(session_dir, "round-%d" % round_no, "fix-batch.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(findings, fh)
    return path


def _write_resolutions(session_dir, round_no, resolutions):
    _round_dir(session_dir, round_no)
    path = os.path.join(session_dir, "round-%d" % round_no, "resolutions.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"round": round_no, "resolutions": resolutions}, fh)
    return path


def _finding(dim_label, severity="Important", file="fileA.py", line=5):
    return {"id": "x-001", "severity": severity, "dimension": dim_label,
            "title": "problem", "file": file, "line": line, "body": "b"}


def _run(capsys, *args):
    rc = CLP.main(list(args))
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    return out


def _plan(capsys, session_dir, rnd):
    return _run(capsys, "plan", "--session-dir", session_dir, "--round", str(rnd))


def _record(capsys, session_dir, rnd):
    return _run(capsys, "record", "--session-dir", session_dir, "--round", str(rnd))


def _decide(capsys, session_dir, rnd, fix_batch=None, resolutions=None, breaker="no",
            max_rounds=7):
    args = ["decide", "--session-dir", session_dir, "--round", str(rnd),
            "--max-rounds", str(max_rounds), "--breaker-halt", breaker]
    if fix_batch is not None:
        args += ["--fix-batch", fix_batch]
    if resolutions is not None:
        args += ["--resolutions", resolutions]
    return _run(capsys, *args)


def _dims_map(out):
    return {d["dimension"]: d for d in out["dims_to_run"]}


def _round1(capsys, session_dir, findings_by_dim=None):
    """Drive a full baseline round: plan, write findings files, record."""
    plan = _plan(capsys, session_dir, 1)
    findings_by_dim = findings_by_dim or {}
    for dim in DIMS:
        _write_findings(session_dir, 1, dim, findings_by_dim.get(dim, []))
    rec = _record(capsys, session_dir, 1)
    return plan, rec


# --- plan ---------------------------------------------------------------------

def test_plan_round1_is_baseline_full_deep(tmp_path, capsys):
    out = _plan(capsys, _session(tmp_path), 1)
    assert out["ok"] is True
    assert out["roundKind"] == "baseline"
    dims = _dims_map(out)
    assert sorted(dims) == sorted(DIMS)
    assert all(d["tier"] == DEEP for d in dims.values())  # reversal: round 1 = ALL deep
    assert out["skipped"] == []


def test_plan_missing_state_round2_fails_toward_run_all_deep(tmp_path, capsys):
    session_dir = _session(tmp_path)
    out = _plan(capsys, session_dir, 2)  # no persisted plan for round 2
    dims = _dims_map(out)
    assert sorted(dims) == sorted(DIMS)
    assert all(d["tier"] == DEEP for d in dims.values())


def test_custom_dimensions_list_is_honored(tmp_path, capsys):
    session_dir = _session(tmp_path)
    out = _run(capsys, "plan", "--session-dir", session_dir, "--round", "1",
               "--dimensions", json.dumps(["code-reviewer", "security-reviewer"]))
    assert sorted(_dims_map(out)) == ["code-reviewer", "security-reviewer"]


def test_malformed_dimensions_falls_back_to_default_roster(tmp_path, capsys):
    session_dir = _session(tmp_path)
    out = _run(capsys, "plan", "--session-dir", session_dir, "--round", "1",
               "--dimensions", "{not json")
    assert sorted(_dims_map(out)) == sorted(DIMS)


# --- record -------------------------------------------------------------------

def test_record_baseline_fresh_clean_is_high_confidence(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir)
    rec = _record(capsys, session_dir, 1)
    for dim in DIMS:
        r = rec["dimensions"][dim]
        assert r["status"] == "run" and r["confidence"] == "high" and r["tier"] == DEEP
    assert rec["escalate"] == []


def test_record_missing_file_escalates_once_then_missing(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _plan(capsys, session_dir, 1)
    # write four; omit code-reviewer's file
    for dim in DIMS:
        if dim != "code-reviewer":
            _write_findings(session_dir, 1, dim, [])
    rec = _record(capsys, session_dir, 1)
    assert any(e["dimension"] == "code-reviewer" and e["tier"] == DEEP for e in rec["escalate"])
    assert rec["dimensions"]["code-reviewer"]["status"] == "escalation-pending"
    # still missing on the retry → recorded missing (low confidence), never a loop
    rec2 = _record(capsys, session_dir, 1)
    assert rec2["escalate"] == []
    assert rec2["dimensions"]["code-reviewer"]["status"] == "missing"
    assert rec2["dimensions"]["code-reviewer"]["confidence"] == "low"


def test_cheap_nonempty_escalates_once_to_deep(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _reach_round2_scoped(tmp_path, capsys, session_dir)
    plan2 = _plan(capsys, session_dir, 2)
    dims2 = _dims_map(plan2)
    assert dims2["code-reviewer"]["tier"] == CHEAP  # prior finding → cheap-first
    _write_findings(session_dir, 2, "code-reviewer", [_finding("Code")])  # nonempty at cheap = low conf
    rec = _record(capsys, session_dir, 2)
    assert any(e["dimension"] == "code-reviewer" and e["tier"] == DEEP for e in rec["escalate"])
    # deep re-dispatch clean → recorded run/high
    _write_findings(session_dir, 2, "code-reviewer", [])
    rec2 = _record(capsys, session_dir, 2)
    assert rec2["dimensions"]["code-reviewer"]["status"] == "run"
    assert rec2["dimensions"]["code-reviewer"]["tier"] == DEEP


def test_cheap_empty_result_stands_without_escalation(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _reach_round2_scoped(tmp_path, capsys, session_dir)
    _plan(capsys, session_dir, 2)
    _write_findings(session_dir, 2, "code-reviewer", [])  # cheap + empty = high conf clean
    rec = _record(capsys, session_dir, 2)
    assert rec["escalate"] == []
    assert rec["dimensions"]["code-reviewer"]["status"] == "run"


# --- changed-surface derivation (git diff, not self-report) -------------------

def _reach_round2_scoped(tmp_path, capsys, session_dir):
    """Round 1: code-reviewer flags fileA.py (Code); others clean. The round-1 fix modifies
    fileA.py only. Drive to a `review` decide so round 2's schedule is persisted."""
    _round1(capsys, session_dir, {"code-reviewer": [_finding("Code", file="fileA.py")]})
    _write_compiled(session_dir, 1, [_finding("Code", file="fileA.py"),
                                     _finding("Security", file="fileB.py", severity="Minor")])
    _write_diff(session_dir, 1, [("fileA.py", "@@ -1 +1 @@\n-old\n+new"),
                                 ("fileB.py", "@@ -1 +1 @@\n-x\n+y")])
    # post-fix: fileA.py section changed, fileB.py unchanged
    _write_head_diff(session_dir, 1, [("fileA.py", "@@ -1 +2 @@\n-old\n+new\n+more"),
                                      ("fileB.py", "@@ -1 +1 @@\n-x\n+y")])
    fb = _write_fix_batch(session_dir, 1, [_finding("Code", file="fileA.py")])  # blocking fixed
    out = _decide(capsys, session_dir, 1, fix_batch=fb)
    assert out["action"] == "review"
    return out


def test_changed_subjects_from_diff_schedules_scoped_round(tmp_path, capsys):
    session_dir = _session(tmp_path)
    out = _reach_round2_scoped(tmp_path, capsys, session_dir)
    assert out["roundKind"] == "intermediate"
    run = {d["dimension"]: d for d in out["dims_to_run"]}
    skipped = {s["dimension"] for s in out["skipped"]}
    # only code re-runs (prior finding + its file fileA.py actually changed); the clean,
    # untouched dimensions skip — the whole point of the reversal.
    assert "code-reviewer" in run and run["code-reviewer"]["tier"] == CHEAP
    assert {"architecture-reviewer", "security-reviewer", "test-reviewer",
            "premortem-reviewer"} <= skipped


def test_changed_subjects_ignores_fixer_self_report(tmp_path, capsys):
    """Even if a (hypothetical) fixer claimed it touched security, the scheduler derives the
    surface from the git diff: fileB.py (security) did NOT change between diff and head-diff,
    so Security is NOT forced to re-run."""
    session_dir = _session(tmp_path)
    out = _reach_round2_scoped(tmp_path, capsys, session_dir)
    skipped = {s["dimension"] for s in out["skipped"]}
    assert "security-reviewer" in skipped


def test_unknown_surface_missing_head_diff_runs_all(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir, {"code-reviewer": [_finding("Code")]})
    _write_compiled(session_dir, 1, [_finding("Code")])
    _write_diff(session_dir, 1, [("fileA.py", "@@ -1 +1 @@\n-old\n+new")])
    # NO head-diff.txt written → unknown surface → run all deep
    fb = _write_fix_batch(session_dir, 1, [_finding("Code")])
    out = _decide(capsys, session_dir, 1, fix_batch=fb)
    assert out["action"] == "review"
    dims = _dims_map(out)
    assert sorted(dims) == sorted(DIMS)
    assert all(d["tier"] == DEEP for d in dims.values())


# --- confirmation invariant + exits -------------------------------------------

def test_clean_full_deep_baseline_exits_clean(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir)  # all clean, all deep
    fb = _write_fix_batch(session_dir, 1, [])  # nothing to fix
    out = _decide(capsys, session_dir, 1, fix_batch=fb)
    assert out["action"] == "exit_clean"
    assert out["certification"]["fullPanels"] == 0  # baseline is not a "confirmation" panel


def test_exit_skipped_from_full_deep_round(tmp_path, capsys):
    """arch-r2-001 contract preserved: skipped-blocking is derived from resolutions, blocking-
    fixed from fix-batch. A full-deep round with only a deliberately-skipped blocker exits
    CLEAN-EXCEPT-FOR-SKIPPED."""
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir, {"security-reviewer": [_finding("Security")]})
    fb = _write_fix_batch(session_dir, 1, [])  # nothing fixed
    res = _write_resolutions(session_dir, 1, [{"id": "x-001", "severity": "Important",
                                               "action": "skip"}])
    out = _decide(capsys, session_dir, 1, fix_batch=fb, resolutions=res)
    assert out["action"] == "exit_skipped"


def test_clean_reduced_round_requires_full_deep_confirmation(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _reach_round2_scoped(tmp_path, capsys, session_dir)
    # round 2 = scoped (code cheap, rest skipped); it comes back clean
    _plan(capsys, session_dir, 2)
    _write_findings(session_dir, 2, "code-reviewer", [])
    _record(capsys, session_dir, 2)
    fb2 = _write_fix_batch(session_dir, 2, [])  # nothing to fix this round
    out = _decide(capsys, session_dir, 2, fix_batch=fb2)
    # NOT full-deep executed (round 2 was reduced) → a mandatory confirmation round is owed
    assert out["action"] == "review"
    assert out["roundKind"] == "confirmation"
    dims = _dims_map(out)
    assert sorted(dims) == sorted(DIMS) and all(d["tier"] == DEEP for d in dims.values())


def _drive_confirmation(tmp_path, capsys, session_dir, conf_round, surfacing=None):
    """Plan+record a full-deep confirmation round `conf_round` where every dim runs deep/high;
    `surfacing` maps dim→findings to surface a blocker in the confirmation panel."""
    _plan(capsys, session_dir, conf_round)
    surfacing = surfacing or {}
    for dim in DIMS:
        _write_findings(session_dir, conf_round, dim, surfacing.get(dim, []))
    _record(capsys, session_dir, conf_round)


def test_confirmation_round_clean_exits(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _reach_round2_scoped(tmp_path, capsys, session_dir)
    _plan(capsys, session_dir, 2)
    _write_findings(session_dir, 2, "code-reviewer", [])
    _record(capsys, session_dir, 2)
    _decide(capsys, session_dir, 2, fix_batch=_write_fix_batch(session_dir, 2, []))
    # round 3 = the confirmation panel, clean
    _drive_confirmation(tmp_path, capsys, session_dir, 3)
    out = _decide(capsys, session_dir, 3, fix_batch=_write_fix_batch(session_dir, 3, []))
    assert out["action"] == "exit_clean"


def _reach_confirmation_surfacing(tmp_path, capsys, session_dir, severity):
    """Drive to a confirmation panel (round 3) that surfaces one blocking finding of `severity`
    in code-reviewer, then return the decide output at round 3."""
    _reach_round2_scoped(tmp_path, capsys, session_dir)
    _plan(capsys, session_dir, 2)
    _write_findings(session_dir, 2, "code-reviewer", [])
    _record(capsys, session_dir, 2)
    _decide(capsys, session_dir, 2, fix_batch=_write_fix_batch(session_dir, 2, []))
    _drive_confirmation(tmp_path, capsys, session_dir, 3,
                        {"code-reviewer": [_finding("Code", severity=severity)]})
    # the confirmation surfaced a blocker → it is fixed this round (fix-batch carries it)
    _write_compiled(session_dir, 3, [_finding("Code", severity=severity)])
    _write_diff(session_dir, 3, [("fileA.py", "@@ -1 +1 @@\n-a\n+b")])
    _write_head_diff(session_dir, 3, [("fileA.py", "@@ -1 +2 @@\n-a\n+b\n+c")])
    fb = _write_fix_batch(session_dir, 3, [_finding("Code", severity=severity)])
    return _decide(capsys, session_dir, 3, fix_batch=fb)


def test_confirmation_surfacing_important_certifies_after_scoped_verify(tmp_path, capsys):
    """#174 requirement 1/2: a confirmation that surfaces an Important does not forfeit
    certification — it is fixed + scoped-verified, then the loop certifies (no ratchet)."""
    session_dir = _session(tmp_path)
    out = _reach_confirmation_surfacing(tmp_path, capsys, session_dir, "Important")
    # the fix is a blocking fix → one scoped re-review round (mandatory), then it certifies.
    assert out["action"] == "review"
    assert out["roundKind"] == "intermediate"  # scoped, NOT a fresh full confirmation panel
    run = {d["dimension"] for d in out["dims_to_run"]}
    assert run == {"code-reviewer"}  # only the surfaced dimension re-runs


def test_confirmation_surfacing_critical_rearms_one_more_confirmation(tmp_path, capsys):
    """#174 requirement 2: a Critical surfaced by a confirmation re-arms one more full panel.
    Like the spec leg: the panel's Critical is fixed → a mandatory SCOPED re-review verifies the
    fix (loop_state returns `review`); the re-arm to a full confirmation fires on the next clean
    decide, via the economics (a Critical surfaced since the last qualifying panel)."""
    session_dir = _session(tmp_path)
    out3 = _reach_confirmation_surfacing(tmp_path, capsys, session_dir, "Critical")
    assert out3["action"] == "review" and out3["roundKind"] == "intermediate"  # scoped fix-verify
    # round 4 = scoped re-review of code-reviewer, now clean
    _plan(capsys, session_dir, 4)
    _write_findings(session_dir, 4, "code-reviewer", [])
    _record(capsys, session_dir, 4)
    _write_compiled(session_dir, 4, [])
    _write_head_diff(session_dir, 4, [("fileA.py", "@@ -1 +2 @@\n-a\n+b\n+c")])  # narrow rework
    out4 = _decide(capsys, session_dir, 4, fix_batch=_write_fix_batch(session_dir, 4, []))
    assert out4["action"] == "review"
    assert out4["roundKind"] == "confirmation"  # re-armed full panel (Critical since the panel)
    assert out4["nextRound"] == 5


def test_important_after_confirmation_certifies_not_ratchet(tmp_path, capsys):
    """After the confirmation panel + a scoped fix of its Important, the loop certifies with ONE
    panel — it does not require a fresh fully-clean panel."""
    session_dir = _session(tmp_path)
    _reach_confirmation_surfacing(tmp_path, capsys, session_dir, "Important")
    # round 4 = the scoped re-review of code-reviewer, now clean; nothing to fix
    _plan(capsys, session_dir, 4)
    _write_findings(session_dir, 4, "code-reviewer", [])
    _record(capsys, session_dir, 4)
    # keep the surface stable/narrow so rework is not cross-cutting
    _write_compiled(session_dir, 4, [])
    _write_diff(session_dir, 3, [("fileA.py", "@@ -1 +1 @@\n-a\n+b")])
    _write_head_diff(session_dir, 4, [("fileA.py", "@@ -1 +1 @@\n-a\n+b")])
    out = _decide(capsys, session_dir, 4, fix_batch=_write_fix_batch(session_dir, 4, []))
    assert out["action"] == "exit_clean"
    assert out["certification"]["fullPanels"] == 1


# --- confirmation-bar economics: cap + cross-cutting --------------------------

def _state(session_dir):
    with open(os.path.join(session_dir, "loop-state.json"), encoding="utf-8") as fh:
        return json.load(fh)


def test_critical_at_cap_parks(tmp_path, capsys, monkeypatch):
    """#174 requirement 3: a Critical still owed at the 2-panel cap parks (certification
    withheld); the fail-safe direction is unchanged."""
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir)
    # forge state: two qualifying confirmation panels already ran, and a Critical surfaced since
    st = {"schemaVersion": 1, "rounds": {}}
    deep_high = lambda blk=0, crit=0: {  # noqa: E731
        d: {"dimension": d, "status": "run", "tier": DEEP, "confidence": "high",
            "blockingCount": blk, "criticalCount": crit, "round": None} for d in DIMS}
    for rnd in (2, 3):
        st["rounds"][str(rnd)] = {"plan": {"roundKind": "confirmation"},
                                  "dims": {**deep_high()}}
    # a post-panel scoped round surfaced a Critical
    st["rounds"]["4"] = {"plan": {"roundKind": "intermediate"},
                         "dims": {"code-reviewer": {"dimension": "code-reviewer", "status": "run",
                                                    "tier": DEEP, "confidence": "high",
                                                    "blockingCount": 1, "criticalCount": 1,
                                                    "round": 4}}}
    with open(os.path.join(session_dir, "loop-state.json"), "w", encoding="utf-8") as fh:
        json.dump(st, fh)
    out = _decide(capsys, session_dir, 4, fix_batch=_write_fix_batch(session_dir, 4, []))
    assert out["action"] == "halt"
    assert out["certification"]["fullPanels"] == 2


def test_non_critical_at_cap_certifies_with_scoped_verify(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir)
    st = {"schemaVersion": 1, "rounds": {}}
    deep_high = {d: {"dimension": d, "status": "run", "tier": DEEP, "confidence": "high",
                     "blockingCount": 0, "criticalCount": 0, "round": None} for d in DIMS}
    for rnd in (2, 3):
        st["rounds"][str(rnd)] = {"plan": {"roundKind": "confirmation"}, "dims": dict(deep_high)}
    st["rounds"]["4"] = {"plan": {"roundKind": "intermediate"},
                         "dims": {"code-reviewer": {"dimension": "code-reviewer", "status": "run",
                                                    "tier": DEEP, "confidence": "high",
                                                    "blockingCount": 1, "criticalCount": 0,
                                                    "round": 4}}}
    with open(os.path.join(session_dir, "loop-state.json"), "w", encoding="utf-8") as fh:
        json.dump(st, fh)
    out = _decide(capsys, session_dir, 4, fix_batch=_write_fix_batch(session_dir, 4, []))
    assert out["action"] == "exit_clean"
    assert out["certification"]["fullPanels"] == 2
    assert out["certification"]["lastPanelSurfacedResolved"] is True


def test_cross_cutting_rework_rearms_one_more_confirmation(tmp_path, capsys):
    """#174 deferred-decision default: rework touching ≥3 policy subjects is cross-cutting and
    re-arms one more full confirmation, even when no Critical surfaced."""
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir)
    st = {"schemaVersion": 1, "rounds": {}}
    deep_high = {d: {"dimension": d, "status": "run", "tier": DEEP, "confidence": "high",
                     "blockingCount": 0, "criticalCount": 0, "round": None} for d in DIMS}
    st["rounds"]["2"] = {"plan": {"roundKind": "confirmation"}, "dims": dict(deep_high)}
    with open(os.path.join(session_dir, "loop-state.json"), "w", encoding="utf-8") as fh:
        json.dump(st, fh)
    # rework since the panel touched 3 files mapped to 3 distinct subjects
    _write_diff(session_dir, 2, [("a.py", "@@ -1 +1 @@\n-x\n+y")])
    _write_head_diff(session_dir, 3, [("a.py", "@@ -1 +2 @@\n-x\n+y\n+z"),
                                      ("b.py", "@@ -1 +1 @@\n-p\n+q"),
                                      ("c.py", "@@ -1 +1 @@\n-m\n+n")])
    _write_compiled(session_dir, 3, [_finding("Code", file="a.py"),
                                     _finding("Security", file="b.py"),
                                     _finding("Test", file="c.py")])
    out = _decide(capsys, session_dir, 3, fix_batch=_write_fix_batch(session_dir, 3, []))
    assert out["action"] == "review"
    assert out["roundKind"] == "confirmation"


# --- fail-safe direction ------------------------------------------------------

def test_breaker_halt_halts(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir, {"code-reviewer": [_finding("Code")]})
    fb = _write_fix_batch(session_dir, 1, [_finding("Code")])
    out = _decide(capsys, session_dir, 1, fix_batch=fb, breaker="yes")
    assert out["action"] == "halt"


def test_unreadable_fix_batch_fails_safe_to_review(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir)
    out = _decide(capsys, session_dir, 1, fix_batch=os.path.join(session_dir, "nope.json"))
    assert out["action"] == "review"
    dims = _dims_map(out)
    assert sorted(dims) == sorted(DIMS)


def test_corrupt_state_fails_toward_run_all_deep(tmp_path, capsys):
    session_dir = _session(tmp_path)
    with open(os.path.join(session_dir, "loop-state.json"), "w", encoding="utf-8") as fh:
        fh.write("{ not json")
    fb = _write_fix_batch(session_dir, 2, [_finding("Code")])
    out = _decide(capsys, session_dir, 2, fix_batch=fb)
    assert out["action"] == "review"
    dims = _dims_map(out)
    assert sorted(dims) == sorted(DIMS)
    assert all(d["tier"] == DEEP for d in dims.values())


def test_corrupt_state_blocks_exit_and_forces_confirmation(tmp_path, capsys):
    session_dir = _session(tmp_path)
    with open(os.path.join(session_dir, "loop-state.json"), "w", encoding="utf-8") as fh:
        fh.write("{ not json")
    fb = _write_fix_batch(session_dir, 3, [])  # nothing fixed → would be exit_clean
    out = _decide(capsys, session_dir, 3, fix_batch=fb)
    assert out["action"] == "review"  # corrupt state can't certify → confirmation owed
    assert out["roundKind"] == "confirmation"


def test_cap_before_confirmation_halts(tmp_path, capsys):
    """A clean reduced round at the round cap, with no confirmation panel yet run, halts rather
    than declaring READY FOR PR."""
    session_dir = _session(tmp_path)
    _reach_round2_scoped(tmp_path, capsys, session_dir)
    _plan(capsys, session_dir, 2)
    _write_findings(session_dir, 2, "code-reviewer", [])
    _record(capsys, session_dir, 2)
    out = _decide(capsys, session_dir, 2, fix_batch=_write_fix_batch(session_dir, 2, []),
                  max_rounds=2)
    assert out["action"] == "halt"


# --- delegation / tiers -------------------------------------------------------

def test_decide_delegates_to_shared_round_policy(tmp_path, capsys, monkeypatch):
    session_dir = _session(tmp_path)
    _reach_round2_scoped(tmp_path, capsys, session_dir)  # populate state
    calls = []
    real = CLP.review_round_policy.plan_round
    monkeypatch.setattr(CLP.review_round_policy, "plan_round",
                        lambda state: calls.append(state) or real(state))
    _plan(capsys, session_dir, 2)
    _write_findings(session_dir, 2, "code-reviewer", [_finding("Code")])
    _record(capsys, session_dir, 2)
    _write_compiled(session_dir, 2, [_finding("Code")])
    _write_diff(session_dir, 2, [("fileA.py", "@@ -1 +1 @@\n-a\n+b")])
    _write_head_diff(session_dir, 2, [("fileA.py", "@@ -1 +2 @@\n-a\n+b\n+c")])
    _decide(capsys, session_dir, 2, fix_batch=_write_fix_batch(session_dir, 2, [_finding("Code")]))
    assert calls, "decide must delegate the schedule to review_round_policy.plan_round"
    assert calls[-1]["round"] == 3 and calls[-1]["dimensions"] == DIMS


def test_gate_decision_delegates_to_loop_state(tmp_path, capsys, monkeypatch):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir)
    seen = []
    real = CLP.loop_state.decide
    monkeypatch.setattr(CLP.loop_state, "decide",
                        lambda *a: seen.append(a) or real(*a))
    _decide(capsys, session_dir, 1, fix_batch=_write_fix_batch(session_dir, 1, []))
    assert seen, "the continuation action must come from loop_state.decide"


def test_tiers_are_roles_never_model_names(tmp_path, capsys):
    session_dir = _session(tmp_path)
    out = _reach_round2_scoped(tmp_path, capsys, session_dir)
    tiers = {d["tier"] for d in out["dims_to_run"]}
    assert tiers <= {CHEAP, DEEP}  # role names, never claude-* model ids


# --- SKILL.md wiring ----------------------------------------------------------

def test_skill_obeys_emitted_plan():
    skill = os.path.join(_HERE, "..", "..", "skills", "review-code", "SKILL.md")
    with open(skill, encoding="utf-8") as fh:
        text = fh.read()
    assert "code_loop_plan.py" in text, "SKILL.md must invoke the script-owned scheduler"
    assert "dims_to_run" in text, "SKILL.md must dispatch the emitted dims_to_run"
    # the reversal is stated explicitly, not silently
    assert "coverage uniform" not in text.lower() or "no longer" in text.lower() \
        or "reverse" in text.lower(), "the coverage-uniformity clause must be reversed, not kept"
