"""C1-L4: a review session never begins a round after its cap, and there is no ceiling above the cap.

`ROUND_CAP` (4) is the cap every session minted through the `next` CLI carries. The cap is a boundary on
the round about to begin: the cap round itself completes (audits, fix leg, verify gate on the post-fix
head), then the PR is handed back through `_hand_back(state, "round-cap", ..., cap=True)`. A stall found in
the cap round runs no recovery attempt. A loaded config above the cap (a session an earlier version
minted) is honored as stored. The library entry point (`new_state` / `run_loop`) is a harness and takes
any positive cap; the CLI refuses a `--max-rounds` that is not a positive integer within `ROUND_CAP`.

Drives the real round driver: `run_loop` with scripted seams for the loop-shaped cases, the CLI
(`next` / `submit`) for the loaded-state and flag cases, and the pieces directly for the edges.

Bite-proof record: c1l4_wo_b
"""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_record_session as RS  # noqa: E402
import round_phases as RP  # noqa: E402
import session_contract as SC  # noqa: E402
import test_review_record_session as TRRS  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD  # run_loop runs on test_round_driver's own load of the module

_CONSEQUENCE = TRD._CONSEQUENCE
_BUG = {"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}


def _kinds(state):
    return [d["kind"] for d in state["decisions"]]


def _trace(state):
    return [(d["kind"], d.get("round"), d.get("detail")) for d in state["decisions"]]


def _ledger(state):
    return {SC.finding_identity_key(e): e for e in state.get(SC.DISPOSITION_LEDGER_KEY) or []}


def _rows_titled(state, title):
    return [row for row in _ledger(state).values() if row.get("title") == title]


def _spy_actions(monkeypatch):
    """Record (action, round) for every action the loop emits."""
    seen = []
    orig = RD._advance

    def spy(state, config):
        step = orig(state, config)
        seen.append((step["action"], state["round"]))
        return step

    monkeypatch.setattr(RD, "_advance", spy)
    return seen


def _finding(title, severity, file="newsurf.py"):
    return {"title": title, "severity": severity, "consequence": _CONSEQUENCE, "file": file, "line": 1}


def _new_blockers_every_round():
    """Every review round raises a NEW blocking finding; the cap round raises an Important and a
    Critical. Audits stay clean, so nothing ever converges and the only exit is the cap."""
    seq = {"n": 0}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "gap-sweep":
            return []
        if dim == "scoped-finder":
            seq["n"] += 1
            if rnd == RP.ROUND_CAP:
                return [_finding("open-important", "Important"), _finding("open-critical", "Critical")]
            return [_finding("scoped-%d" % seq["n"], "Important")]
        if dim == "code-reviewer":
            seq["n"] += 1
            return {"findings": [_finding("panel-%d" % seq["n"], "Important", file="f.py")]}
        return {}

    fix_n = {"n": 0}

    def fix_step(batch, rnd, payload):
        fix_n["n"] += 1
        return {"fixes": [], "headDiff": TRD._headf_ns(fix_n["n"]), "changedSubjects": ["Code"]}

    return TRD._seams(reviewer=reviewer, fix_step=fix_step, vendors=["claude", "codex"])


def _failing_fix_seams(findings, extra_scoped=None, fail_titles=None):
    """The listed findings are fixed, never discharged (`fail_titles` None: every fix fails its audit)."""
    counter = {"n": 0}

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [dict(f) for f in findings]}
        if dim == "scoped-finder" and extra_scoped is not None and rnd == extra_scoped[0]:
            return [dict(f) for f in extra_scoped[1]]
        return []

    def fix_step(batch, rnd, payload):
        counter["n"] += 1
        return {"fixes": [], "headDiff": TRD._headf_ns(counter["n"]), "changedSubjects": ["Code"]}

    def plausible(clusters, rnd):
        return [{"id": i, "verdict": "PLAUSIBLE", "reason": "checked"}
                for c in (clusters or []) for i in (c.get("ids") or [])]

    def auditor(targets, rnd):
        out = []
        for t in targets or []:
            if fail_titles is None or t.get("title") in fail_titles:
                out.append({"id": t["id"], "ruling": "not-discharged", "reason": "broken"})
            else:
                out.append({"id": t["id"], "ruling": "discharged", "reason": "fix resolves it",
                            "evidence": "tests pass", "auditorVendor": t.get("auditorVendor")})
        return out

    return TRD._seams(reviewer=reviewer, verifier=plausible, fix_step=fix_step, auditor=auditor,
                      vendors=["claude", "codex"])


# --- T1: a session that never converges ends at the cap, round 4, and begins no fifth round -----

def test_t1_a_loop_that_never_converges_reaches_round_four_and_is_handed_back_at_the_cap(monkeypatch, tmp_path):
    # axis: the ROUND BOUNDARY in _cap_blocks — round 5 must never begin; the cap round itself still runs
    # to its verify gate — see bite-proof record c1l4_wo_b
    seen = _spy_actions(monkeypatch)
    _result, state = TRD._run_loop_capturing_state(_new_blockers_every_round(), TRD._cfg_cert())
    assert state["config"]["maxRounds"] == RP.ROUND_CAP == 4
    assert state["terminal"] == "handed-back"
    assert state["decisions"][-1]["kind"] == "round-cap", _kinds(state)
    assert sorted(state["rounds"]) == ["1", "2", "3", "4"]
    assert "5" not in state["rounds"] and state["round"] == 4
    assert max(rnd for _action, rnd in seen) == 4
    verifies = [i for i, (action, _rnd) in enumerate(seen) if action == RD.P_VERIFY]
    assert verifies and seen[verifies[-1]][1] == 4  # the cap round's verify gate ran
    assert seen[verifies[-1] + 1:] == []  # no action is emitted after the cap round's verify
    assert state["certification"]["shape"] is None
    for title in ("open-important", "open-critical"):
        rows = _rows_titled(state, title)
        assert len(rows) == 1, (title, _ledger(state))
        # an outcome, and neither fixed nor converged: the cap round's fix was never audited
        assert rows[0]["disposition"] == "left-for-owner", rows[0]
        assert "round cap" in rows[0]["settledReason"]
    session = TRRS.Session(tmp_path, **state).seat("code-reviewer").save()
    assert RS.account_from_session(session, TRRS.extras())["rounds"] == {
        "count": 4, "cap": 4, "capKind": "rounds", "stoppedAtCap": True}


# --- T2 / E7: the same fix fails its audit twice; one recovery is audited in the cap round ------

def test_t2_the_same_fix_failing_in_rounds_two_and_three_gets_a_recovery_audited_in_round_four(monkeypatch):
    # axis: a stall detected below the cap still gets its one recovery attempt (E7)
    seen = _spy_actions(monkeypatch)
    _result, state = TRD._run_loop_capturing_state(_failing_fix_seams([_BUG]), TRD._cfg_cert())
    kinds = _kinds(state)
    assert kinds.count("self-recovery") == 1, _trace(state)
    recovery = next(d for d in state["decisions"] if d["kind"] == "self-recovery")
    assert recovery["round"] == 3, recovery
    assert [r["round"] for r in state["auditRounds"]] == [2, 3, 4]  # the recovered fix is audited in round 4
    assert state["terminal"] == "handed-back"
    assert kinds[-1] == "round-cap", kinds  # the second stall is found in the cap round
    assert sorted(state["rounds"]) == ["1", "2", "3", "4"]
    assert max(rnd for _action, rnd in seen) == 4


# --- T3 / E6: a stall in the cap round runs no recovery ----------------------------------------

def test_t3_a_stall_found_in_the_cap_round_runs_no_recovery_attempt(monkeypatch):
    # axis: the cap-round guard in _handle_stall — round 4 is the cap, so a stall found there hands back
    # with no recovery and no fix leg — see bite-proof record c1l4_wo_b
    seen = _spy_actions(monkeypatch)
    late = [_finding("late", "Important")]
    seams = _failing_fix_seams([_BUG], extra_scoped=(2, late), fail_titles={"late"})
    _result, state = TRD._run_loop_capturing_state(seams, TRD._cfg_cert())
    kinds = _kinds(state)
    audited = {r["round"]: [o["ruling"] for o in r["outcomes"] if "late" in o.get("identity", "")]
               for r in state["auditRounds"]}
    assert audited.get(3) == ["not-discharged"] and audited.get(4) == ["not-discharged"], (
        audited, _trace(state))
    assert "self-recovery" not in kinds, kinds
    assert "selfRecovered" not in state or state["selfRecovered"] is not True
    assert state["terminal"] == "handed-back"
    assert kinds[-1] == "round-cap", kinds
    assert max(rnd for _action, rnd in seen) == 4
    assert max(rnd for action, rnd in seen if action == RD.P_APPLY_FIXES) == 3  # no fix leg in the cap round


# --- T4: a round-1 panel with nothing blocking ends at round 1 ----------------------------------

@pytest.mark.parametrize("severities,refute", [
    (("Important", "Important"), True),
    (("Minor", "Nit"), False),
], ids=["all-refuted", "minor-and-nit"])
def test_t4_a_panel_whose_findings_are_all_refuted_or_minor_ends_at_round_one(monkeypatch, severities, refute):
    # axis: FR-36 — findings the verifier refutes, and Minor/Nit ones, never open a second round
    seen = _spy_actions(monkeypatch)

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "code-reviewer":
            quality = {"consequenceKind": "code-quality", "consequence": "the name is harder to read"}
            return {"findings": [
                dict(_finding("first", severities[0], file="f.py"), line=1, **({} if refute else quality)),
                dict(_finding("second", severities[1], file="f.py"), line=2, **({} if refute else quality)),
            ]}
        return []

    def refuting(clusters, rnd):
        return {"verdicts": [{"id": i, "verdict": "REFUTED", "reason": "checked"}
                             for c in (clusters or []) for i in (c.get("ids") or [])],
                "vendor": "codex"}

    def confirming(clusters, rnd):
        return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran", "reason": "checked"}
                             for c in (clusters or []) for i in (c.get("ids") or [])],
                "vendor": "codex"}

    seams = TRD._seams(reviewer=reviewer, verifier=refuting if refute else confirming,
                       vendors=["claude", "codex"])
    _result, state = TRD._run_loop_capturing_state(seams, TRD._cfg_cert())
    assert state["terminal"] == "converged", (state["terminal"], _trace(state))
    round_one = state["rounds"]["1"]
    shown = (seen, _trace(state), {k: v for k, v in round_one.items() if k in ("verify", "verifyPasses", "verifierProvenance")})
    assert not refute or round_one["verifyPasses"][0]["REFUTED"] == 2, shown
    # axis: the surviving Minor/Nit findings are CONFIRMED by the verifier and still open no second round
    # — see bite-proof record c1l4_wo_f
    assert refute or round_one["verifyPasses"][0]["CONFIRMED"] == 2, shown
    assert sorted(state["rounds"]) == ["1"], (seen, _trace(state))
    assert RD.P_APPLY_FIXES not in [action for action, _rnd in seen]
    assert max(rnd for _action, rnd in seen) == 1


# --- T5 / E5: --max-rounds on a fresh CLI state -------------------------------------------------

@pytest.mark.parametrize("value", ["5", "0", "-1"])
def test_t5_a_fresh_cli_max_rounds_that_is_not_a_positive_int_within_the_cap_is_refused(tmp_path, capsys, value):
    # axis: the CLI refusal of --max-rounds — 5 is above ROUND_CAP and must write nothing — see
    # bite-proof record c1l4_wo_b
    d = str(tmp_path)
    rc, out = TRD._cli_next_json(d, ["--max-rounds=" + value] + TRD._guard_argv(d), capsys)
    assert rc == 1
    assert out == {"ok": False, "reason": "max-rounds-invalid", "value": int(value)}
    assert not os.path.exists(os.path.join(d, RD.STATE_FILE))


@pytest.mark.parametrize("value", ["1", "3", "4"])
def test_t5_a_fresh_cli_max_rounds_within_the_cap_is_stored(tmp_path, capsys, value):
    d = str(tmp_path)
    rc, out = TRD._cli_next_json(d, ["--max-rounds", value] + TRD._guard_argv(d), capsys)
    assert rc == 0 and out["ok"], out
    ok, state = RD.load_state(d)
    assert ok and state["config"]["maxRounds"] == int(value)


def test_t5_a_fresh_cli_session_without_the_flag_has_the_round_cap(tmp_path, capsys):
    d = str(tmp_path)
    rc, out = TRD._cli_next_json(d, TRD._guard_argv(d), capsys)
    assert rc == 0 and out["ok"], out
    ok, state = RD.load_state(d)
    assert ok and state["config"]["maxRounds"] == 4
    assert "maxRoundsAbsolute" not in state["config"]


def test_t5_the_max_rounds_absolute_flag_is_gone(tmp_path, capsys):
    d = str(tmp_path)
    with pytest.raises(SystemExit) as exc:
        RD.main(["next", "--session-dir", d, "--max-rounds-absolute", "5"] + TRD._guard_argv(d))
    assert exc.value.code == 2
    assert not os.path.exists(os.path.join(d, RD.STATE_FILE))


def test_t5_a_loaded_state_ignores_the_flag(tmp_path, capsys):
    d = str(tmp_path)
    rc, out = TRD._cli_next_json(d, ["--max-rounds", "3"] + TRD._guard_argv(d), capsys)
    assert rc == 0 and out["ok"], out
    rc, out = TRD._cli_next_json(d, ["--max-rounds", "9"] + TRD._guard_argv(d, fresh=False), capsys)
    assert rc == 0 and out["ok"], out
    ok, state = RD.load_state(d)
    assert ok and state["config"]["maxRounds"] == 3


@pytest.mark.parametrize("value", [0, -1, True, "4"])
def test_e5_the_library_path_refuses_a_non_positive_or_non_int_max_rounds(value):
    with pytest.raises(RD.MaxRoundsRefusal) as exc:
        RD._default_config({"maxRounds": value})
    assert exc.value.reason == "max-rounds-invalid"
    assert exc.value.value is value or exc.value.value == value


@pytest.mark.parametrize("value", [1, 4, 7, 20])
def test_the_library_path_takes_any_positive_int_cap(value):
    assert RD._default_config({"maxRounds": value})["maxRounds"] == value
    assert RD.new_state(TRD._cfg(maxRounds=value))["config"]["maxRounds"] == value


# --- E1 / E2 / E3: the boundary predicate and the cap lookup -----------------------------------

def test_e1_e2_the_boundary_runs_the_cap_round_and_refuses_the_one_after():
    state = RD.new_state(TRD._cfg())
    state["round"] = 3
    assert RD._advance_round(state, state["config"], reason="test") is True  # next_round == cap: runs
    assert state["round"] == 4 and not state.get("terminal")
    assert RD._advance_round(state, state["config"], reason="test") is False  # next_round == cap + 1
    assert state["round"] == 4 and "5" not in state.get("rounds", {})
    assert state["terminal"] == "handed-back" and state["decisions"][-1]["kind"] == "round-cap"
    assert state["certification"]["shape"] is None


@pytest.mark.parametrize("stored", [True, False, 0, -3, "4", None, 2.5, [], {}])
def test_e3_a_malformed_loaded_max_rounds_falls_back_to_the_round_cap_never_to_no_cap(stored):
    assert RD._round_cap({"maxRounds": stored}) == RP.ROUND_CAP
    assert RD._round_cap({}) == RP.ROUND_CAP
    assert RD._round_cap(None) == RP.ROUND_CAP


def test_e3_a_well_formed_loaded_max_rounds_is_honored_as_stored():
    assert RD._round_cap({"maxRounds": 7}) == 7
    assert RD._round_cap({"maxRounds": 2}) == 2


# --- T6 / E4: a loaded non-terminal state above its cap hands back on the next `next` -----------

def test_t6_a_loaded_state_edited_to_round_five_hands_back_on_the_next_next(tmp_path):
    # axis: _cap_blocks_loaded at the `next` call site — a resumed state already past its cap
    d = str(tmp_path)
    first = RD.cmd_next(d, TRD._cfg())
    assert first["ok"] and first["phase"] == RD.P_PANEL, first
    ok, state = RD.load_state(d)
    assert ok and state["config"]["maxRounds"] == 4 and not state.get("terminal")
    state["round"] = state["config"]["maxRounds"] + 1
    RD.save_state(d, state)
    out = RD.cmd_next(d)
    assert out["ok"] and out["phase"] == RD.P_TERMINAL, out
    ok, reloaded = RD.load_state(d)
    assert ok
    assert reloaded["terminal"] == "handed-back"
    assert reloaded["decisions"][-1]["kind"] == "round-cap"
    assert reloaded["certification"]["shape"] is None
    rows = [r for r in RD.read_journal(d) if r.get("outcome") == "loaded-cap-hand-back"]
    assert rows, RD.read_journal(d)


# --- T7: a loaded config above the cap is honored as stored ------------------------------------

def test_t7_a_loaded_state_whose_config_says_seven_begins_round_five_and_hands_back_after_round_seven(tmp_path):
    # axis: _round_cap honors a stored cap above ROUND_CAP — it is not clamped
    d = str(tmp_path)
    checkout = os.path.join(d, "checkout")
    TRD.enter_checkout(checkout)
    TRD._seed_repo_root_if_missing(d, checkout)
    seq = {"n": 0}
    base = TRD._responder(round1_findings=[_BUG], vendors=TRD._cfg()["vendors"])

    def respond(phase, payload, rnd):
        if phase == RD.P_SCOPED:
            seq["n"] += 1
            return {"findings": [_finding("scoped-%d" % seq["n"], "Important")]}
        if phase == RD.P_APPLY_FIXES:
            seq["n"] += 1
            return {"fixes": [], "headDiff": TRD._headf_ns(seq["n"]), "changedSubjects": ["Code"]}
        return base(phase, payload, rnd)

    first = RD.cmd_next(d, TRD._cfg())
    assert first["ok"], first
    ok, state = RD.load_state(d)
    assert ok and state["config"]["maxRounds"] == 4
    state["config"]["maxRounds"] = 7  # what a generation-6 session carries
    RD.save_state(d, state)
    emitted, payload = [], None
    for _ in range(200):
        n = RD.cmd_next(d)
        assert n["ok"], n
        emitted.append(n["round"])
        if n["action"] == RD.P_TERMINAL:
            payload = n["payload"]
            break
        art = TRD._claim_reviewer(d, n["phase"], respond(n["phase"], n["payload"], n["round"]))
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    assert payload is not None, "the loop did not reach a terminal"
    assert payload["verdict"] == "handed-back"
    assert 5 in emitted and max(emitted) == 7, sorted(set(emitted))
    ok, final = RD.load_state(d)
    assert ok
    assert sorted(final["rounds"]) == ["1", "2", "3", "4", "5", "6", "7"]
    assert final["decisions"][-1]["kind"] == "round-cap"
    assert final["config"]["maxRounds"] == 7
