"""A saved session left at the retired fixer step is moved to `apply-fixes` before any command acts on it.

The fixtures under `fixtures/gen6_sessions/` are real generation-6 sessions, minted by the generation-6 driver;
`near-its-boundary` stands at its fixer step, `waiting-at-judgment` at an owner gate this version no longer has.
A test copies one to `tmp_path` before driving it; a fixture is never driven in place.

E12 a generation-6 state at the fixer step is migrated, not handed back; a state at a truly retired gate still is;
    a state of the current generation at the fixer step is migrated the same way.
"""
import json
import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import session_checkout  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD

FIXTURES = os.path.join(_HERE, "fixtures", "gen6_sessions")
AT_FIXER = "near-its-boundary"
AT_RETIRED_GATE = "waiting-at-judgment"
RETIRED_FIXER = "dispatch-fixer"
MIGRATED = "fix-step-migrated"
HANDED_BACK = "retired-gate-hand-back"


def _bootstrap(tmp_path, name):
    """Copy the fixture session to `tmp_path`, give it a real checkout and point its meta at it."""
    session_dir = str(tmp_path / "session")
    shutil.copytree(os.path.join(FIXTURES, name), session_dir)
    checkout = os.path.join(session_dir, "checkout")
    session_checkout.enter_checkout(checkout)
    session_checkout.seed_session_meta(session_dir, checkout)
    return session_dir


def _state(session_dir):
    ok, state = RD.load_state(session_dir)
    assert ok and isinstance(state, dict), state
    return state


def _rows(session_dir, outcome):
    return [row for row in RD.read_journal(session_dir) if row.get("outcome") == outcome]


def _migrated_session(tmp_path, generation=None):
    session_dir = _bootstrap(tmp_path, AT_FIXER)
    state = _state(session_dir)
    assert state["step"] == RETIRED_FIXER and state["pending"]["phase"] == RETIRED_FIXER
    anchor = state["_ordersAnchors"]["%d:%s:%d" % (state["round"], RETIRED_FIXER, state["pending"]["attempt"])]
    if generation is not None:
        state["sessionGeneration"] = generation
        RD.save_state(session_dir, state)
    return session_dir, state, anchor


def test_e12_a_generation_6_session_at_the_fixer_step_is_migrated_not_handed_back(tmp_path):
    # axis: the migration runs before the retired-gate hand-back, so a generation-6 fixer step is moved on — see bite-proof record c1l9a_wo3_apply_fixes
    session_dir, before, anchor = _migrated_session(tmp_path)
    assert before["sessionGeneration"] == 6
    out = RD.cmd_next(session_dir)
    assert out["ok"] is True and out["action"] == out["phase"] == RD.P_APPLY_FIXES, out
    assert out["round"] == before["round"]
    assert out["payload"]["startHead"] == anchor["headSha"]
    state = _state(session_dir)
    assert state["terminal"] is None and state["step"] == RD.P_APPLY_FIXES
    assert state["sessionGeneration"] == 6 and state["config"]["maxRounds"] == before["config"]["maxRounds"]
    assert "_escalatedRung" not in state and state["_fixStepHead"] == anchor["headSha"]
    (row,) = _rows(session_dir, MIGRATED)
    assert (row["phase"], row["round"], row["attempt"]) == (RETIRED_FIXER, before["round"],
                                                            before["pending"]["attempt"])
    assert _rows(session_dir, HANDED_BACK) == []
    assert not os.path.exists(os.path.join(session_dir, "round-%d" % before["round"], "orders",
                                           RD.P_APPLY_FIXES))


def test_e12_a_state_at_a_truly_retired_gate_is_still_handed_back(tmp_path):
    session_dir = _bootstrap(tmp_path, AT_RETIRED_GATE)
    assert _state(session_dir)["step"] not in (RETIRED_FIXER, RD.P_APPLY_FIXES)
    out = RD.cmd_next(session_dir)
    assert out["ok"] is True and out["action"] == RD.P_TERMINAL, out
    assert _state(session_dir)["terminal"] == "handed-back"
    assert len(_rows(session_dir, HANDED_BACK)) == 1 and _rows(session_dir, MIGRATED) == []


def test_e12_a_current_generation_state_at_the_fixer_step_is_migrated_the_same_way(tmp_path):
    session_dir, before, anchor = _migrated_session(tmp_path, generation=RD.SESSION_GENERATION)
    out = RD.cmd_next(session_dir)
    assert out["ok"] is True and out["action"] == RD.P_APPLY_FIXES, out
    assert out["payload"]["startHead"] == anchor["headSha"]
    assert len(_rows(session_dir, MIGRATED)) == 1 and _rows(session_dir, HANDED_BACK) == []
    # the step then folds as any apply-fixes report does
    state = _state(session_dir)
    assert state["pending"]["phase"] == RD.P_APPLY_FIXES and state["_fixStepHead"] == anchor["headSha"]


def test_e12_the_build_session_becomes_the_fix_maker_when_the_old_fixer_differs_from_the_host(tmp_path):
    session_dir, before, _anchor = _migrated_session(tmp_path)
    state = _state(session_dir)
    state["config"]["fixerVendor"] = "claude"
    state["config"]["seatMap"] = {"hostFamily": "openai"}
    state["seatMapReceipts"] = []
    state.pop("seatMap", None)
    host_vendor = RD._build_session_vendor({"hostFamily": "openai"})
    assert host_vendor not in (None, "claude")
    RD.save_state(session_dir, state)
    RD.cmd_next(session_dir)
    assert len(_rows(session_dir, MIGRATED)) == 1
    assert _state(session_dir)["config"]["fixerVendor"] == host_vendor


def test_e12_the_replaced_external_fixers_family_stays_a_maker_so_its_commits_are_not_self_audited(tmp_path):
    session_dir, _before, _anchor = _migrated_session(tmp_path)
    state = _state(session_dir)
    state["config"]["fixerVendor"] = "claude"
    _record_fix_work(state)
    state["config"]["seatMap"] = {"hostFamily": "openai"}
    state["seatMapReceipts"] = []
    state.pop("seatMap", None)
    former_family = RD.model_registry.family_for("implementer", "claude")
    host_vendor = RD._build_session_vendor({"hostFamily": "openai"})
    assert former_family is not None and host_vendor not in (None, "claude")
    RD.save_state(session_dir, state)
    RD.cmd_next(session_dir)
    after = _state(session_dir)
    assert after["config"]["fixerVendor"] == host_vendor
    assert after["formerFixerFamilies"] == [former_family]
    assert former_family in RD.receipt_disclosures.accumulated_maker_families(after)
    after["config"]["vendors"] = ["claude", host_vendor]
    vendor, independence = RD._auditor_vendor(
        after["config"], host_vendor, maker_families=RD.receipt_disclosures.accumulated_maker_families(after))
    assert (vendor, independence) == (None, "unseatable")


def _record_fix_work(state):
    """Record, in round 1, an external fixer (claude) that fixed something: the history that makes its
    family a maker."""
    state["rounds"]["1"]["fixerVendor"] = "claude"
    state["rounds"]["1"]["fix"] = {"fixes": ["fixed"], "commits": []}


def _continued_at_apply_fixes(tmp_path, seat_map):
    """The fixer-step fixture, moved on to `apply-fixes` and made a continued session that names an
    external fixer: no fix-maker mark, `fixerVendor` claude, the given seat map."""
    session_dir, _before, _anchor = _migrated_session(tmp_path)
    RD.cmd_next(session_dir)
    state = _state(session_dir)
    assert state["step"] == RD.P_APPLY_FIXES
    state.pop(RD.FIX_MAKER_MARK, None)
    state.pop("formerFixerFamilies", None)
    _record_fix_work(state)
    state["config"]["fixerVendor"] = "claude"
    state["config"]["seatMap"] = seat_map
    state["seatMapReceipts"] = []
    state.pop("seatMap", None)
    RD.save_state(session_dir, state)
    return session_dir


def test_e12_a_continued_session_past_the_fixer_step_also_takes_the_build_session_as_fix_maker(tmp_path):
    session_dir = _continued_at_apply_fixes(tmp_path, {"hostFamily": "openai"})
    former_family = RD.model_registry.family_for("implementer", "claude")
    host_vendor = RD._build_session_vendor({"hostFamily": "openai"})
    assert former_family is not None and host_vendor not in (None, "claude")
    RD.cmd_next(session_dir)
    after = _state(session_dir)
    assert after["config"]["fixerVendor"] == host_vendor and after[RD.FIX_MAKER_MARK] is True
    assert after["formerFixerFamilies"] == [former_family]
    # the attribution is once-only: a later command changes nothing
    after["config"]["fixerVendor"] = "claude"
    RD.save_state(session_dir, after)
    RD.cmd_next(session_dir)
    assert _state(session_dir)["config"]["fixerVendor"] == "claude"


def test_e12_a_configured_fixer_vendor_that_did_no_work_is_not_made_a_maker(tmp_path):
    session_dir = _continued_at_apply_fixes(tmp_path, {"hostFamily": "openai"})
    state = _state(session_dir)
    # before its first fix: no round names a fixer, and the step holds no commit past its start head
    for rec in state["rounds"].values():
        rec.pop("fixerVendor", None)
        rec.pop("fix", None)
    state["_fixStepHead"] = RD._fix_step_head(state["config"])
    RD.save_state(session_dir, state)
    host_vendor = RD._build_session_vendor({"hostFamily": "openai"})
    assert host_vendor not in (None, "claude")
    RD.cmd_next(session_dir)
    after = _state(session_dir)
    assert after["config"]["fixerVendor"] == host_vendor and after[RD.FIX_MAKER_MARK] is True
    assert "formerFixerFamilies" not in after
    assert RD.model_registry.family_for("implementer", "claude") not in (
        RD.receipt_disclosures.accumulated_maker_families(after))


def test_e12_a_former_fixer_vendor_with_a_recorded_fix_stays_a_maker_before_the_next_fix(tmp_path):
    session_dir = _continued_at_apply_fixes(tmp_path, {"hostFamily": "openai"})
    state = _state(session_dir)
    _record_fix_work(state)
    RD.save_state(session_dir, state)
    RD.cmd_next(session_dir)
    assert _state(session_dir)["formerFixerFamilies"] == [RD.model_registry.family_for("implementer", "claude")]


def test_e12_a_former_fixer_whose_only_work_was_a_pr_body_edit_stays_a_maker_before_its_audit(tmp_path):
    session_dir = _continued_at_apply_fixes(tmp_path, {"hostFamily": "openai"})
    state = _state(session_dir)
    # a body-only fix: empty fixes, no commits, a recorded body change, the step head unmoved
    state["rounds"]["1"]["fix"] = {"fixes": [], "commits": []}
    state["rounds"]["1"]["prBodyFix"] = {"before": "a" * 64, "after": "b" * 64}
    state["_fixStepHead"] = RD._fix_step_head(state["config"])
    RD.save_state(session_dir, state)
    former_family = RD.model_registry.family_for("implementer", "claude")
    host_vendor = RD._build_session_vendor({"hostFamily": "openai"})
    assert former_family is not None and host_vendor not in (None, "claude")
    RD.cmd_next(session_dir)
    after = _state(session_dir)
    assert after["config"]["fixerVendor"] == host_vendor
    assert after["formerFixerFamilies"] == [former_family]
    assert former_family in RD.receipt_disclosures.accumulated_maker_families(after)
    after["config"]["vendors"] = ["claude", host_vendor]
    vendor, independence = RD._auditor_vendor(
        after["config"], host_vendor, maker_families=RD.receipt_disclosures.accumulated_maker_families(after))
    assert (vendor, independence) == (None, "unseatable")


def test_e12_a_pr_body_record_that_changed_nothing_does_not_make_a_former_fixer_a_maker(tmp_path):
    session_dir = _continued_at_apply_fixes(tmp_path, {"hostFamily": "openai"})
    state = _state(session_dir)
    state["rounds"]["1"]["fix"] = {"fixes": [], "commits": []}
    state["rounds"]["1"]["prBodyFix"] = {"before": "a" * 64, "after": "a" * 64}
    state["_fixStepHead"] = RD._fix_step_head(state["config"])
    RD.save_state(session_dir, state)
    RD.cmd_next(session_dir)
    assert "formerFixerFamilies" not in _state(session_dir)


def test_e12_a_continued_session_whose_host_family_maps_to_no_vendor_leaves_the_fixer_unknown(tmp_path):
    session_dir = _continued_at_apply_fixes(tmp_path, {"hostFamily": "no-such-family"})
    assert RD._build_session_vendor({"hostFamily": "no-such-family"}) is None
    RD.cmd_next(session_dir)
    after = _state(session_dir)
    # a stale external vendor is never kept as the maker: the audit degrades instead
    assert after["config"]["fixerVendor"] is None and after[RD.FIX_MAKER_MARK] is True
    assert after["formerFixerFamilies"] == [RD.model_registry.family_for("implementer", "claude")]


def test_e12_a_new_session_keeps_a_fixer_vendor_it_was_given(tmp_path):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    out = RD.cmd_next(session_dir, TRD._cfg(fixerVendor="claude", seatMap={"hostFamily": "openai"}))
    assert out["ok"] is True, out
    state = _state(session_dir)
    assert state["config"]["fixerVendor"] == "claude" and state[RD.FIX_MAKER_MARK] is True
    assert "formerFixerFamilies" not in state


def test_e12_a_second_command_migrates_nothing_again(tmp_path):
    session_dir, _before, _anchor = _migrated_session(tmp_path)
    first = RD.cmd_next(session_dir)
    again = RD.cmd_next(session_dir)
    assert (again["phase"], again["attempt"], again["expectedStateHash"]) == (
        first["phase"], first["attempt"], first["expectedStateHash"])
    assert len(_rows(session_dir, MIGRATED)) == 1
