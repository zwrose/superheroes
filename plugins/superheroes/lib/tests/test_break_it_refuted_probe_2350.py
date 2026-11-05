"""A refuted break-it probe never makes a finding owe a kept test (#2350).

A verifier refutes a reviewer's break-it probe; synthesis then keeps the probe as a repeat of an earlier,
already-fixed finding (`fixed` + `repeatKept`). The probe's own test was never committed, so the kept check
must not run it, while the fixed finding's real kept test is still checked.

Cases:
- T1 the DoD case, real flow: a refuted probe kept as a repeat of an earlier fixed finding converges, the key
  reads `not-required` / `refuted-probe`, and `check_kept` never runs for it
- T2 the same key raised again as a refuted probe with a different body: the round-1 run is the one checked
  (a) present and passing -> kept, (b) removed from head -> parks `missing`, (c) changed in head -> parks `changed`
- T3 a fixed finding never refuted still parks when its test is dropped (`missing`) or changed (`changed`)
- T4 a fixed finding with its kept test present and passing is `kept` and converges
- T5 a newer real `fixed` disposition pops `repeatKept` and puts the stamped run back under the check
- T6 a refuted probe raised after a test restore fails closed (`unresolved` / `restore-shadowed-by-refuted-probe`);
  a probe in the restore's own round does not
- T7 the stamp writer marks only the refuted finding's current-round runs

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo_a_2350_refuted_probe.md
"""
import hashlib
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import break_it  # noqa: E402
import round_driver as RD  # noqa: E402
import test_break_it_loop as TL  # noqa: E402  (its `World` drives `RD._fold`)
import test_repeat_marks_c1l8 as C8  # noqa: E402  (its verifier and synthesis helpers)
from test_break_it_loop import world  # noqa: E402,F401  (the fixture, reused by name)

V = RD.verification
PROBE_TITLE = TL._break_it_finding()["title"]
OTHER_PATH = "tests/test_other.py"
RECEIPT = {"headSha": "a" * 40}


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.fixture
def spy(monkeypatch):
    """Record every `check_kept` call and run the real one."""
    calls = []
    real = break_it.check_kept

    def recording(*args, **kwargs):
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(break_it, "check_kept", recording)
    return calls


def _seat(world):
    """The seat map and fixer vendor `test_repeat_marks_c1l8._state` uses, so a non-maker verifier is seatable."""
    world.state["config"]["seatMap"] = {"hostFamily": "anthropic"}
    world.state["config"]["fixerVendor"] = "codex"


def _verdicts(world, by_title):
    """Fold the verifier's ``by_title`` verdicts ({title: CONFIRMED | PLAUSIBLE | REFUTED}) over the staged findings."""
    state = world.state
    vs = []
    for staged in V.stage_ids(state["_toVerify"]):
        verdict = by_title.get(staged["title"])
        if verdict is not None:
            vs.append(dict({"id": staged["id"], "verdict": verdict, "reason": "checked: " + verdict},
                           **({"evidence": "ran"} if verdict == "CONFIRMED" else {})))
    RD._fold_verifiers(state, state["config"], {
        "verdicts": vs, "verifierVendor": RD._nonpanel_selection(state, None, RD.P_VERIFIERS)[0]})


def _row_of(world, key):
    return C8._ledger(world.state)[key]


def _kept_rows(world):
    return world.round_record["breakItKept"]


def _earlier_alpha(world):
    """Round 1: an unrelated finding staged and closed `fixed` with a receipt, as an earlier round did."""
    _seat(world)
    return C8._earlier(world.state, C8._raw("alpha bug", id="F-1"), "fixed", dispositionReceipt=RECEIPT)


def _refuted_probe_kept_as_repeat(world):
    """Round 2: a break-it probe whose run is recorded, refuted by the verifier, kept as a repeat of the earlier
    fixed finding. Returns the probe's key."""
    _earlier_alpha(world)
    world.state["round"] = 2
    world.fold_panel(TL._break_it_finding())
    key = world.key_of_failed_run()
    _verdicts(world, {PROBE_TITLE: "REFUTED"})
    C8._synth(world.state, [C8._group(C8._ids(world.state)[PROBE_TITLE], ref="e1")])
    return key


def _same_key_probe_refuted(world):
    """Round 1: a break-it finding raised (real failing run) and closed `fixed`. Round 2: the same key raised again
    as a probe carrying a different body, refuted, same-key synthesis restores `fixed`. Returns the key."""
    _seat(world)
    world.fold_panel(TL._break_it_finding())
    key = world.key_of_failed_run()
    world.disposition("fixed", dispositionReceipt=RECEIPT)
    world.state["round"] = 2
    world.fold_panel(TL._break_it_finding(TL._TEST_FAILING + "# a different probe body\n"))
    assert world.key_of_failed_run() == key, "premise: the probe shares the finding's key"
    _verdicts(world, {PROBE_TITLE: "REFUTED"})
    C8._synth(world.state, None)
    return key


# ---- T1: the DoD case, real flow -----------------------------------------------------------------

# bites on: G1 (no stamp -> the run is checked), G2 (no skip -> check_kept runs on the probe's uncommitted test and parks)
def test_t1_a_refuted_probe_kept_as_a_repeat_of_a_fixed_finding_owes_no_kept_test(world, spy):
    key = _refuted_probe_kept_as_repeat(world)
    row = _row_of(world, key)
    assert row["disposition"] == "fixed" and row["grade"]["verdict"] == "wrong"
    assert isinstance(row["repeatKept"], dict)
    (run,) = world.round_record["breakItRuns"]
    assert run[RD.BREAK_IT_REFUTED_FIELD] is True
    world.fix(None)  # the fix does not carry the probe's test
    assert RD._break_it_kept_step(world.state, world.state["config"]) is False
    assert spy == []
    assert _kept_rows(world) == [{"findingKey": key, "path": TL.TEST_PATH, "outcome": "not-required",
                                  "reason": "refuted-probe"}]
    assert not [r for r in _kept_rows(world) if r["outcome"] in ("unresolved", "missing")]
    detail = [d["detail"] for d in world.state["decisions"] if d["kind"] == "break-it-kept"]
    # (the synthesis fold's own converge attempt recorded the same decision once already)
    assert detail[-1] == "0 checked: 0 kept, 0 not kept, 1 not required, 0 ruled out of scope"
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    assert world.state["terminal"] == "converged"
    assert spy == []


# ---- T2: the same key raised again as a refuted probe ----------------------------------------------

# bites on: G2 (no skip -> the probe's round-2 run is the latest and its body is checked, not round 1's), G1 (no stamp)
def test_t2a_the_round_one_run_is_checked_when_its_test_is_kept(world, spy):
    key = _same_key_probe_refuted(world)
    row = _row_of(world, key)
    assert row["disposition"] == "fixed" and isinstance(row["repeatKept"], dict)
    first, second = world.state["rounds"]["1"]["breakItRuns"][0], world.round_record["breakItRuns"][0]
    assert first["sha256"] != second["sha256"] and RD.BREAK_IT_REFUTED_FIELD not in first
    assert second[RD.BREAK_IT_REFUTED_FIELD] is True
    spy.clear()  # the synthesis fold's own converge attempt, before any fix, is setup
    world.fix(TL._TEST_FAILING)
    assert RD._break_it_kept_step(world.state, world.state["config"]) is False
    (call,) = spy
    assert call[3]["sha256"] == first["sha256"] == _sha(TL._TEST_FAILING)
    (kept,) = _kept_rows(world)
    assert kept["findingKey"] == key and kept["outcome"] == "kept"


# bites on: G2 (the unskipped round-1 run is what must park when its test is gone)
def test_t2b_the_round_one_test_removed_from_head_parks_missing(world, spy):
    key = _same_key_probe_refuted(world)
    spy.clear()  # the synthesis fold's own converge attempt, before any fix, is setup
    world.fix(None)
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    assert world.state["terminal"] == "cannot-certify"
    (kept,) = _kept_rows(world)
    assert (kept["findingKey"], kept["outcome"]) == (key, "missing")
    assert len(spy) == 1


# bites on: G2 (the unskipped round-1 run is what must park when its test was changed)
def test_t2c_the_round_one_test_changed_in_head_parks_changed(world, spy):
    key = _same_key_probe_refuted(world)
    spy.clear()  # the synthesis fold's own converge attempt, before any fix, is setup
    world.fix(TL._TEST_WEAKENED)
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    assert world.state["terminal"] == "cannot-certify"
    (kept,) = _kept_rows(world)
    assert (kept["findingKey"], kept["outcome"]) == (key, "changed")
    assert len(spy) == 1


# ---- T3: the sibling guard still fires -------------------------------------------------------------

# bites on: the kept check itself (a never-refuted fixed finding keeps owing it)
@pytest.mark.parametrize("head_test, outcome", [(None, "missing"), (TL._TEST_WEAKENED, "changed")])
def test_t3_a_fixed_finding_never_refuted_still_parks_when_its_test_is_dropped_or_changed(world, head_test, outcome):
    world.fold_panel(TL._break_it_finding())
    key = world.key_of_failed_run()
    world.disposition("fixed")
    world.fix(head_test)
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    assert world.state["terminal"] == "cannot-certify"
    (kept,) = _kept_rows(world)
    assert (kept["findingKey"], kept["outcome"]) == (key, outcome)


# ---- T4: the healthy case is unchanged -------------------------------------------------------------

# bites on: the kept check itself (a kept test certifies)
def test_t4_a_fixed_finding_with_its_test_kept_is_kept_and_converges(world):
    world.fold_panel(TL._break_it_finding())
    world.disposition("fixed")
    world.fix(TL._TEST_FAILING)
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    assert world.state["terminal"] == "converged"
    (kept,) = _kept_rows(world)
    assert kept["outcome"] == "kept"


# ---- T5: a later real disposition clears the exemption ---------------------------------------------

# bites on: G3 (the skip on the stamp alone ignores that repeatKept is gone)
def test_t5_a_newer_real_fixed_disposition_puts_the_stamped_run_back_under_the_check(world, spy):
    key = _refuted_probe_kept_as_repeat(world)
    RD._record_disposition(world.state, key, "fixed", 3)
    assert "repeatKept" not in _row_of(world, key), "premise: a newer disposition pops the marker"
    world.fix(None)
    assert RD._break_it_kept_step(world.state, world.state["config"]) is True
    assert len(spy) == 1
    (kept,) = _kept_rows(world)
    assert (kept["findingKey"], kept["outcome"]) == (key, "missing")


# ---- T6: a restore shadowed by a later refuted probe fails closed -----------------------------------

def _restore_shape(world, probe_round):
    """Key K: an unstamped run in round 1, a `testRestore` entry in round 2, a stamped run in ``probe_round``,
    ledger row `fixed` carrying `repeatKept`."""
    world.fold_panel(TL._break_it_finding())
    key = world.key_of_failed_run()
    run = world.round_record["breakItRuns"][0]
    world.disposition("fixed", dispositionReceipt=RECEIPT)
    _row_of(world, key)["repeatKept"] = {"outcome": "fixed", "reason": "kept"}
    world.state["rounds"].setdefault("2", {})["testRestore"] = [{"findingKey": key}]
    probes = world.state["rounds"].setdefault(str(probe_round), {}).setdefault("breakItRuns", [])
    probes.append(dict(run, **{RD.BREAK_IT_REFUTED_FIELD: True}))
    world.state["round"] = 3
    world.fix(None)
    return key


# bites on: G4 (without the branch the restored bytes are read from a re-seeded block and check_kept runs)
def test_t6_a_refuted_probe_after_a_restore_fails_closed(world, spy):
    key = _restore_shape(world, probe_round=3)
    assert RD._break_it_kept_step(world.state, world.state["config"]) is True
    assert spy == []
    (kept,) = _kept_rows(world)
    assert kept == {"findingKey": key, "path": TL.TEST_PATH, "outcome": "unresolved",
                    "reason": "restore-shadowed-by-refuted-probe", "run": None}


# bites on: G4 (the branch is tied to a probe strictly after the restore)
def test_t6b_a_refuted_probe_in_the_restores_own_round_is_not_shadowing(world, spy):
    _restore_shape(world, probe_round=2)
    assert RD._break_it_kept_step(world.state, world.state["config"]) is True
    assert len(spy) == 1
    assert "restore-shadowed-by-refuted-probe" not in [r["reason"] for r in _kept_rows(world)]


# ---- T7: the stamp writer ----------------------------------------------------------------------------

# bites on: G1 (the stamp write), and the current-round-only, refuted-key-only scope of the write
def test_t7_only_the_refuted_findings_current_round_runs_are_stamped(world):
    _seat(world)
    world.fold_panel(TL._break_it_finding())
    key = world.key_of_failed_run()
    world.state["round"] = 2
    other = TL._break_it_finding(title="Break-it: a second retried charge", file=OTHER_PATH,
                                 suggestion=TL._block(OTHER_PATH, TL._TEST_FAILING))
    world.fold_panel(TL._break_it_finding(TL._TEST_FAILING + "# round two\n"), other)
    _verdicts(world, {PROBE_TITLE: "REFUTED", other["title"]: "CONFIRMED"})
    (earlier,) = world.state["rounds"]["1"]["breakItRuns"]
    current = world.round_record["breakItRuns"]
    assert len(current) == 2
    by_key = {r["findingKey"]: r for r in current}
    assert by_key[key][RD.BREAK_IT_REFUTED_FIELD] is True
    (confirmed,) = [r for r in current if r["findingKey"] != key]
    assert RD.BREAK_IT_REFUTED_FIELD not in confirmed
    assert earlier["findingKey"] == key and RD.BREAK_IT_REFUTED_FIELD not in earlier
